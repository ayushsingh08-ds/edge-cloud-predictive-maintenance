from __future__ import annotations

from dataclasses import dataclass, field

from events import Event, EventBus, EventType

from .graph import LayoutGraph


@dataclass(slots=True)
class LayoutEditor:
    event_bus: EventBus
    graph: LayoutGraph = field(default_factory=LayoutGraph)

    def update_layout(self, graph: LayoutGraph) -> None:
        self.graph = graph
        self.event_bus.publish(
            Event(
                event_type=EventType.LAYOUT_CHANGED,
                timestamp=0.0,
                source="layout.editor",
                payload={"graph": graph.to_dict()},
            )
        )
