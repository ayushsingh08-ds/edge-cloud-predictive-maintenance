from __future__ import annotations

from dataclasses import dataclass, field

import simpy

from events import EventBus
from layout import LayoutGraph

from .engine import FactorySimulationEngine


@dataclass(slots=True)
class Simulation:
    engine: FactorySimulationEngine

    @classmethod
    def from_layout_graph(
        cls,
        layout_graph: LayoutGraph,
        environment: simpy.Environment | None = None,
        event_bus: EventBus | None = None,
    ) -> "Simulation":
        environment = environment or simpy.Environment()
        engine = FactorySimulationEngine.from_layout_json(
            layout_graph.to_json(),
            environment=environment,
            event_bus=event_bus,
        )
        return cls(engine=engine)

    @classmethod
    def from_layout_json(
        cls,
        layout_json: str,
        environment: simpy.Environment | None = None,
        event_bus: EventBus | None = None,
    ) -> "Simulation":
        environment = environment or simpy.Environment()
        engine = FactorySimulationEngine.from_layout_json(layout_json, environment=environment, event_bus=event_bus)
        return cls(engine=engine)

    @property
    def event_bus(self):
        return self.engine.event_bus

    @property
    def environment(self):
        return self.engine.environment

    def run(self, until: float) -> None:
        self.engine.run(until)
