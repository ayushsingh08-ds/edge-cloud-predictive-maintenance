"""Business logic for machine registry operations and event publishing."""

from __future__ import annotations

from events import MachineConnected, MachineRegistered, MachineStatusChanged
from messaging.rabbitmq_client import RabbitMQClient
from services.machine_registry import machine_repository as repository


class MachineRegistryService:
    """Core service for machine lifecycle and topology management."""

    def __init__(self, publisher: RabbitMQClient | None = None) -> None:
        self.publisher = publisher or RabbitMQClient()

    def _publish_event(self, topic: str, event_payload: dict) -> None:
        self.publisher.publish(topic, event_payload)

    def register_machine(self, name: str, type: str, location: str) -> dict:
        machine = repository.create_machine(
            name=name,
            type=type,
            location=location,
            status="running",
        )

        event = MachineRegistered(
            machine_id=str(machine["id"]),
            name=machine["name"],
            type=machine["type"],
            location=machine["location"],
        )
        self._publish_event("machine.registered", event.to_dict())

        return machine

    def change_machine_status(self, machine_id: int, new_status: str) -> dict:
        current_machine = repository.get_machine(machine_id)
        if current_machine is None:
            raise ValueError(f"Machine {machine_id} not found")

        previous_status = current_machine["status"]
        updated_machine = repository.update_machine_status(machine_id, new_status)
        if updated_machine is None:
            raise ValueError(f"Machine {machine_id} not found")

        event = MachineStatusChanged(
            machine_id=str(machine_id),
            previous_status=previous_status,
            new_status=updated_machine["status"],
        )
        self._publish_event("machine.status.changed", event.to_dict())

        return updated_machine

    def list_machines(self) -> list[dict]:
        return repository.get_all_machines()

    def connect_machines(self, from_machine_id: int, to_machine_id: int) -> dict:
        connection = repository.connect_machines(from_machine_id, to_machine_id)

        event = MachineConnected(
            from_machine_id=str(connection["from_machine_id"]),
            to_machine_id=str(connection["to_machine_id"]),
        )
        self._publish_event("machine.connected", event.to_dict())

        return connection

    def get_machine_details(self, machine_id: int) -> dict:
        machine = repository.get_machine(machine_id)
        if machine is None:
            raise ValueError(f"Machine {machine_id} not found")

        return {
            **machine,
            "connections": repository.get_machine_connections(machine_id),
        }
