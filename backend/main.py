from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import simpy

from events import Event, EventBus, EventType
from layout import LayoutEdge, LayoutEditor, LayoutGraph, LayoutNode, LayoutNodeType, LayoutPosition
from mes import ManufacturingExecutionSystem
from ml import PredictionService
from simulation import Simulation
from data.persistence import PersistenceService
from services.maintenance_service import MaintenanceScheduler


def _build_industrial_balanced_baseline() -> LayoutGraph:
	nodes = []
	edges = []
	
	# Stage 1: Parallel Ingestion (5 Sources)
	for i in range(1, 6):
		y_off = (i-3)*160.0
		nodes.append(LayoutNode(id=f"src-{i}", type=LayoutNodeType.SOURCE, 
				 position=LayoutPosition(x=0.0, y=y_off),
				 properties={"interarrival_time": 1.0, "max_jobs": 0}))
		nodes.append(LayoutNode(id=f"buf-in-{i}", type=LayoutNodeType.BUFFER, 
				 position=LayoutPosition(x=120.0, y=y_off),
				 properties={"capacity": 50}))
		edges.append(LayoutEdge(from_node=f"src-{i}", to_node=f"buf-in-{i}"))

	# Stage 2: Pre-Processing (5 Machines)
	for i in range(1, 6):
		y_off = (i-3)*160.0
		nodes.append(LayoutNode(id=f"pre-{i}", type=LayoutNodeType.MACHINE, 
				 position=LayoutPosition(x=240.0, y=y_off),
				properties={
			"processing_time": 3.5, 
			"failure_probability": 0.0001,
			"wear_rate_time": 0.002,
			"wear_rate_usage": 0.005
		}
))
		edges.append(LayoutEdge(from_node=f"buf-in-{i}", to_node=f"pre-{i}"))

	# Stage 3: Intermediate Sorting (2 Dividers)
	nodes.append(LayoutNode(id="div-north", type=LayoutNodeType.DIVIDER, position=LayoutPosition(x=400.0, y=-200.0)))
	nodes.append(LayoutNode(id="div-south", type=LayoutNodeType.DIVIDER, position=LayoutPosition(x=400.0, y=200.0)))
	for i in range(1, 4):
		edges.append(LayoutEdge(from_node=f"pre-{i}", to_node="div-north"))
	for i in range(4, 6):
		edges.append(LayoutEdge(from_node=f"pre-{i}", to_node="div-south"))

	# Stage 4: Critical Assembly (8 Machines)
	for i in range(1, 9):
		y_off = (i-4.5)*110.0
		target_div = "div-north" if i <= 4 else "div-south"
		nodes.append(LayoutNode(id=f"asm-{i}", type=LayoutNodeType.MACHINE, 
				 position=LayoutPosition(x=600.0, y=y_off),
				properties={
			"processing_time": 1.2, 
			"failure_probability": 0.005,
			"wear_rate_time": 0.008,
			"wear_rate_usage": 0.02
		}
))
		nodes.append(LayoutNode(id=f"buf-asm-{i}", type=LayoutNodeType.BUFFER, 
				 position=LayoutPosition(x=500.0, y=y_off),
				 properties={"capacity": 30}))
		edges.append(LayoutEdge(from_node=target_div, to_node=f"buf-asm-{i}"))
		edges.append(LayoutEdge(from_node=f"buf-asm-{i}", to_node=f"asm-{i}"))

	# Stage 5: Quality Inspection (4 Machines)
	for i in range(1, 5):
		y_off = (i-2.5)*180.0
		nodes.append(LayoutNode(id=f"qc-{i}", type=LayoutNodeType.MACHINE, 
				 position=LayoutPosition(x=800.0, y=y_off),
				 properties={"processing_time": 5.0, "failure_rate": 0.02}))
		# Connect 2 assembly machines to each QC machine
		edges.append(LayoutEdge(from_node=f"asm-{(i*2)-1}", to_node=f"qc-{i}"))
		edges.append(LayoutEdge(from_node=f"asm-{i*2}", to_node=f"qc-{i}"))

	# Stage 6: Shipping
	nodes.append(LayoutNode(id="ship-sink", type=LayoutNodeType.SINK, position=LayoutPosition(x=1000.0, y=0.0)))
	for i in range(1, 5):
		edges.append(LayoutEdge(from_node=f"qc-{i}", to_node="ship-sink"))

	return LayoutGraph(nodes=nodes, edges=edges)


def _build_industrial_bottleneck_stress() -> LayoutGraph:
	nodes = []
	edges = []
	
	# High-Volume Ingestion (8 Sources)
	for i in range(1, 9):
		y_off = (i-4.5)*100.0
		nodes.append(LayoutNode(id=f"src-fast-{i}", type=LayoutNodeType.SOURCE, 
				 position=LayoutPosition(x=0.0, y=y_off),
				 properties={"interarrival_time": 0.4, "max_jobs": 0}))
		nodes.append(LayoutNode(id=f"buf-fast-{i}", type=LayoutNodeType.BUFFER, 
				 position=LayoutPosition(x=120.0, y=y_off),
				 properties={"capacity": 100}))
		edges.append(LayoutEdge(from_node=f"src-fast-{i}", to_node=f"buf-fast-{i}"))

	# Intermediate Processing Layer (4 Machines)
	for i in range(1, 5):
		y_off = (i-2.5)*180.0
		nodes.append(LayoutNode(id=f"inter-proc-{i}", type=LayoutNodeType.MACHINE, 
				 position=LayoutPosition(x=280.0, y=y_off),
				 properties={"processing_time": 2.0, "failure_rate": 0.01}))
		# Connect 2 sources to each intermediate machine
		edges.append(LayoutEdge(from_node=f"buf-fast-{(i*2)-1}", to_node=f"inter-proc-{i}"))
		edges.append(LayoutEdge(from_node=f"buf-fast-{i*2}", to_node=f"inter-proc-{i}"))

	# Converge to the Master Bottleneck
	nodes.append(LayoutNode(id="converge-divider", type=LayoutNodeType.DIVIDER, position=LayoutPosition(x=450.0, y=0.0)))
	for i in range(1, 5):
		edges.append(LayoutEdge(from_node=f"inter-proc-{i}", to_node="converge-divider"))

	# The Slow Master Machine
	nodes.append(LayoutNode(id="master-bottleneck", type=LayoutNodeType.MACHINE, 
			 position=LayoutPosition(x=650.0, y=0.0),
			 properties={"processing_time": 15.0, "failure_rate": 0.02}))
	nodes.append(LayoutNode(id="massive-buffer", type=LayoutNodeType.BUFFER, 
			 position=LayoutPosition(x=550.0, y=0.0),
			 properties={"capacity": 500}))
	
	edges.append(LayoutEdge(from_node="converge-divider", to_node="massive-buffer"))
	edges.append(LayoutEdge(from_node="massive-buffer", to_node="master-bottleneck"))
	
	nodes.append(LayoutNode(id="final-sink", type=LayoutNodeType.SINK, position=LayoutPosition(x=800.0, y=0.0)))
	edges.append(LayoutEdge(from_node="master-bottleneck", to_node="final-sink"))
	
	return LayoutGraph(nodes=nodes, edges=edges)


def _build_industrial_failure_prone() -> LayoutGraph:
	# A 4x4 grid of machines with varying reliability
	nodes = []
	edges = []
	
	nodes.append(LayoutNode(id="grid-src", type=LayoutNodeType.SOURCE, position=LayoutPosition(x=0.0, y=0.0)))
	nodes.append(LayoutNode(id="grid-entry-div", type=LayoutNodeType.DIVIDER, position=LayoutPosition(x=100.0, y=0.0)))
	edges.append(LayoutEdge(from_node="grid-src", to_node="grid-entry-div"))

	# 4 Entry Buffers
	for j in range(4):
		y_off = (j-1.5)*200.0
		nodes.append(LayoutNode(id=f"grid-buf-start-{j}", type=LayoutNodeType.BUFFER, position=LayoutPosition(x=200.0, y=y_off)))
		edges.append(LayoutEdge(from_node="grid-entry-div", to_node=f"grid-buf-start-{j}"))

	# 4x4 Grid
	for i in range(4): # Columns
		for j in range(4): # Rows
			node_id = f"grid-m-{i}-{j}"
			x_pos = 350.0 + (i * 200.0)
			y_pos = (j - 1.5) * 200.0
			
			# High failure rate for center machines
			fail_rate = 0.3 if (1 <= i <= 2 and 1 <= j <= 2) else 0.01
			
			nodes.append(LayoutNode(id=node_id, type=LayoutNodeType.MACHINE, 
					 position=LayoutPosition(x=x_pos, y=y_pos),
					 properties={"processing_time": 5.0, "failure_rate": fail_rate}))
			
			if i == 0:
				edges.append(LayoutEdge(from_node=f"grid-buf-start-{j}", to_node=node_id))
			else:
				# Connect to machine in previous column, same row
				edges.append(LayoutEdge(from_node=f"grid-m-{i-1}-{j}", to_node=node_id))

	nodes.append(LayoutNode(id="grid-exit-sink", type=LayoutNodeType.SINK, position=LayoutPosition(x=1200.0, y=0.0)))
	for j in range(4):
		edges.append(LayoutEdge(from_node=f"grid-m-3-{j}", to_node="grid-exit-sink"))
	
	return LayoutGraph(nodes=nodes, edges=edges)
	

def _build_industrial_dynamic_routing() -> LayoutGraph:
	nodes = []
	edges = []
	
	# Entry
	nodes.append(LayoutNode(id="src-in", type=LayoutNodeType.SOURCE, position=LayoutPosition(x=0.0, y=0.0), properties={"interarrival_time": 0.6}))
	nodes.append(LayoutNode(id="buf-in", type=LayoutNodeType.BUFFER, position=LayoutPosition(x=120.0, y=0.0), properties={"capacity": 50}))
	edges.append(LayoutEdge(from_node="src-in", to_node="buf-in"))
	
	# Smart Diverter
	nodes.append(LayoutNode(id="div-smart", type=LayoutNodeType.DIVIDER, position=LayoutPosition(x=250.0, y=0.0), 
				 properties={"routing_rule": "weighted_cost", "minimum_health": 0.5, "health_based_toggle": True}))
	edges.append(LayoutEdge(from_node="buf-in", to_node="div-smart"))

	# Path A: High Speed (Fragile)
	nodes.append(LayoutNode(id="buf-path-a", type=LayoutNodeType.BUFFER, position=LayoutPosition(x=400.0, y=-150.0), properties={"capacity": 40}))
	nodes.append(LayoutNode(id="m-fast", type=LayoutNodeType.MACHINE, position=LayoutPosition(x=550.0, y=-150.0), 
				properties={
			"processing_time": 10.0, 
			"failure_rate": 0.02, 
			"repair_time": 15.0,
			"wear_rate_time": 0.005,
			"wear_rate_usage": 0.015
		}
))
	edges.append(LayoutEdge(from_node="div-smart", to_node="buf-path-a"))
	edges.append(LayoutEdge(from_node="buf-path-a", to_node="m-fast"))

	# Path B: Low Speed (Robust)
	nodes.append(LayoutNode(id="buf-path-b", type=LayoutNodeType.BUFFER, position=LayoutPosition(x=400.0, y=150.0), properties={"capacity": 80}))
	nodes.append(LayoutNode(id="m-robust", type=LayoutNodeType.MACHINE, position=LayoutPosition(x=550.0, y=150.0), 
				 properties={"processing_time": 6.0, "failure_rate": 0.001, "wear_rate_usage": 0.001}))
	edges.append(LayoutEdge(from_node="div-smart", to_node="buf-path-b"))
	edges.append(LayoutEdge(from_node="buf-path-b", to_node="m-robust"))

	# Convergence to Sink
	nodes.append(LayoutNode(id="sink-out", type=LayoutNodeType.SINK, position=LayoutPosition(x=750.0, y=0.0)))
	edges.append(LayoutEdge(from_node="m-fast", to_node="sink-out"))
	edges.append(LayoutEdge(from_node="m-robust", to_node="sink-out"))

	return LayoutGraph(nodes=nodes, edges=edges)


def build_sample_layout_graph() -> LayoutGraph:
	return _build_industrial_balanced_baseline()


def _clone_graph(graph: LayoutGraph) -> LayoutGraph:
	return LayoutGraph.from_dict(graph.to_dict())


_SCENARIO_CATALOG: list[dict[str, Any]] = [
	{
		"scenario_id": "balanced_baseline",
		"name": "Balanced Baseline",
		"description": "Multi-stage assembly line (30+ nodes) with parallel tracks.",
		"focus": ["efficiency", "flow"],
		"showcase_config": {"zoom": 0.5, "center": [500, 0]}
	},
	{
		"scenario_id": "bottleneck_stress",
		"name": "Bottleneck Stress",
		"description": "High-volume ingestion stressing a central master machine.",
		"focus": ["congestion", "wip"],
		"showcase_config": {"zoom": 0.5, "center": [400, 0]}
	},
	{
		"scenario_id": "failure_prone",
		"name": "Failure Prone",
		"description": "Grid layout with elevated central failure rates.",
		"focus": ["reliability", "routing"],
		"showcase_config": {"zoom": 0.4, "center": [600, 0]}
	},
	{
		"scenario_id": "dynamic_routing",
		"name": "Dynamic Routing",
		"description": "Smart fail-over: Slower path vs Fragile path.",
		"focus": ["failover", "buffers"],
		"showcase_config": {"zoom": 0.6, "center": [400, 0]}
	}
]


class SmartFactoryDigitalTwinSystem:
	def __init__(self, event_bus: EventBus | None = None, *, bootstrap_layout: bool = True):
		self.environment = simpy.Environment()
		self.event_bus = event_bus or EventBus(self.environment)
		self.persistence = PersistenceService(self.event_bus)
		self.persistence.start()
		self.layout_editor = LayoutEditor(self.event_bus)
		self.mes: ManufacturingExecutionSystem | None = None
		self.simulation: Simulation | None = None
		self.maintenance: MaintenanceScheduler | None = None
		self.prediction: PredictionService | None = None
		
		# Load baseline by default unless the caller wants to subscribe first.
		if bootstrap_layout:
			self.bootstrap_sample_layout()

	def bootstrap_sample_layout(self) -> None:
		self.ingest_layout_graph_json(build_sample_layout_graph().to_json())

	def ingest_layout_graph_json(self, graph_json: str) -> None:
		"""Primary entry point for loading/reloading factory layouts."""
		graph = LayoutGraph.from_json(graph_json)
		self.layout_editor.update_layout(graph)
		
		# Re-initialize all dependent services
		self.mes = ManufacturingExecutionSystem(self.event_bus)
		self.simulation = Simulation.from_layout_graph(graph, environment=self.environment, event_bus=self.event_bus)
		self.maintenance = MaintenanceScheduler(self.event_bus)
		self.prediction = PredictionService(self.event_bus)
		
		# Broadcast change to frontend
		self.event_bus.publish(Event(
			event_type=EventType.LAYOUT_CHANGED, 
			timestamp=self.environment.now, 
			source="system", 
			payload={"nodes": len(graph.nodes), "edges": len(graph.edges)}
		))

	def load_scenario(self, scenario_id: str) -> dict[str, Any]:
		if scenario_id == "balanced_baseline":
			graph = _build_industrial_balanced_baseline()
		elif scenario_id == "bottleneck_stress":
			graph = _build_industrial_bottleneck_stress()
		elif scenario_id == "failure_prone":
			graph = _build_industrial_failure_prone()
		elif scenario_id == "dynamic_routing":
			graph = _build_industrial_dynamic_routing()
		else:
			raise ValueError(f"Unknown scenario_id: {scenario_id}")
			
		self.ingest_layout_graph_json(graph.to_json())
		return {
			"status": "scenario_loaded",
			"scenario": scenario_id,
			"nodes": len(graph.nodes),
			"edges": len(graph.edges)
		}

	def get_catalog(self) -> list[dict[str, Any]]:
		return _SCENARIO_CATALOG


def list_layout_scenarios() -> list[dict[str, Any]]:
	return _SCENARIO_CATALOG


def get_scenario_showcase_config(scenario_id: str) -> dict[str, Any]:
	for s in _SCENARIO_CATALOG:
		if s.get("scenario_id") == scenario_id:
			return s.get("showcase_config", {})
	return {}


def build_layout_graph_for_scenario(scenario_id: str) -> LayoutGraph:
	if scenario_id == "balanced_baseline":
		return _build_industrial_balanced_baseline()
	elif scenario_id == "bottleneck_stress":
		return _build_industrial_bottleneck_stress()
	elif scenario_id == "failure_prone":
		return _build_industrial_failure_prone()
	elif scenario_id == "dynamic_routing":
		return _build_industrial_dynamic_routing()
	raise ValueError(f"Unknown scenario_id: {scenario_id}")
