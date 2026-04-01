from __future__ import annotations

import random
from dataclasses import dataclass

import simpy

from services.scheduler.health_aware import HealthAwareWeights

from .entities import Job, Machine
from .scheduling import BaselineScheduler, SchedulerContext, SchedulingPolicy


@dataclass(slots=True)
class FactoryConfig:
    num_machines: int = 3
    arrival_rate_per_hour: float = 6.0
    mean_processing_time_hours: float = 0.35
    due_date_factor: float = 3.0
    scheduling_policy: SchedulingPolicy = SchedulingPolicy.QUEUE_BASED
    health_w1: float = 0.35
    health_w2: float = 0.30
    health_w3: float = 0.20
    health_w4: float = 0.15
    enable_failures: bool = False
    weibull_shape: float = 1.8
    weibull_scale_hours: float = 16.0
    mean_repair_time_hours: float = 1.2
    repair_crews: int = 1
    preventive_maintenance_interval_hours: float = 10.0
    preventive_maintenance_duration_hours: float = 0.6
    random_seed: int = 42


class FactorySimulation:
    def __init__(self, config: FactoryConfig) -> None:
        self.config = config
        self.rng = random.Random(config.random_seed)
        self.env = simpy.Environment()
        self.incoming_queue = simpy.Store(self.env)
        self.machine_queues = [simpy.Store(self.env) for _ in range(config.num_machines)]
        self.scheduler = BaselineScheduler(
            policy=config.scheduling_policy,
            rng=self.rng,
            health_weights=HealthAwareWeights(
                w1=config.health_w1,
                w2=config.health_w2,
                w3=config.health_w3,
                w4=config.health_w4,
            ),
        )
        self.repair_resource = simpy.Resource(self.env, capacity=config.repair_crews)
        self.machines = [Machine(machine_id=i) for i in range(config.num_machines)]
        self.jobs: list[Job] = []
        self.event_log: list[dict[str, float | int | str]] = []
        self.worker_processes: dict[int, simpy.events.Process] = {}
        self.preferred_machine_by_job_id: dict[int, int] = {}
        self.preferred_candidate_index_by_job_id: dict[int, int] = {}
        self._job_counter = 0
        self._throughput = 0

    def _sample_interarrival(self) -> float:
        return self.rng.expovariate(self.config.arrival_rate_per_hour)

    def _sample_processing_time(self) -> float:
        low = self.config.mean_processing_time_hours * 0.4
        high = self.config.mean_processing_time_hours * 1.6
        return self.rng.uniform(low, high)

    def _sample_time_to_failure(self) -> float:
        return self.config.weibull_scale_hours * self.rng.weibullvariate(1.0, self.config.weibull_shape)

    def _sample_repair_duration(self) -> float:
        return max(0.1, self.rng.expovariate(1.0 / max(self.config.mean_repair_time_hours, 1e-9)))

    def _record_event(self, event_type: str, **payload: float | int | str) -> None:
        self.event_log.append({"time": self.env.now, "event": event_type, **payload})

    def job_arrivals(self) -> simpy.events.Event:
        while True:
            inter_arrival = self._sample_interarrival()
            yield self.env.timeout(inter_arrival)

            processing_time = self._sample_processing_time()
            due_date = self.env.now + processing_time * self.config.due_date_factor

            job = Job(
                job_id=self._job_counter,
                arrival_time=self.env.now,
                processing_time=processing_time,
                due_date=due_date,
            )
            # Backward-compatible jobs auto-create one operation with empty candidates.
            op = job.current_operation()
            if op is not None and not op.candidate_machines:
                op.candidate_machines = [m.machine_id for m in self.machines]
            self._job_counter += 1
            self.jobs.append(job)
            self._record_event(
                "job_arrived",
                job_id=job.job_id,
                processing_time=round(job.processing_time, 4),
                due_date=round(job.due_date, 4),
            )
            yield self.incoming_queue.put(job)

    def operation_dispatcher(self) -> simpy.events.Event:
        while True:
            job = yield self.incoming_queue.get()
            operation = job.current_operation()
            if operation is None:
                continue

            queue_lengths = [len(q.items) for q in self.machine_queues]
            queue_workload = [
                sum(
                    (queued_job.current_operation().processing_time if queued_job.current_operation() is not None else 0.0)
                    for queued_job in q.items
                )
                for q in self.machine_queues
            ]
            machine_health = [
                max(0.05, 1.0 - ((m.failure_count * 0.12) + (m.busy_time_since_maintenance / 30.0)))
                for m in self.machines
            ]
            due_date_urgency = 1.0 / max(job.due_date - self.env.now, 1e-6)

            candidates = operation.candidate_machines or [m.machine_id for m in self.machines]
            available_candidates = [
                machine_id
                for machine_id in candidates
                if self.machines[machine_id].state != "down"
            ]

            if not available_candidates:
                self._record_event(
                    "routing_attempt_failed",
                    job_id=job.job_id,
                    operation=job.current_operation_index,
                    candidates=str(candidates),
                    reason="no_available_candidate",
                )
                yield self.env.timeout(0.05)
                yield self.incoming_queue.put(job)
                continue

            preferred_machine = self.preferred_machine_by_job_id.pop(job.job_id, None)
            if preferred_machine is not None and preferred_machine in available_candidates:
                selected_machine = preferred_machine
            else:
                preferred_candidate_index = self.preferred_candidate_index_by_job_id.pop(job.job_id, None)
                if (
                    preferred_candidate_index is not None
                    and 0 <= preferred_candidate_index < len(available_candidates)
                ):
                    selected_machine = available_candidates[preferred_candidate_index]
                else:
                    selected_machine = self.scheduler.select_from_candidates(
                    job=job,
                    context=SchedulerContext(
                        machines=self.machines,
                        queue_lengths=queue_lengths,
                        queue_workload_hours=queue_workload,
                        machine_health=machine_health,
                        due_date_urgency=due_date_urgency,
                    ),
                    candidate_machines=available_candidates,
                )

            operation.assigned_machine = selected_machine
            if operation.state in {"pending", "interrupted"}:
                operation.state = "ready"

            yield self.machine_queues[selected_machine].put(job)
            self._record_event(
                "operation_routed",
                job_id=job.job_id,
                operation=job.current_operation_index,
                machine_id=selected_machine,
                candidates=str(available_candidates),
                policy=self.config.scheduling_policy.value,
            )
            self._record_event(
                "job_dispatched",
                job_id=job.job_id,
                machine_id=selected_machine,
                policy=self.config.scheduling_policy.value,
            )

    def job_dispatcher(self) -> simpy.events.Event:
        # Backward-compatible alias for old callers.
        return self.operation_dispatcher()

    def machine_worker(self, machine: Machine) -> simpy.events.Event:
        local_queue = self.machine_queues[machine.machine_id]
        while True:
            machine.queue_depth_samples.append(len(local_queue.items))
            job = yield local_queue.get()
            operation = job.current_operation()
            if operation is None:
                continue

            while machine.state in {"down", "maintenance"}:
                yield self.env.timeout(0.05)

            machine.state = "busy"
            machine.last_state_change = self.env.now
            machine.processing_started_at = self.env.now
            machine.current_job = job
            machine.current_operation_index = job.current_operation_index
            job.start_time = self.env.now
            operation.state = "in_progress"
            operation.assigned_machine = machine.machine_id
            operation.start_time = self.env.now

            self._record_event(
                "operation_started",
                machine_id=machine.machine_id,
                job_id=job.job_id,
                operation=job.current_operation_index,
                queue_size=len(local_queue.items),
            )
            self._record_event(
                "job_started",
                machine_id=machine.machine_id,
                job_id=job.job_id,
                queue_size=len(local_queue.items),
            )

            try:
                yield self.env.timeout(operation.processing_time)
            except simpy.Interrupt as interrupt:
                elapsed = self.env.now - (machine.processing_started_at or self.env.now)
                remaining = max(operation.processing_time - elapsed, 0.05)
                operation.processing_time = remaining
                operation.state = "interrupted"
                operation.reroute_count += 1
                job.rerouting_history.append(
                    {
                        "time": self.env.now,
                        "job_id": job.job_id,
                        "operation": job.current_operation_index,
                        "from_machine": machine.machine_id,
                        "to_machine": None,
                        "reason": str(interrupt.cause),
                    }
                )
                machine.current_job = None
                machine.processing_started_at = None
                machine.current_operation_index = None
                machine.state = "idle"
                self._record_event(
                    "operation_interrupted",
                    machine_id=machine.machine_id,
                    job_id=job.job_id,
                    operation=job.current_operation_index,
                    reason=str(interrupt.cause),
                    remaining_processing=round(remaining, 4),
                )
                self._record_event(
                    "job_interrupted",
                    machine_id=machine.machine_id,
                    job_id=job.job_id,
                    reason=str(interrupt.cause),
                    remaining_processing=round(remaining, 4),
                )
                self._record_event(
                    "job_rerouted",
                    job_id=job.job_id,
                    operation=job.current_operation_index,
                    from_machine=machine.machine_id,
                )
                yield self.incoming_queue.put(job)
                continue

            machine.processed_jobs += 1
            machine.busy_time += operation.processing_time
            machine.busy_time_since_maintenance += operation.processing_time
            machine.state = "idle"
            machine.current_job = None
            machine.processing_started_at = None
            machine.current_operation_index = None
            operation.completion_time = self.env.now
            operation.state = "completed"

            self._record_event(
                "operation_completed",
                machine_id=machine.machine_id,
                job_id=job.job_id,
                operation=job.current_operation_index,
                completion_time=round(self.env.now, 4),
            )

            job.advance_operation()
            if job.has_remaining_operations():
                next_op = job.current_operation()
                if next_op is not None and next_op.state == "pending":
                    next_op.state = "ready"
                yield self.incoming_queue.put(job)
            else:
                job.completion_time = self.env.now
                self._throughput += 1
                self._record_event(
                    "job_completed",
                    machine_id=machine.machine_id,
                    job_id=job.job_id,
                    completion_time=round(self.env.now, 4),
                )

    def machine_failure_process(self, machine: Machine) -> simpy.events.Event:
        while True:
            yield self.env.timeout(self._sample_time_to_failure())
            if machine.state in {"down", "maintenance"}:
                continue

            machine.failure_count += 1
            self._record_event(
                "machine_failed",
                machine_id=machine.machine_id,
                failure_count=machine.failure_count,
            )
            self._record_event(
                "machine_failure",
                machine_id=machine.machine_id,
                failure_count=machine.failure_count,
            )

            worker = self.worker_processes.get(machine.machine_id)
            if worker is not None and machine.state == "busy":
                worker.interrupt("machine_failure")

            with self.repair_resource.request() as request:
                yield request
                machine.state = "down"
                repair_time = self._sample_repair_duration()
                repair_start = self.env.now
                yield self.env.timeout(repair_time)
                machine.downtime += self.env.now - repair_start
                machine.state = "idle"
                self._record_event(
                    "machine_repaired",
                    machine_id=machine.machine_id,
                    repair_time=round(repair_time, 4),
                )

    def preventive_maintenance_process(self, machine: Machine) -> simpy.events.Event:
        while True:
            yield self.env.timeout(0.2)
            if machine.state != "idle":
                continue
            if (
                machine.busy_time_since_maintenance
                < self.config.preventive_maintenance_interval_hours
            ):
                continue

            machine.preventive_maintenance_count += 1
            self._record_event(
                "preventive_maintenance_started",
                machine_id=machine.machine_id,
                count=machine.preventive_maintenance_count,
            )

            with self.repair_resource.request() as request:
                yield request
                machine.state = "maintenance"
                start = self.env.now
                yield self.env.timeout(self.config.preventive_maintenance_duration_hours)
                machine.downtime += self.env.now - start
                machine.busy_time_since_maintenance = 0.0
                machine.state = "idle"
                self._record_event(
                    "preventive_maintenance_completed",
                    machine_id=machine.machine_id,
                    duration=round(self.config.preventive_maintenance_duration_hours, 4),
                )

    def run(self, until_hours: float = 24.0) -> dict[str, float | int]:
        self.env.process(self.job_arrivals())
        self.env.process(self.operation_dispatcher())
        for machine in self.machines:
            worker = self.env.process(self.machine_worker(machine))
            self.worker_processes[machine.machine_id] = worker
            if self.config.enable_failures:
                self.env.process(self.machine_failure_process(machine))
                self.env.process(self.preventive_maintenance_process(machine))

        self.env.run(until=until_hours)
        return self.summary()

    def summary(self) -> dict[str, float | int]:
        finished_jobs = [job for job in self.jobs if job.completion_time is not None]
        if finished_jobs:
            makespan = max(job.completion_time or 0.0 for job in finished_jobs)
            avg_tardiness = sum(
                max((job.completion_time or 0.0) - job.due_date, 0.0)
                for job in finished_jobs
            ) / len(finished_jobs)
        else:
            makespan = 0.0
            avg_tardiness = 0.0

        total_busy_time = sum(machine.busy_time for machine in self.machines)
        total_downtime = sum(machine.downtime for machine in self.machines)
        total_failures = sum(machine.failure_count for machine in self.machines)
        total_preventive = sum(
            machine.preventive_maintenance_count for machine in self.machines
        )
        capacity_window = max(self.env.now, 1e-9) * len(self.machines)
        utilization = total_busy_time / capacity_window

        avg_queue_length = 0.0
        total_samples = sum(len(m.queue_depth_samples) for m in self.machines)
        if total_samples:
            avg_queue_length = sum(sum(m.queue_depth_samples) for m in self.machines) / total_samples

        return {
            "sim_time_hours": round(self.env.now, 4),
            "jobs_generated": len(self.jobs),
            "jobs_completed": self._throughput,
            "policy": self.config.scheduling_policy.value,
            "throughput_jobs_per_hour": round(self._throughput / max(self.env.now, 1e-9), 4),
            "makespan_hours": round(makespan, 4),
            "utilization": round(utilization, 4),
            "downtime_hours": round(total_downtime, 4),
            "failures": total_failures,
            "preventive_maintenance": total_preventive,
            "avg_tardiness_hours": round(avg_tardiness, 4),
            "avg_queue_length": round(avg_queue_length, 4),
            "events_logged": len(self.event_log),
        }
