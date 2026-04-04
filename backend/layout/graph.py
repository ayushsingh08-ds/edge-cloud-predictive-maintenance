from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LayoutNodeType(str, Enum):
    MACHINE = "Machine"
    BUFFER = "Buffer"
    DIVIDER = "Divider"
    CONVEYOR = "Conveyor"
    SOURCE = "Source"
    SINK = "Sink"


@dataclass(slots=True)
class LayoutPosition:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutPosition":
        return cls(x=float(data["x"]), y=float(data["y"]))


def _empty_properties() -> dict[str, Any]:
    return {}


@dataclass(slots=True)
class LayoutNode:
    id: str
    type: LayoutNodeType
    position: LayoutPosition
    properties: dict[str, Any] = field(default_factory=_empty_properties)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "position": self.position.to_dict(),
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutNode":
        return cls(
            id=str(data["id"]),
            type=LayoutNodeType(str(data["type"])),
            position=LayoutPosition.from_dict(dict(data["position"])),
            properties=dict(data.get("properties", {})),
        )


@dataclass(slots=True)
class LayoutEdge:
    from_node: str
    to_node: str
    transport_time: float | None = None
    properties: dict[str, Any] = field(default_factory=_empty_properties)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "properties": self.properties,
        }
        if self.transport_time is not None:
            data["transport_time"] = self.transport_time
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutEdge":
        return cls(
            from_node=str(data["from_node"]),
            to_node=str(data["to_node"]),
            transport_time=(float(data["transport_time"]) if data.get("transport_time") is not None else None),
            properties=dict(data.get("properties", {})),
        )


@dataclass(slots=True)
class LayoutGraph:
    nodes: list[LayoutNode] = field(default_factory=list)
    edges: list[LayoutEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutGraph":
        return cls(
            nodes=[LayoutNode.from_dict(node) for node in data.get("nodes", [])],
            edges=[LayoutEdge.from_dict(edge) for edge in data.get("edges", [])],
        )

    @classmethod
    def from_json(cls, json_text: str) -> "LayoutGraph":
        return cls.from_dict(json.loads(json_text))

    def node_by_id(self, node_id: str) -> LayoutNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
