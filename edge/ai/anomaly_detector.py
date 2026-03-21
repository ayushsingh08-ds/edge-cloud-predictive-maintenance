import json
import logging
import time
import os
from datetime import datetime
from messaging.rabbitmq_client import RabbitMQClient
from .inference import load_model, predict

# Setup metrics logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/edge_ai_metrics.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
metrics_logger = logging.getLogger('metrics')

class EdgeAnomalyDetector:
    def __init__(self):
        self.client = RabbitMQClient()
        self.model, self.scaler, self.features, self.meta = load_model()
        
        # Metrics
        self.total_messages = 0
        self.anomalies_detected = 0
        self.total_inference_time = 0
        
        metrics_logger.info("EdgeAnomalyDetector initialized")

    def process_message(self, ch, method, properties, body):
        message = json.loads(body)

        print(f"[+] Received cleaned data: {message}")

        # Extract features
        features = message.get("data", {})

        # Run prediction with timing
        start_time = time.time()
        is_anomaly = predict(self.model, self.scaler, self.features, self.meta, features)
        inference_time = time.time() - start_time

        # Update metrics
        self.total_messages += 1
        if is_anomaly:
            self.anomalies_detected += 1
        self.total_inference_time += inference_time

        # Create anomaly event
        anomaly_event = {
            "machine_id": message.get("machine_id"),
            "is_anomaly": is_anomaly,
            "data": features,
            "inference_time_ms": round(inference_time * 1000, 2),
            "timestamp": datetime.utcnow().isoformat()
        }

        # Publish result
        self.client.publish("edge.anomaly", anomaly_event)

        print(f"[!] Anomaly result: {anomaly_event}")
        
        # Log metrics periodically
        if self.total_messages % 10 == 0:
            avg_inference_time = self.total_inference_time / self.total_messages
            anomaly_rate = (self.anomalies_detected / self.total_messages * 100) if self.total_messages > 0 else 0
            metrics_logger.info(
                f"Messages: {self.total_messages}, Anomalies: {self.anomalies_detected}, "
                f"Anomaly Rate: {anomaly_rate:.2f}%, Avg Inference Time: {avg_inference_time*1000:.2f}ms"
            )

    def start(self):
        metrics_logger.info("EdgeAnomalyDetector started, listening for sensor.cleaned messages")
        self.client.subscribe("sensor.cleaned", self.process_message)