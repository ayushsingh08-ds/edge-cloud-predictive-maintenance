"""Routing decision event definitions."""

from __future__ import annotations

from dataclasses import dataclass

from events.base_event import BaseEvent


@dataclass
class RoutingDecision(BaseEvent):
    event_name = "routing.decision"

    product_id: str
    from_machine: str
    to_machine: str
    route: list[str]


@dataclass
class ProductRouteAssigned(BaseEvent):
    event_name = "routing.product.assigned"

    product_id: str
    from_machine: str
    to_machine: str
    route: list[str]
