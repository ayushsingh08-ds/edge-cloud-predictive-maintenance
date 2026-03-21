"""Entry point for sensor simulator."""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge.ai.simulator.sensor_simulator import SensorSimulator

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensor Simulator")
    parser.add_argument("--mode", choices=["normal", "degrading", "failing"], help="Run only this mode")
    args = parser.parse_args()
    
    simulator = SensorSimulator()
    simulator.start(mode=args.mode)
