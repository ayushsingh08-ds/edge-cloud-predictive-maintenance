"""Product flow event definitions."""

from __future__ import annotations

from dataclasses import dataclass

from events.base_event import BaseEvent


@dataclass
class ProductCreated(BaseEvent):
    event_name = "product.created"

    product_id: str
    machine_id: str
    location: str
    status: str


@dataclass
class ProductMoved(BaseEvent):
    event_name = "product.moved"

    product_id: str
    machine_id: str
    location: str
    status: str


@dataclass
class ProductCompleted(BaseEvent):
    event_name = "product.completed"

    product_id: str
    machine_id: str
    location: str
    status: str
