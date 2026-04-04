from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from events import Event, EventType
from layout import LayoutEdge, LayoutGraph, LayoutNode, LayoutNodeType
from main import SmartFactoryDigitalTwinSystem, build_sample_layout_graph


def _event_to_dict(event: Event) -> dict[str, Any]:
	return {
		"event_id": event.event_id,
		"event_type": event.event_type.value,
		"timestamp": event.timestamp,
		"source": event.source,
		"payload": event.payload,
	}


def _safe_float(value: Any, default: float) -> float:
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _safe_int(value: Any, default: int) -> int:
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def _normalize_node(node: LayoutNode) -> LayoutNode:
	props = dict(node.properties)

	if node.type == LayoutNodeType.MACHINE:
		props["maintenance_threshold"] = _safe_float(props.get("maintenance_threshold", 0.35), 0.35)
		props["load_factor"] = _safe_float(props.get("load_factor", 0.5), 0.5)
		props["wear_rate_time"] = _safe_float(props.get("wear_rate_time", 0.0008), 0.0008)
		props["wear_rate_usage"] = _safe_float(props.get("wear_rate_usage", 0.003), 0.003)
		props["failure_probability"] = _safe_float(props.get("failure_probability", 0.0), 0.0)
		props["failure_rate"] = _safe_float(props.get("failure_rate", 0.0), 0.0)
		props["sensor_interval"] = _safe_float(props.get("sensor_interval", 1.0), 1.0)
		props["maintenance_duration"] = _safe_float(
			props.get("maintenance_duration", props.get("repair_time", 5.0)),
			5.0,
		)

	elif node.type == LayoutNodeType.BUFFER:
		capacity = props.get("queue_limit", props.get("capacity", props.get("buffer_capacity", 30)))
		props["queue_limit"] = _safe_int(capacity, 30)
		props["capacity"] = props["queue_limit"]
		props["buffer_capacity"] = props["queue_limit"]
		props["fill_percentage"] = _safe_float(props.get("fill_percentage", 0.0), 0.0)

	elif node.type == LayoutNodeType.CONVEYOR:
		props["speed"] = _safe_float(props.get("speed", 1.0), 1.0)
		props["capacity"] = _safe_int(props.get("capacity", 1), 1)
		props["transport_time"] = _safe_float(props.get("transport_time", 0.5), 0.5)

	elif node.type == LayoutNodeType.DIVIDER:
		props["routing_priority"] = _safe_int(props.get("routing_priority", 1), 1)
		props["minimum_health"] = _safe_float(props.get("minimum_health", 0.4), 0.4)
		props["health_based_toggle"] = bool(props.get("health_based_toggle", True))
		props["routing_rule"] = str(props.get("routing_rule", "round_robin"))

	node.properties = props
	return node


def _normalize_edge(edge: LayoutEdge) -> LayoutEdge:
	props = dict(edge.properties)
	props["capacity"] = _safe_int(props.get("capacity", 1), 1)
	props["directionality"] = str(props.get("directionality", "forward"))
	edge.properties = props
	if edge.transport_time is not None:
		edge.transport_time = _safe_float(edge.transport_time, 0.0)
	return edge


def _component_catalog() -> list[dict[str, Any]]:
	return [
		{
			"type": "Machine",
			"defaults": {
				"processing_time": 5.0,
				"maintenance_threshold": 0.35,
				"load_factor": 0.5,
				"wear_rate_time": 0.0008,
				"wear_rate_usage": 0.003,
				"failure_probability": 0.0,
				"failure_rate": 0.01,
				"sensor_interval": 1.0,
				"maintenance_duration": 5.0,
			},
		},
		{
			"type": "Buffer",
			"defaults": {
				"queue_limit": 30,
				"fill_percentage": 0.0,
			},
		},
		{
			"type": "Conveyor",
			"defaults": {
				"speed": 1.0,
				"capacity": 1,
				"transport_time": 0.5,
			},
		},
		{
			"type": "Divider",
			"defaults": {
				"routing_rule": "round_robin",
				"routing_priority": 1,
				"minimum_health": 0.4,
				"health_based_toggle": True,
			},
		},
		{
			"type": "Source",
			"defaults": {
				"interarrival_time": 1.0,
				"max_jobs": 0,
				"processing_time": 4.0,
			},
		},
		{
			"type": "Sink",
			"defaults": {},
		},
	]


@dataclass(slots=True)
class EventRelay:
	max_events: int = 5000
	_events: deque[dict[str, Any]] = field(default_factory=deque, init=False)
	_lock: RLock = field(default_factory=RLock, init=False)
	_sequence: int = field(default=0, init=False)

	def publish(self, event: Event) -> None:
		item = _event_to_dict(event)
		with self._lock:
			self._sequence += 1
			item["seq"] = self._sequence
			self._events.append(item)
			while len(self._events) > self.max_events:
				self._events.popleft()

	def snapshot(self, limit: int = 200) -> list[dict[str, Any]]:
		with self._lock:
			if limit <= 0:
				return []
			return list(self._events)[-limit:]

	def since(self, last_seq: int, limit: int = 200) -> list[dict[str, Any]]:
		with self._lock:
			output = [item for item in self._events if int(item.get("seq", 0)) > last_seq]
			return output[:limit]

	def latest_seq(self) -> int:
		with self._lock:
			if not self._events:
				return 0
			return int(self._events[-1].get("seq", 0))


@dataclass(slots=True)
class DigitalTwinRuntime:
	relay: EventRelay
	system: SmartFactoryDigitalTwinSystem = field(init=False)
	_lock: RLock = field(default_factory=RLock, init=False)
	simulation_enabled: bool = field(default=True, init=False)
	speed_multiplier: float = field(default=1.0, init=False)

	def __post_init__(self) -> None:
		self.system = self._new_system()

	def _new_system(self) -> SmartFactoryDigitalTwinSystem:
		system = SmartFactoryDigitalTwinSystem()
		for event_type in EventType:
			system.event_bus.subscribe(event_type, self.relay.publish)
		return system

	def load_layout(self, graph: LayoutGraph) -> dict[str, Any]:
		normalized = self.validate_layout(graph)
		with self._lock:
			self.system = self._new_system()
			self.system.ingest_layout_graph_json(normalized.to_json(indent=None))
			return {
				"status": "layout_loaded",
				"nodes": len(normalized.nodes),
				"edges": len(normalized.edges),
				"simulation_ready": self.system.simulation is not None,
			}

	def validate_layout(self, graph: LayoutGraph) -> LayoutGraph:
		for node in graph.nodes:
			_normalize_node(node)
		for edge in graph.edges:
			_normalize_edge(edge)
		return graph

	def _graph_copy(self) -> LayoutGraph:
		return LayoutGraph.from_dict(self.system.layout_editor.graph.to_dict())

	def add_node(self, node: LayoutNode) -> dict[str, Any]:
		with self._lock:
			graph = self._graph_copy()
			if graph.node_by_id(node.id) is not None:
				raise ValueError(f"node '{node.id}' already exists")
			graph.nodes.append(_normalize_node(node))
			result = self.load_layout(graph)
			return {
				"status": "node_added",
				"node_id": node.id,
				"runtime_reinitialized": True,
				**result,
			}

	def update_node(self, node_id: str, patch: dict[str, Any]) -> dict[str, Any]:
		with self._lock:
			graph = self._graph_copy()
			node = graph.node_by_id(node_id)
			if node is None:
				raise ValueError(f"node '{node_id}' not found")

			if "position" in patch and isinstance(patch["position"], dict):
				pos = dict(patch["position"])
				node.position.x = _safe_float(pos.get("x", node.position.x), node.position.x)
				node.position.y = _safe_float(pos.get("y", node.position.y), node.position.y)

			if "properties" in patch and isinstance(patch["properties"], dict):
				node.properties.update(dict(patch["properties"]))

			_normalize_node(node)
			result = self.load_layout(graph)
			return {
				"status": "node_updated",
				"node_id": node_id,
				"runtime_reinitialized": True,
				**result,
			}

	def delete_node(self, node_id: str) -> dict[str, Any]:
		with self._lock:
			graph = self._graph_copy()
			if graph.node_by_id(node_id) is None:
				raise ValueError(f"node '{node_id}' not found")

			graph.nodes = [n for n in graph.nodes if n.id != node_id]
			removed_edges = len([e for e in graph.edges if e.from_node == node_id or e.to_node == node_id])
			graph.edges = [e for e in graph.edges if e.from_node != node_id and e.to_node != node_id]

			result = self.load_layout(graph)
			return {
				"status": "node_deleted",
				"node_id": node_id,
				"removed_edges": removed_edges,
				"runtime_reinitialized": True,
				**result,
			}

	def add_edge(self, edge: LayoutEdge) -> dict[str, Any]:
		with self._lock:
			graph = self._graph_copy()
			if graph.node_by_id(edge.from_node) is None:
				raise ValueError(f"from_node '{edge.from_node}' not found")
			if graph.node_by_id(edge.to_node) is None:
				raise ValueError(f"to_node '{edge.to_node}' not found")

			for e in graph.edges:
				if e.from_node == edge.from_node and e.to_node == edge.to_node:
					raise ValueError(f"edge '{edge.from_node}' -> '{edge.to_node}' already exists")

			graph.edges.append(_normalize_edge(edge))
			result = self.load_layout(graph)
			return {
				"status": "edge_added",
				"from_node": edge.from_node,
				"to_node": edge.to_node,
				"runtime_reinitialized": True,
				**result,
			}

	def delete_edge(self, from_node: str, to_node: str) -> dict[str, Any]:
		with self._lock:
			graph = self._graph_copy()
			before = len(graph.edges)
			graph.edges = [e for e in graph.edges if not (e.from_node == from_node and e.to_node == to_node)]
			if len(graph.edges) == before:
				raise ValueError(f"edge '{from_node}' -> '{to_node}' not found")

			result = self.load_layout(graph)
			return {
				"status": "edge_deleted",
				"from_node": from_node,
				"to_node": to_node,
				"runtime_reinitialized": True,
				**result,
			}

	def load_sample_layout(self) -> dict[str, Any]:
		return self.load_layout(build_sample_layout_graph())

	def run_for(self, duration: float) -> dict[str, Any]:
		if duration <= 0:
			raise ValueError("duration must be > 0")
		if not self.simulation_enabled:
			raise RuntimeError("simulation is paused")
		with self._lock:
			if self.system.simulation is None:
				raise RuntimeError("simulation is not loaded")
			effective_duration = duration * self.speed_multiplier
			now = float(self.system.environment.now)
			target = now + effective_duration
			self.system.run(until=target)
			return {
				"status": "simulation_advanced",
				"from": now,
				"to": float(self.system.environment.now),
				"requested_duration": duration,
				"effective_duration": effective_duration,
				"speed_multiplier": self.speed_multiplier,
				"completed_jobs": len(self.system.simulation.engine.completed_jobs),
			}

	def set_speed(self, multiplier: float) -> dict[str, Any]:
		if multiplier <= 0 or multiplier > 20:
			raise ValueError("speed_multiplier must be > 0 and <= 20")
		with self._lock:
			self.speed_multiplier = float(multiplier)
			return {"status": "speed_updated", "speed_multiplier": self.speed_multiplier}

	def set_simulation_enabled(self, enabled: bool) -> dict[str, Any]:
		with self._lock:
			self.simulation_enabled = bool(enabled)
			return {"status": "simulation_toggled", "enabled": self.simulation_enabled}

	def current_layout(self) -> dict[str, Any]:
		with self._lock:
			return self.system.layout_editor.graph.to_dict()

	def node_details(self, node_id: str) -> dict[str, Any] | None:
		with self._lock:
			node = self.system.layout_editor.graph.node_by_id(node_id)
			if node is None:
				return None
			queue_size = None
			if self.system.simulation is not None:
				queue_size = self.system.simulation.engine._queue_length(node_id)
			return {
				"id": node.id,
				"type": node.type.value,
				"position": node.position.to_dict(),
				"properties": node.properties,
				"queue_size": queue_size,
			}

	def node_telemetry(self, node_id: str, limit: int = 100) -> dict[str, Any]:
		safe_limit = max(1, min(limit, 1000))
		window = self.relay.snapshot(limit=max(500, safe_limit * 15))
		telemetry: list[dict[str, Any]] = []
		for item in reversed(window):
			payload = dict(item.get("payload", {}))
			if str(payload.get("machine_id", "")) != node_id:
				continue
			telemetry.append(item)
			if len(telemetry) >= safe_limit:
				break
		telemetry.reverse()
		latest = telemetry[-1] if telemetry else None
		return {"node_id": node_id, "events": telemetry, "latest": latest}

	def global_metrics(self) -> dict[str, Any]:
		with self._lock:
			env_time = float(self.system.environment.now)
			machines = list(self.system.mes.machine_metrics.values())
			if not machines:
				return {
					"environment_time": env_time,
					"machine_count": 0,
					"availability": 0.0,
					"performance": 0.0,
					"quality": 0.0,
					"oee": 0.0,
					"throughput_per_time": 0.0,
					"wip": 0,
					"completed_jobs": 0,
					"speed_multiplier": self.speed_multiplier,
					"simulation_enabled": self.simulation_enabled,
				}

			availability = sum(m.availability for m in machines) / len(machines)
			performance = sum(m.performance for m in machines) / len(machines)
			quality = sum(m.quality for m in machines) / len(machines)
			oee = sum(m.oee for m in machines) / len(machines)
			good_total = sum(m.good_count for m in machines)
			throughput = good_total / max(1e-6, env_time)

			wip = 0
			completed_jobs = 0
			if self.system.simulation is not None:
				engine = self.system.simulation.engine
				for store in engine._incoming_stores.values():
					wip += len(getattr(store, "items", []))
				for buf in engine._buffers.values():
					wip += len(buf)
				completed_jobs = len(engine.completed_jobs)

			return {
				"environment_time": env_time,
				"machine_count": len(machines),
				"availability": round(availability, 4),
				"performance": round(performance, 4),
				"quality": round(quality, 4),
				"oee": round(oee, 4),
				"throughput_per_time": round(throughput, 4),
				"wip": int(wip),
				"completed_jobs": int(completed_jobs),
				"speed_multiplier": self.speed_multiplier,
				"simulation_enabled": self.simulation_enabled,
			}

	def recent_alerts(self, limit: int = 100) -> list[dict[str, Any]]:
		safe_limit = max(1, min(limit, 1000))
		window = self.relay.snapshot(limit=max(500, safe_limit * 10))
		alerts: list[dict[str, Any]] = []
		for item in reversed(window):
			event_type = str(item.get("event_type", ""))
			payload = dict(item.get("payload", {}))
			severity = None
			reason = None

			if event_type == EventType.MACHINE_FAILURE.value:
				severity = "critical"
				reason = "machine_failure"
			elif event_type == EventType.MAINTENANCE_TRIGGER.value:
				severity = "high"
				reason = str(payload.get("reason", "maintenance_trigger"))
			elif event_type == EventType.HEALTH_UPDATE.value:
				health = _safe_float(payload.get("health", 1.0), 1.0)
				if health < 0.2:
					severity = "critical"
					reason = "health_critical"
				elif health < 0.35:
					severity = "high"
					reason = "health_degraded"

			if severity is None:
				continue

			alerts.append(
				{
					"event_id": item.get("event_id"),
					"timestamp": item.get("timestamp"),
					"severity": severity,
					"reason": reason,
					"event_type": event_type,
					"source": item.get("source"),
					"payload": payload,
				}
			)
			if len(alerts) >= safe_limit:
				break
		alerts.reverse()
		return alerts

	def status(self) -> dict[str, Any]:
		with self._lock:
			model_loaded = self.system.prediction_service._model is not None
			return {
				"simulation_ready": self.system.simulation is not None,
				"simulation_enabled": self.simulation_enabled,
				"speed_multiplier": self.speed_multiplier,
				"environment_time": float(self.system.environment.now),
				"model_loaded": model_loaded,
				"window_size": int(self.system.prediction_service._window_size),
				"tracked_machines": len(self.system.mes.machine_metrics),
			}


app = FastAPI(title="Smart Factory Digital Twin API", version="1.0.0")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
relay = EventRelay()
runtime = DigitalTwinRuntime(relay=relay)


@app.get("/health")
async def health() -> dict[str, Any]:
	return {"status": "ok", **runtime.status()}


@app.post("/layout")
async def load_layout(layout_payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	try:
		graph = LayoutGraph.from_dict(layout_payload)
	except Exception as exc:
		raise HTTPException(status_code=400, detail=f"invalid layout graph payload: {exc}") from exc
	return await run_in_threadpool(runtime.load_layout, graph)


@app.post("/layout/validate")
async def validate_layout(layout_payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	try:
		graph = LayoutGraph.from_dict(layout_payload)
		normalized = runtime.validate_layout(graph)
	except Exception as exc:
		raise HTTPException(status_code=400, detail=f"invalid layout graph payload: {exc}") from exc
	return {
		"status": "layout_valid",
		"nodes": len(normalized.nodes),
		"edges": len(normalized.edges),
		"normalized_graph": normalized.to_dict(),
	}


@app.get("/layout/current")
async def current_layout() -> dict[str, Any]:
	return {"graph": runtime.current_layout()}


@app.post("/layout/node/add")
async def add_layout_node(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	try:
		node = LayoutNode.from_dict(payload)
		return await run_in_threadpool(runtime.add_node, node)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=f"invalid node payload: {exc}") from exc


@app.post("/layout/node/update")
async def update_layout_node(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	node_id = str(payload.get("node_id", ""))
	if not node_id:
		raise HTTPException(status_code=400, detail="node_id is required")
	try:
		patch = dict(payload.get("patch", {}))
		return await run_in_threadpool(runtime.update_node, node_id, patch)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/layout/node/delete")
async def delete_layout_node(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	node_id = str(payload.get("node_id", ""))
	if not node_id:
		raise HTTPException(status_code=400, detail="node_id is required")
	try:
		return await run_in_threadpool(runtime.delete_node, node_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/layout/edge/add")
async def add_layout_edge(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	try:
		edge = LayoutEdge.from_dict(payload)
		return await run_in_threadpool(runtime.add_edge, edge)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=400, detail=f"invalid edge payload: {exc}") from exc


@app.post("/layout/edge/delete")
async def delete_layout_edge(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	from_node = str(payload.get("from_node", ""))
	to_node = str(payload.get("to_node", ""))
	if not from_node or not to_node:
		raise HTTPException(status_code=400, detail="from_node and to_node are required")
	try:
		return await run_in_threadpool(runtime.delete_edge, from_node, to_node)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/layout/sample")
async def load_sample() -> dict[str, Any]:
	return await run_in_threadpool(runtime.load_sample_layout)


@app.post("/simulation/run")
async def run_simulation(duration: float = 5.0) -> dict[str, Any]:
	try:
		return await run_in_threadpool(runtime.run_for, duration)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except RuntimeError as exc:
		raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/simulation/speed")
async def set_simulation_speed(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	try:
		speed_multiplier = _safe_float(payload.get("speed_multiplier"), -1.0)
		if speed_multiplier <= 0:
			raise ValueError("speed_multiplier is required and must be > 0")
		return await run_in_threadpool(runtime.set_speed, speed_multiplier)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/simulation/toggle")
async def toggle_simulation(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
	if "enabled" not in payload:
		raise HTTPException(status_code=400, detail="enabled is required")
	return await run_in_threadpool(runtime.set_simulation_enabled, bool(payload.get("enabled")))


@app.get("/simulation/state")
async def simulation_state() -> dict[str, Any]:
	return runtime.status()


@app.get("/catalog/components")
async def component_catalog() -> dict[str, Any]:
	return {"components": _component_catalog()}


@app.get("/nodes/{node_id}")
async def get_node(node_id: str) -> dict[str, Any]:
	node = runtime.node_details(node_id)
	if node is None:
		raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
	return node


@app.get("/nodes/{node_id}/telemetry")
async def get_node_telemetry(node_id: str, limit: int = 100) -> dict[str, Any]:
	return runtime.node_telemetry(node_id=node_id, limit=limit)


@app.get("/events/recent")
async def recent_events(limit: int = 200) -> dict[str, Any]:
	safe_limit = max(1, min(limit, 1000))
	return {"events": relay.snapshot(limit=safe_limit)}


@app.get("/metrics/global")
async def global_metrics() -> dict[str, Any]:
	return runtime.global_metrics()


@app.get("/alerts/recent")
async def recent_alerts(limit: int = 100) -> dict[str, Any]:
	return {"alerts": runtime.recent_alerts(limit=limit)}


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
	await websocket.accept()
	last_seq = relay.latest_seq()
	try:
		while True:
			events = relay.since(last_seq=last_seq, limit=200)
			for item in events:
				await websocket.send_text(json.dumps(item))
				last_seq = int(item.get("seq", last_seq))
			await asyncio.sleep(0.2)
	except WebSocketDisconnect:
		return

