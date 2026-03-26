import json
import logging
import time
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

# Allow running this file directly via script path by exposing backend root.
BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from messaging.rabbitmq_client import RabbitMQClient

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
        self.model_enabled = True
        try:
            from .inference import load_models, predict_anomaly
            self._predict_anomaly = predict_anomaly
            self.model, self.scaler, self.meta = load_models()
        except Exception as exc:
            self.model_enabled = False
            self._predict_anomaly = None
            metrics_logger.warning(f"Model load failed, using heuristic fallback: {exc}")
        
        # Metrics
        self.total_messages = 0
        self.anomalies_detected = 0
        self.total_inference_time = 0
        
        metrics_logger.info("EdgeAnomalyDetector initialized")

    def _heuristic_anomaly(self, message):
        temp = abs(float(message.get("temperature", 0.0)))
        vib = abs(float(message.get("vibration", 0.0)))
        pres = abs(float(message.get("pressure", 0.0)))

        features = message.get("features", {})
        vib_std = abs(float(features.get("vib_std", 0.0)))
        pressure_rate = abs(float(features.get("pressure_rate", 0.0)))

        # Normalized channels + engineered signals to derive a bounded anomaly score.
        raw_score = (
            0.25 * min(temp / 3.0, 1.0)
            + 0.35 * min(vib / 3.0, 1.0)
            + 0.15 * min(pres / 3.0, 1.0)
            + 0.15 * min(vib_std / 2.0, 1.0)
            + 0.10 * min(pressure_rate / 2.0, 1.0)
        )

        anomaly_score = float(max(0.0, min(raw_score, 1.0)))
        is_anomaly = anomaly_score >= 0.7
        return anomaly_score, is_anomaly

    def process_message(self, ch, method, properties, body):
        message = json.loads(body)

        print(f"[+] Received cleaned data: {message}")

        # Build feature input from cleaned adapter payload.
        feature_dict = {
            "temperature": message.get("temperature", 0.0),
            "vibration": message.get("vibration", 0.0),
            "pressure": message.get("pressure", 0.0),
        }
        feature_dict.update(message.get("features", {}))

        # Run prediction with timing
        start_time = time.time()
        if self.model_enabled:
            try:
                score, is_anomaly = self._predict_anomaly(feature_dict)
                anomaly_score = max(0.0, min((-score) + 0.5, 1.0))
            except Exception as exc:
                metrics_logger.warning(f"Model inference failed, switching to heuristic: {exc}")
                anomaly_score, is_anomaly = self._heuristic_anomaly(message)
        else:
            anomaly_score, is_anomaly = self._heuristic_anomaly(message)
        inference_time = time.time() - start_time

        # Ensure payload fields are plain Python JSON-native types.
        is_anomaly = bool(is_anomaly)
        anomaly_score = float(anomaly_score)

        # Update metrics
        self.total_messages += 1
        if is_anomaly:
            self.anomalies_detected += 1
        self.total_inference_time += inference_time

        # Create anomaly event
        anomaly_event = {
            "machine_id": message.get("machine_id"),
            "is_anomaly": is_anomaly,
            "anomaly_score": round(anomaly_score, 4),
            "data": feature_dict,
            "inference_time_ms": round(inference_time * 1000, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
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


if __name__ == "__main__":
    print("[+] Edge Anomaly Detector listening for sensor.cleaned messages...")
    detector = EdgeAnomalyDetector()
    detector.start()