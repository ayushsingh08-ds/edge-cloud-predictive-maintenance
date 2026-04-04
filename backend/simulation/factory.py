from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import simpy

from events import Event, EventBus, EventType
from layout import LayoutEdge, LayoutGraph, LayoutNodeType

from .buffer import Buffer
from .job import Job
from .machine import Machine, MachineStatus


@dataclass(slots=True)
class Factory:
    environment: simpy.Environment
    event_bus: EventBus | None = None
    layout_graph: LayoutGraph | None = None
    machines: list[Machine] = field(default_factory=list)
    buffers: list[Buffer] = field(default_factory=list)
    layout_edges: list[LayoutEdge] = field(default_factory=list)
    node_registry: dict[str, object] = field(default_factory=dict)
    job_queue: Buffer | None = None

    @classmethod
    def from_layout_graph(
        cls,
        environment: simpy.Environment,
        layout_graph: LayoutGraph,
        event_bus: EventBus | None = None,
    ) -> "Factory":
        factory = cls(environment=environment, event_bus=event_bus, layout_graph=layout_graph)
        factory.layout_edges = list(layout_graph.edges)

        first_queue: Buffer | None = None
        for node in layout_graph.nodes:
            if node.type == LayoutNodeType.MACHINE:
                machine = Machine(
                    machine_id=node.id,
                    environment=environment,
                    event_bus=event_bus,
                    failure_rate=float(node.properties.get("failure_rate", 0.0)),
                    maintenance_duration=float(node.properties.get("maintenance_duration", 0.0)),
                )
                factory.add_machine(machine)
                factory.node_registry[node.id] = machine
                continue

            buffer_capacity = node.properties.get("buffer_capacity", node.properties.get("capacity"))
            buffer = Buffer(
                name=node.id,
                capacity=(int(buffer_capacity) if buffer_capacity is not None else None),
            )
            factory.add_buffer(buffer)
            factory.node_registry[node.id] = buffer
            if first_queue is None:
                first_queue = buffer
            if node.type == LayoutNodeType.SOURCE and factory.job_queue is None:
                factory.set_job_queue(buffer)

        if factory.job_queue is None:
            if first_queue is None:
                first_queue = Buffer(name="job_queue")
                factory.add_buffer(first_queue)
                factory.node_registry[first_queue.name] = first_queue
            factory.set_job_queue(first_queue)

        return factory

    def add_machine(self, machine: Machine) -> None:
        self.machines.append(machine)

    def add_buffer(self, buffer: Buffer) -> None:
        self.buffers.append(buffer)

    def set_job_queue(self, buffer: Buffer) -> None:
        self.job_queue = buffer

    def receive_job(self, job: Job) -> bool:
        if self.job_queue is None:
            raise RuntimeError("Factory job queue has not been configured")
        accepted = self.job_queue.put(job)
        if accepted and self.event_bus is not None:
            self.event_bus.publish(
                Event(
                    event_type=EventType.JOB_ARRIVAL,
                    timestamp=self.environment.now,
                    source="simulation.factory",
                    payload={"job_id": job.job_id, "priority": job.priority},
                )
            )
        return accepted

    def available_machine(self) -> Machine | None:
        for machine in self.machines:
            if machine.status == MachineStatus.IDLE:
                return machine
        return None

    def dispatch_jobs(self) -> simpy.events.Process | None:
        if self.job_queue is None:
            raise RuntimeError("Factory job queue has not been configured")
        return self.environment.process(self._dispatch_loop())

    def _dispatch_loop(self):
        while True:
            job = self.job_queue.peek()
            machine = self.available_machine()
            if job is None or machine is None:
                yield self.environment.timeout(1)
                continue

            job = self.job_queue.get()
            if job is None:
                continue

            machine.assign_job(job)
            self.environment.process(self._process_job(machine, job))
            yield self.environment.timeout(0)

    def _process_job(self, machine: Machine, job: Job):
        yield self.environment.timeout(job.processing_time)
        machine.release_job()
        if self.event_bus is not None:
            self.event_bus.publish(
                Event(
                    event_type=EventType.JOB_FINISH,
                    timestamp=self.environment.now,
                    source=f"machine.{machine.machine_id}",
                    payload={"job_id": job.job_id, "machine_id": machine.machine_id},
                )
            )

    def active_jobs(self) -> Iterable[Job]:
        for machine in self.machines:
            if machine.current_job is not None:
                yield machine.current_job

    def downstream_node_ids(self, node_id: str) -> list[str]:
        return [edge.to_node for edge in self.layout_edges if edge.from_node == node_id]
