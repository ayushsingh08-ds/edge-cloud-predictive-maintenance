from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime
from events import EventBus, Event, EventType

class MaintenanceScheduler:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.scheduled_jobs: Dict[str, float] = {} # machine_id -> timestamp
        self.tickets: List[Dict[str, Any]] = []

    def check_and_schedule(self, machine_id: str, health: float, rul_hours: float, current_time: float):
        """
        Decision Logic:
        If RUL < 5h OR health < 0.2, schedule ASAP.
        If RUL < 24h, find next predicted low-demand window (mocked for now).
        """
        if machine_id in self.scheduled_jobs:
            return

        if health < 0.25 or rul_hours < 5.0:
            # Prescriptive Action: Immediate maintenance
            self._schedule(machine_id, current_time + 5.0, "Critical health depletion")
        elif health < 0.4 or rul_hours < 12.0:
            # Prescriptive Action: Scheduled maintenance in 15 mins (simulated time)
            self._schedule(machine_id, current_time + 900.0, "Degradation trend predicted")

    def _schedule(self, machine_id: str, start_time: float, reason: str):
        self.scheduled_jobs[machine_id] = start_time
        ticket = {
            "id": f"TKT-{datetime.now().strftime('%H%M%S')}-{machine_id}",
            "machine_id": machine_id,
            "scheduled_at": start_time,
            "reason": reason,
            "status": "scheduled",
        }
        self.tickets.append(ticket)
        
        # Notify UI through event bus
        self.event_bus.publish(
            Event(
                event_type=EventType.MAINTENANCE_TRIGGER,
                timestamp=start_time,
                source=f"maintenance.scheduler",
                payload={
                    "machine_id": machine_id,
                    "scheduled_start": start_time,
                    "ticket_id": ticket["id"],
                    "message": f"PRESCRIPTIVE ACTION: Machine {machine_id} scheduled for maintenance at T={start_time:.1f} ({reason})."
                }
            )
        )

    def get_upcoming_maintenance(self, machine_id: str) -> float | None:
        return self.scheduled_jobs.get(machine_id)
