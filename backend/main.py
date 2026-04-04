from __future__ import annotations

from dataclasses import dataclass, field

import simpy

from events import EventBus
from layout import LayoutEdge, LayoutEditor, LayoutGraph, LayoutNode, LayoutNodeType, LayoutPosition
from mes import ManufacturingExecutionSystem
from ml import PredictionService
from simulation import Simulation


def build_sample_layout_graph() -> LayoutGraph:
	return LayoutGraph(
		nodes=[
			LayoutNode(
				id="source-1",
				type=LayoutNodeType.SOURCE,
				position=LayoutPosition(x=0.0, y=0.0),
				properties={"interarrival_time": 1.0, "max_jobs": 12, "processing_time": 4.0},
			),
			LayoutNode(
				id="buffer-1",
				type=LayoutNodeType.BUFFER,
				position=LayoutPosition(x=120.0, y=0.0),
				properties={"capacity": 50},
			),
			LayoutNode(
				id="machine-1",
				type=LayoutNodeType.MACHINE,
				position=LayoutPosition(x=260.0, y=0.0),
				properties={
					"processing_time": 5.0,
					"failure_rate": 0.03,
					"repair_time": 2.0,
					"sensor_interval": 1.0,
					"load_factor": 0.65,
					"wear": 0.08,
				},
			),
			LayoutNode(
				id="conveyor-1",
				type=LayoutNodeType.CONVEYOR,
				position=LayoutPosition(x=340.0, y=0.0),
				properties={"transport_time": 0.5},
			),
			LayoutNode(
				id="divider-1",
				type=LayoutNodeType.DIVIDER,
				position=LayoutPosition(x=400.0, y=0.0),
				properties={"routing_rule": "round_robin"},
			),
			LayoutNode(
				id="buffer-2",
				type=LayoutNodeType.BUFFER,
				position=LayoutPosition(x=480.0, y=-40.0),
				properties={"capacity": 30},
			),
			LayoutNode(
				id="buffer-3",
				type=LayoutNodeType.BUFFER,
				position=LayoutPosition(x=480.0, y=40.0),
				properties={"capacity": 30},
			),
			LayoutNode(
				id="sink-1",
				type=LayoutNodeType.SINK,
				position=LayoutPosition(x=620.0, y=0.0),
				properties={},
			),
		],
		edges=[
			LayoutEdge(from_node="source-1", to_node="buffer-1"),
			LayoutEdge(from_node="buffer-1", to_node="machine-1", transport_time=1.0),
			LayoutEdge(from_node="machine-1", to_node="conveyor-1", transport_time=0.5),
			LayoutEdge(from_node="conveyor-1", to_node="divider-1"),
			LayoutEdge(from_node="divider-1", to_node="buffer-2", transport_time=0.2),
			LayoutEdge(from_node="divider-1", to_node="buffer-3", transport_time=0.4),
			LayoutEdge(from_node="buffer-2", to_node="sink-1"),
			LayoutEdge(from_node="buffer-3", to_node="sink-1"),
		],
	)


@dataclass(slots=True)
class SmartFactoryDigitalTwinSystem:
	environment: simpy.Environment = field(default_factory=simpy.Environment)
	event_bus: EventBus = field(init=False)
	layout_editor: LayoutEditor = field(init=False)
	mes: ManufacturingExecutionSystem = field(init=False)
	prediction_service: PredictionService = field(init=False)
	simulation: Simulation | None = field(default=None, init=False)

	def __post_init__(self) -> None:
		self.event_bus = EventBus(self.environment)
		self.layout_editor = LayoutEditor(event_bus=self.event_bus)
		self.mes = ManufacturingExecutionSystem(event_bus=self.event_bus)
		self.prediction_service = PredictionService(event_bus=self.event_bus)

	def ingest_layout_graph_json(self, layout_json: str) -> None:
		graph = LayoutGraph.from_json(layout_json)
		self.layout_editor.update_layout(graph)
		self.simulation = Simulation.from_layout_graph(
			graph,
			environment=self.environment,
			event_bus=self.event_bus,
		)

	def run(self, until: float) -> None:
		if self.simulation is None:
			raise RuntimeError("No layout ingested. Call ingest_layout_graph_json() first.")
		self.simulation.run(until=until)


def build_system() -> SmartFactoryDigitalTwinSystem:
	system = SmartFactoryDigitalTwinSystem()
	layout_graph = build_sample_layout_graph()
	system.ingest_layout_graph_json(layout_graph.to_json())
	return system


def main() -> None:
	system = build_system()
	system.run(until=20)


if __name__ == "__main__":
	main()
