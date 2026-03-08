import time
import random
from datetime import datetime

from messaging.rabbitmq_client import RabbitMQClient
from edge.ai.simulator.failure_scenarios import SCENARIOS


class SensorSimulator:

    def __init__(self):
        self.client = RabbitMQClient()
        self.sensor_id = "sensor_001"
        self.value = 50.0
        self.mode = "normal"

    def generate_reading(self):

        if self.mode == "normal":
            self.value += random.uniform(-0.5, 0.5)

        elif self.mode == "degrading":
            self.value += random.uniform(0.3, 0.8)

        elif self.mode == "failing":
            self.value += random.uniform(5, 10)

        event = {
            "sensor_id": self.sensor_id,
            "timestamp": datetime.utcnow().isoformat(),
            "value": round(self.value, 2),
            "mode": self.mode
        }

        return event

    def start(self):

        print("Sensor Simulator Started")

        for scenario in SCENARIOS:

            self.mode = scenario.mode

            print(f"\nRunning scenario: {scenario.name}")
            print(f"Mode: {scenario.mode}")
            print(f"Duration: {scenario.duration_minutes} minutes")

            duration = scenario.duration_seconds()
            start_time = time.time()

            while time.time() - start_time < duration:

                event = self.generate_reading()

                self.client.publish("sensor.raw", event)

                print("Published:", event)

                time.sleep(1)


if __name__ == "__main__":
    simulator = SensorSimulator()
    simulator.start()