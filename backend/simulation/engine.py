from __future__ import annotations

import logging
import random
from threading import RLock
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

import simpy

from events import Event, EventBus, EventType
from layout import LayoutEdge, LayoutGraph, LayoutNode, LayoutNodeType
from routing import RoutingEngine

from .buffer import Buffer
from .job import Job
from .machine import Machine, MachineStatus


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class FactorySimulationEngine:
    layout_graph: LayoutGraph
    environment: simpy.Environment
    event_bus: EventBus
    random_seed: int = 42
    completed_jobs: list[Job] = field(default_factory=list)
    _rng: random.Random = field(init=False)
    _incoming_stores: dict[str, simpy.Store] = field(init=False, default_factory=dict)
    _outgoing_edges: dict[str, list[LayoutEdge]] = field(init=False, default_factory=dict)
    _node_by_id: dict[str, LayoutNode] = field(init=False, default_factory=dict)
    _divider_round_robin_index: dict[str, int] = field(init=False, default_factory=dict)
    _buffers: dict[str, Buffer] = field(init=False, default_factory=dict)
    _machines: dict[str, Machine] = field(init=False, default_factory=dict)
    _routing_engine: RoutingEngine = field(init=False)
    _maintenance_in_progress: set[str] = field(init=False, default_factory=set)
    _buffer_pressure_high: dict[str, bool] = field(init=False, default_factory=dict)
    _lock: RLock = field(init=False, default_factory=RLock)
    _maintenance_scheduler_provider: Callable[[str], float | None] | None = field(init=False, default=None)
    _green_score_evaluator: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = field(init=False, default=None)
    _started: bool = field(init=False, default=False)
    _sim_start_time: float = field(init=False, default=0.0)
    _jobs_completed_count: int = field(init=False, default=0)

    @classmethod
    def from_layout(cls, graph: LayoutGraph, environment: simpy.Environment, event_bus: EventBus) -> "FactorySimulationEngine":
        return cls(layout_graph=graph, environment=environment, event_bus=event_bus)

    @classmethod
    def from_layout_json(cls, json_text: str, environment: simpy.Environment, event_bus: EventBus) -> "FactorySimulationEngine":
        graph = LayoutGraph.from_json(json_text)
        return cls.from_layout(graph, environment, event_bus)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.random_seed)
        self._incoming_stores = {}
        self._outgoing_edges = {node.id: [] for node in self.layout_graph.nodes}
        self._node_by_id = {node.id: node for node in self.layout_graph.nodes}
        self._divider_round_robin_index = {}
        self._buffers = {}
        self._machines = {}
        self._routing_engine = RoutingEngine(event_bus=self.event_bus)
        self._maintenance_in_progress = set()
        self._buffer_pressure_high = {}
        self._lock = RLock()
        self._maintenance_scheduler_provider = None
        self._started = False

        for edge in self.layout_graph.edges:
            if edge.from_node not in self._node_by_id or edge.to_node not in self._node_by_id:
                raise ValueError(f"Invalid edge {edge.from_node} -> {edge.to_node}: node not found")
            self._outgoing_edges[edge.from_node].append(edge)

        for node in self.layout_graph.nodes:
            if node.type != LayoutNodeType.SOURCE:
                capacity = node.properties.get("queue_capacity")
                if capacity is None and node.type == LayoutNodeType.BUFFER:
                    capacity = node.properties.get("buffer_capacity", node.properties.get("capacity"))
                if capacity is None and node.type == LayoutNodeType.MACHINE:
                    capacity = 1
                max_capacity = _as_int(capacity, 0)
                if max_capacity <= 0:
                    self._incoming_stores[node.id] = simpy.Store(self.environment)
                else:
                    self._incoming_stores[node.id] = simpy.Store(self.environment, capacity=max_capacity)

            if node.type == LayoutNodeType.BUFFER:
                self._buffers[node.id] = Buffer(
                    name=node.id,
                    capacity=_as_int(node.properties.get("buffer_capacity", node.properties.get("capacity")), 0) or None,
                )

            if node.type == LayoutNodeType.MACHINE:
                self._machines[node.id] = Machine(
                    machine_id=node.id,
                    environment=self.environment,
                    event_bus=self.event_bus,
                    processing_time=_as_float(node.properties.get("processing_time", 1.0), 1.0),
                    health=_as_float(node.properties.get("health", 1.0), 1.0),
                    wear=_as_float(node.properties.get("wear", 0.0), 0.0),
                    load_factor=_as_float(node.properties.get("load_factor", 0.5), 0.5),
                    wear_rate_time=_as_float(node.properties.get("wear_rate_time", 0.0008), 0.0008),
                    wear_rate_usage=_as_float(node.properties.get("wear_rate_usage", 0.003), 0.003),
                    failure_probability=_as_float(node.properties.get("failure_probability", 0.0), 0.0),
                    failure_rate=_as_float(node.properties.get("failure_rate", 0.0), 0.0),
                    sensor_interval=_as_float(node.properties.get("sensor_interval", 1.0), 1.0),
                    maintenance_duration=_as_float(
                        node.properties.get("maintenance_duration", node.properties.get("repair_time", 5.0)),
                        5.0,
                    ),
                )

        self._routing_engine.configure_context(
            machine_provider=self._machine_snapshot,
            queue_provider=self._queue_length,
            node_type_provider=self._node_type,
            green_score_provider=self._green_score_evaluator,
        )
        self.event_bus.subscribe(EventType.MAINTENANCE_TRIGGER, self._handle_maintenance_trigger)

    def configure_maintenance_scheduler(self, provider: Callable[[str], float | None]):
        self._maintenance_scheduler_provider = provider

    def configure_green_evaluator(self, evaluator: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]):
        self._green_score_evaluator = evaluator
        self._routing_engine.configure_context(
            machine_provider=self._machine_snapshot,
            queue_provider=self._queue_length,
            node_type_provider=self._node_type,
            green_score_provider=self._green_score_evaluator,
        )

    @classmethod
    def from_layout_json(
        cls,
        layout_json: str,
        environment: simpy.Environment | None = None,
        event_bus: EventBus | None = None,
        random_seed: int = 42,
    ) -> "FactorySimulationEngine":
        graph = LayoutGraph.from_json(layout_json)
        environment = environment or simpy.Environment()
        event_bus = event_bus or EventBus(environment)
        return cls(layout_graph=graph, environment=environment, event_bus=event_bus, random_seed=random_seed)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.event_bus.publish(
            Event(
                event_type=EventType.LAYOUT_CHANGED,
                timestamp=self.environment.now,
                source="simulation.engine",
                payload={"graph": self.layout_graph.to_dict()},
            )
        )

        for node in self.layout_graph.nodes:
            if node.type == LayoutNodeType.SOURCE:
                self.environment.process(self._run_source(node))
            elif node.type == LayoutNodeType.BUFFER:
                self.environment.process(self._run_buffer(node))
            elif node.type == LayoutNodeType.MACHINE:
                self.environment.process(self._run_machine(node))
                self.environment.process(self._run_machine_failure_monitor(node))
                self._machines[node.id].start_sensor_stream()
            elif node.type == LayoutNodeType.DIVIDER:
                self.environment.process(self._run_divider(node))
            elif node.type == LayoutNodeType.CONVEYOR:
                self.environment.process(self._run_conveyor(node))
            elif node.type == LayoutNodeType.SINK:
                self.environment.process(self._run_sink(node.id))
        # Set simulation start time and trigger metrics loop
        self._sim_start_time = self.environment.now
        self.environment.process(self._run_metrics_updater())

    def capture_state(self) -> dict[str, Any]:
        """Captures the absolute state of the factory for cloning."""
        return {
            "now": self.environment.now,
            "machines": {
                m_id: {
                    "health": m.health,
                    "wear": m.wear,
                    "status": m.status.value,
                    "load": m.load_factor,
                    "operating_time": m.operating_time,
                }
                for m_id, m in self._machines.items()
            },
            "queues": {
                node_id: [job.job_id for job in list(getattr(store, "items", []))]
                for node_id, store in self._incoming_stores.items()
            },
            "layout": self.layout_graph.to_dict(),
        }

    def apply_scenario(self, scenario: dict[str, Any]):
        """Injects hypothetical changes into the simulation."""
        for action in scenario.get("actions", []):
            action_type = action.get("type")
            target = action.get("target")

            if action_type == "fail_machine":
                if target in self._machines:
                    self._machines[target].fail()
            
            elif action_type == "change_demand":
                for node in self.layout_graph.nodes:
                    if node.type == LayoutNodeType.SOURCE:
                        node.properties["interarrival_time"] = action.get("value", 1.0)
            
            elif action_type == "speed_up":
                if target in self._machines:
                    self._machines[target].processing_time *= action.get("multiplier", 0.5)

    def run(self, until: float) -> None:
        self.start()
        self.environment.run(until=until)

    def _run_source(self, node: LayoutNode):
        interarrival = _as_float(node.properties.get("interarrival_time", 1.0), 1.0)
        max_jobs = _as_int(node.properties.get("max_jobs", 0), 0)
        base_processing_time = _as_float(node.properties.get("processing_time", 1.0), 1.0)
        priority = _as_int(node.properties.get("priority", 0), 0)
        operations = [str(op) for op in node.properties.get("operations", ["op-1"])]
        operation_processing_times = {
            str(name): _as_float(value, base_processing_time)
            for name, value in dict(node.properties.get("operation_processing_times", {})).items()
        }
        due_date_offset = _as_float(node.properties.get("due_date_offset", 50.0), 50.0)

        emitted = 0
        while max_jobs <= 0 or emitted < max_jobs:
            yield self.environment.timeout(interarrival)
            emitted += 1
            job = Job(
                job_id=f"{node.id}-J{emitted}",
                arrival_time=self.environment.now,
                processing_time=base_processing_time,
                operations=list(operations),
                due_date=self.environment.now + due_date_offset,
                priority=priority,
                operation_processing_times=dict(operation_processing_times),
                attributes={"source": node.id},
            )
            self.event_bus.publish(
                Event(
                    event_type=EventType.JOB_ARRIVAL,
                    timestamp=self.environment.now,
                    source=f"source.{node.id}",
                    payload={"job_id": job.job_id, "source": node.id},
                )
            )
            yield self.environment.process(self._forward_default(node.id, job))

    def _run_buffer(self, node: LayoutNode):
        store = self._incoming_stores[node.id]
        runtime_buffer = self._buffers[node.id]
        while True:
            job = yield store.get()
            if not runtime_buffer.put(job):
                yield self.environment.timeout(0.1)
                yield store.put(job)
                self._update_buffer_pressure(node.id)
                continue

            self._update_buffer_pressure(node.id)

            while len(runtime_buffer) > 0:
                available_edge = self._first_available_edge(node.id)
                if available_edge is None:
                    # Structured retry to prevent deadlock if state-change events are missed
                    yield self.environment.timeout(0.2)
                    self._update_buffer_pressure(node.id)
                    continue

                # Once an edge is guaranteed, we pop and deliver
                next_job = runtime_buffer.get()
                if next_job is not None:
                    yield self.environment.process(self._transport_and_deliver(available_edge, next_job))
                    self._update_buffer_pressure(node.id)
                else:
                    yield self.environment.timeout(0.1)
                    continue

    def _run_machine(self, node: LayoutNode):
        machine = self._machines[node.id]
        store = self._incoming_stores[node.id]

        while True:
            job = yield store.get()

            if machine.status == MachineStatus.IDLE and self._should_enter_jit_maintenance(machine, store, job):
                yield self.environment.process(machine.start_maintenance())

            while machine.status in {MachineStatus.FAILED, MachineStatus.MAINTENANCE}:
                yield self.environment.timeout(0.2)

            yield self.environment.process(machine.process_job(job))
            yield self.environment.process(self._forward_default(node.id, job))

    def _run_machine_failure_monitor(self, node: LayoutNode):
        machine = self._machines[node.id]
        failure_rate = machine.failure_rate
        repair_time = machine.maintenance_duration
        if failure_rate <= 0:
            return

        while True:
            yield self.environment.timeout(self._rng.expovariate(failure_rate))
            if machine.status != MachineStatus.IDLE:
                continue
            if not machine.should_fail_now():
                continue

            machine.fail()

            yield self.environment.timeout(repair_time)

            machine.repair()

    def _run_divider(self, node: LayoutNode):
        store = self._incoming_stores[node.id]
        while True:
            job = yield store.get()
            edges = self._outgoing_edges.get(node.id, [])
            if not edges:
                continue

            request_id = str(uuid4())
            self.event_bus.publish(
                Event(
                    event_type=EventType.ROUTING_REQUEST,
                    timestamp=self.environment.now,
                    source=f"divider.{node.id}",
                    payload={
                        "request_id": request_id,
                        "divider_id": node.id,
                        "job_id": job.job_id,
                        "operation": job.current_operation(),
                        "priority": job.priority,
                        "due_date": job.due_date,
                        "processing_time": job.processing_time_for_current_operation(),
                        "minimum_health": float(node.properties.get("minimum_health", 0.4)),
                        "candidates": [
                            {
                                "from_node": edge.from_node,
                                "to_node": edge.to_node,
                                "transport_time": edge.transport_time if edge.transport_time is not None else 0.0,
                            }
                            for edge in edges
                        ],
                    },
                )
            )
            yield self.environment.timeout(0)

            selected_to = self._routing_engine.pop_decision(request_id)
            selected = None
            if selected_to is not None:
                for edge in edges:
                    if edge.to_node == selected_to:
                        selected = edge
                        break
            if selected is None:
                selected = self._select_divider_edge(node, job, edges)

            self.event_bus.publish(
                Event(
                    event_type=EventType.ROUTING_DECISION,
                    timestamp=self.environment.now,
                    source=f"divider.{node.id}",
                    payload={
                        "job_id": job.job_id,
                        "from": node.id,
                        "to": selected.to_node,
                        "routing_policy": self._routing_engine.routing_policy,
                        "selection_reason": "weighted_cost_router",
                    },
                )
            )
            yield self.environment.process(self._transport_and_deliver(selected, job))

    def _run_conveyor(self, node: LayoutNode):
        store = self._incoming_stores[node.id]
        conveyor_time = _as_float(node.properties.get("transport_time", 0.0), 0.0)
        while True:
            job = yield store.get()
            if conveyor_time > 0:
                yield self.environment.timeout(conveyor_time)
            yield self.environment.process(self._forward_default(node.id, job))

    def _run_sink(self, node_id: str):
        store = self._incoming_stores[node_id]
        while True:
            job = yield store.get()
            self._update_buffer_pressure(node_id)
            self.event_bus.publish(
                Event(
                    event_type=EventType.JOB_COMPLETED,
                    timestamp=self.environment.now,
                    source=f"sink.{node_id}",
                    payload={"job_id": job.job_id, "sink_id": node_id},
                )
            )
            yield self.environment.timeout(0.1)
            self._jobs_completed_count += 1
            self.completed_jobs.append(job)
            
            # Periodically log throughput
            if self._jobs_completed_count % 10 == 0:
                metrics = self.get_throughput_metrics()
                logging.info(f"Simulation Throughput: {metrics['throughput']:.2f} jobs/time-unit")

    def get_throughput_metrics(self) -> dict[str, Any]:
        elapsed = max(0.001, self.environment.now - self._sim_start_time)
        throughput = self._jobs_completed_count / elapsed
        return {
            "completed_jobs": self._jobs_completed_count,
            "elapsed_time": round(elapsed, 2),
            "throughput": round(throughput, 4),
            "pdm_active": self._routing_engine.routing_policy == "pdm_rul"
        }

    def _forward_default(self, node_id: str, job: Job):
        edges = self._outgoing_edges.get(node_id, [])
        if not edges:
            return
        yield self.environment.process(self._transport_and_deliver(edges[0], job))

    def _transport_and_deliver(self, edge: LayoutEdge, job: Job):
        if edge.transport_time is not None and edge.transport_time > 0:
            self.event_bus.publish(
                Event(
                    event_type=EventType.JOB_TRANSFER,
                    timestamp=self.environment.now,
                    source="simulation.engine",
                    payload={
                        "job_id": job.job_id,
                        "from_node": edge.from_node,
                        "to_node": edge.to_node,
                        "duration": edge.transport_time,
                        "state": "moving"
                    }
                )
            )
            yield self.environment.timeout(edge.transport_time)

        target_store = self._incoming_stores.get(edge.to_node)
        if target_store is None:
            return

        yield target_store.put(job)
        
        # Immediate notification of arrival at target
        self.event_bus.publish(
            Event(
                event_type=EventType.JOB_TRANSFER,
                timestamp=self.environment.now,
                source="simulation.engine",
                payload={
                    "job_id": job.job_id,
                    "from_node": edge.from_node,
                    "to_node": edge.to_node,
                    "state": "delivered"
                }
            )
        )
        if edge.to_node in self._buffers:
            self._update_buffer_pressure(edge.to_node)

    def _first_available_edge(self, node_id: str) -> LayoutEdge | None:
        for edge in self._outgoing_edges.get(node_id, []):
            if self._can_deliver_to(edge.to_node):
                return edge
        return None

    def _can_deliver_to(self, node_id: str) -> bool:
        store = self._incoming_stores.get(node_id)
        if store is None:
            return False
        capacity = getattr(store, "capacity", None)
        if capacity in (None, float("inf")):
            return True
        return len(getattr(store, "items", [])) < int(capacity)

    def _queue_length(self, node_id: str) -> int:
        count = 0
        store = self._incoming_stores.get(node_id)
        if store is not None:
            count += len(getattr(store, "items", []))
        runtime_buffer = self._buffers.get(node_id)
        if runtime_buffer is not None:
            count += len(runtime_buffer)
        return count

    def _node_type(self, node_id: str) -> str:
        node = self._node_by_id.get(node_id)
        return node.type.value if node is not None else "Unknown"

    def _machine_snapshot(self, machine_id: str) -> dict[str, Any]:
        machine = self._machines.get(machine_id)
        if machine is None:
            return {
                "available": False,
                "health": 0.0,
                "predicted_health": 0.0,
                "predicted_rul": None,
                "processing_time": 1.0,
                "capabilities": [],
            }

        node = self._node_by_id.get(machine_id)
        capabilities = []
        if node is not None:
            capabilities = [str(item) for item in node.properties.get("capabilities", [])]

        return {
            "available": machine.status == MachineStatus.IDLE,
            "health": machine.health,
            "predicted_health": machine.predicted_health_score if machine.predicted_health_score is not None else machine.health,
            "predicted_rul": machine.predicted_rul_hours,
            "wear": machine.wear,
            "load_factor": machine.load_factor,
            "failure_probability": machine.failure_probability,
            "processing_time": machine.processing_time,
            "congestion_risk": machine.calculate_congestion_risk(),
            "scheduled_maintenance": self._maintenance_scheduler_provider(machine_id) if self._maintenance_scheduler_provider else None,
            "capabilities": capabilities,
        }

    def _select_divider_edge(self, node: LayoutNode, job: Job, edges: list[LayoutEdge]) -> LayoutEdge:
        del job
        rule = str(node.properties.get("routing_rule", "round_robin")).lower()
        if rule == "random":
            return self._rng.choice(edges)
        if rule == "lowest_transport_time":
            return min(edges, key=lambda edge: edge.transport_time if edge.transport_time is not None else 0.0)

        index = self._divider_round_robin_index.get(node.id, 0)
        selected = edges[index % len(edges)]
        self._divider_round_robin_index[node.id] = index + 1
        return selected

    def _handle_maintenance_trigger(self, event: Event):
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        machine = self._machines.get(machine_id)
        if machine is None:
            return
        if machine_id in self._maintenance_in_progress:
            return
        self._maintenance_in_progress.add(machine_id)
        return self.environment.process(self._run_maintenance(machine))

    def _should_enter_jit_maintenance(self, machine: Machine, store: simpy.Store, job: Job) -> bool:
        predicted_rul = machine.predicted_rul_hours
        if predicted_rul is None:
            return False
        if machine.status != MachineStatus.IDLE:
            return False

        pending_jobs = list(getattr(store, "items", []))
        if job not in pending_jobs:
            pending_jobs.insert(0, job)

        next_batch_time = sum(
            float(next_job.processing_time_for_current_operation())
            for next_job in pending_jobs[: max(1, min(len(pending_jobs), 3))]
        )
        if next_batch_time <= 0:
            return False
        return float(predicted_rul) < next_batch_time

    def _update_buffer_pressure(self, buffer_id: str) -> None:
        buffer = self._buffers.get(buffer_id)
        store = self._incoming_stores.get(buffer_id)
        if buffer is None or store is None:
            return

        capacity = buffer.capacity or getattr(store, "capacity", None)
        if not capacity or capacity in (None, float("inf")):
            return

        occupancy = len(buffer) / float(capacity)
        was_high = self._buffer_pressure_high.get(buffer_id, False)

        if occupancy >= 0.9 and not was_high:
            self._buffer_pressure_high[buffer_id] = True
            self.event_bus.publish(
                Event(
                    event_type=EventType.HIGH_PRESSURE,
                    timestamp=self.environment.now,
                    source=f"buffer.{buffer_id}",
                    payload={
                        "node_id": buffer_id,
                        "pressure": round(occupancy, 4),
                        "capacity": capacity,
                        "queue_length": len(buffer),
                        "state": "HIGH",
                    },
                )
            )
        elif occupancy <= 0.5 and was_high:
            self._buffer_pressure_high[buffer_id] = False
            self.event_bus.publish(
                Event(
                    event_type=EventType.LOW_PRESSURE,
                    timestamp=self.environment.now,
                    source=f"buffer.{buffer_id}",
                    payload={
                        "node_id": buffer_id,
                        "pressure": round(occupancy, 4),
                        "capacity": capacity,
                        "queue_length": len(buffer),
                        "state": "CLEAR",
                    },
                )
            )

    def _run_maintenance(self, machine: Machine):
        while machine.status == MachineStatus.BUSY:
            yield self.environment.timeout(0.1)

        machine.status = MachineStatus.MAINTENANCE
        yield self.environment.timeout(machine.maintenance_duration)
        machine.repair()
        self._maintenance_in_progress.discard(machine.machine_id)

    def _run_metrics_updater(self, interval: float = 1.0):
        """Periodically injects simulation-derived metrics into machine sensor data."""
        while True:
            routing_load = float(self._routing_engine.pending_count())
            
            for m_id, machine in self._machines.items():
                # 1. Queue Length (Incoming store + internal buffer)
                q_len = float(self._queue_length(m_id))
                
                # 2. Machine Utilization (%)
                # Handle edge case where operating_time is 0
                if machine.operating_time > 0:
                    machine.utilization = round(float(machine.total_busy_time / machine.operating_time), 4)
                else:
                    machine.utilization = 0.0
                
                # 3. Inject into machine's dynamic metrics
                machine.dynamic_metrics.update({
                    "queue_length": round(q_len, 2),
                    "routing_load": round(routing_load, 2),
                })
                
            yield self.environment.timeout(interval)
