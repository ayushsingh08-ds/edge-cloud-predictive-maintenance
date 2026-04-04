from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import DefaultDict, Deque

import simpy

from .contracts import Event, EventHandler, EventType


@dataclass(slots=True)
class EventBus:
    environment: simpy.Environment
    queue_capacity: int | None = None
    _subscribers: DefaultDict[EventType, list[EventHandler]] = field(default_factory=lambda: defaultdict(list))
    _queue: Deque[Event] = field(default_factory=deque, init=False)
    _queue_event: simpy.events.Event = field(init=False)
    _dispatcher_started: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._queue_event = self.environment.event()
        self.start()

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: Event) -> bool:
        if self.queue_capacity is not None and len(self._queue) >= self.queue_capacity:
            return False
        self._queue.append(event)
        if not self._queue_event.triggered:
            self._queue_event.succeed()
        return True

    def start(self) -> None:
        if not self._dispatcher_started:
            self._dispatcher_started = True
            self.environment.process(self._dispatch_loop())

    def _dispatch_loop(self):
        while True:
            if not self._queue:
                self._queue_event = self.environment.event()
                yield self._queue_event
                continue

            event = self._queue.popleft()
            for handler in list(self._subscribers.get(event.event_type, [])):
                self.environment.process(self._invoke_handler(handler, event))

            yield self.environment.timeout(0)

    def _invoke_handler(self, handler: EventHandler, event: Event):
        result = handler(event)
        if isinstance(result, simpy.events.Event):
            yield result
        else:
            yield self.environment.timeout(0)
