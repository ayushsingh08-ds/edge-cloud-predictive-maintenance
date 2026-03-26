from __future__ import annotations

import asyncio
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.production_node import ProductionNode
from services.simulation.sensor_simulator.sensor_simulator import SensorSimulator

class SimulationManager:
    _instance: Optional['SimulationManager'] = None
    
    def __init__(self):
        self.is_running = False
        self.sensor_tasks: Dict[str, asyncio.Task] = {}
        self.simulators: Dict[str, SensorSimulator] = {}
    
    @classmethod
    def get_instance(cls) -> 'SimulationManager':
        if cls._instance is None:
            cls._instance = cls()
        assert cls._instance is not None
        return cls._instance

    async def start_simulation(self, db: Session):
        if self.is_running:
            return
        self.is_running = True
        
        # Pull all current machines from DB
        nodes = db.scalars(select(ProductionNode)).all()
        for node in nodes:
            machine_id = str(node.id)
            self.start_machine_sensor(machine_id)
            
    async def stop_simulation(self):
        self.is_running = False
        for task in self.sensor_tasks.values():
            task.cancel()
        self.sensor_tasks.clear()
        self.simulators.clear()
        
    def start_machine_sensor(self, machine_id: str):
        if not self.is_running:
            return
            
        if machine_id in self.sensor_tasks:
            return # Already running
            
        simulator = SensorSimulator(machine_id=machine_id)
        self.simulators[machine_id] = simulator
        
        # Spawn asyncio background task
        task = asyncio.create_task(simulator.run_async_loop())
        self.sensor_tasks[machine_id] = task

simulation_manager = SimulationManager.get_instance()
