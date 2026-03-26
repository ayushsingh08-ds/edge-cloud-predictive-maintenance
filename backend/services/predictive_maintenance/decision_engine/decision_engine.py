import json
import logging
import time
import os
from pathlib import Path
import sys
from datetime import datetime

# Allow running this file directly via script path by exposing backend root.
BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from messaging.rabbitmq_client import RabbitMQClient

# Setup metrics logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/cloud_decision_metrics.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
metrics_logger = logging.getLogger('metrics')


class DecisionEngine:
    def __init__(self):
        self.client = RabbitMQClient()
        
        # Metrics
        self.total_anomalies = 0
        self.critical_count = 0
        self.high_count = 0
        self.medium_count = 0
        self.total_processing_time = 0
        
        metrics_logger.info("DecisionEngine initialized")

    def process_anomaly(self, anomaly_event):
        """
        Process anomaly event and decide action based on anomaly score.
        
        Args:
            anomaly_event: Dict with anomaly data including is_anomaly flag
        
        Returns:
            maintenance_alert: Dict with severity and action
        """
        start_time = time.time()
        
        # Extract data
        machine_id = anomaly_event.get('machine_id', 'UNKNOWN')
        is_anomaly = anomaly_event.get('is_anomaly', False)
        inference_time = anomaly_event.get('inference_time_ms', 0)
        
        # Determine severity and action based on anomaly score.
        anomaly_score = float(anomaly_event.get('anomaly_score', 0.0)) if is_anomaly else 0.0
        
        if anomaly_score > 0.9:
            severity = 'CRITICAL'
            action = 'Stop machine immediately'
            self.critical_count += 1
        elif anomaly_score > 0.7:
            severity = 'HIGH'
            action = 'Schedule inspection within 4 hours'
            self.high_count += 1
        else:
            severity = 'MEDIUM'
            action = 'Monitor closely'
            self.medium_count += 1
        
        processing_time = time.time() - start_time
        
        # Create maintenance alert event
        maintenance_alert = {
            "machine_id": machine_id,
            "severity": severity,
            "action": action,
            "anomaly_detected": is_anomaly,
            "anomaly_score": round(anomaly_score, 4),
            "inference_time_ms": inference_time,
            "decision_time_ms": round(processing_time * 1000, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Publish alert
        self.client.publish("maintenance.alert", maintenance_alert)
        
        print(f"[DECISION] {severity}: {action} for {machine_id}")
        
        # Update metrics
        self.total_anomalies += 1
        self.total_processing_time += processing_time
        
        # Log metrics periodically
        if self.total_anomalies % 10 == 0:
            avg_processing_time = self.total_processing_time / self.total_anomalies
            critical_rate = (self.critical_count / self.total_anomalies * 100) if self.total_anomalies > 0 else 0
            high_rate = (self.high_count / self.total_anomalies * 100) if self.total_anomalies > 0 else 0
            medium_rate = (self.medium_count / self.total_anomalies * 100) if self.total_anomalies > 0 else 0
            
            metrics_logger.info(
                f"Total Anomalies: {self.total_anomalies}, "
                f"Critical: {self.critical_count} ({critical_rate:.1f}%), "
                f"High: {self.high_count} ({high_rate:.1f}%), "
                f"Medium: {self.medium_count} ({medium_rate:.1f}%), "
                f"Avg Decision Time: {avg_processing_time*1000:.2f}ms"
            )
        
        return maintenance_alert

    def process_rul(self, rul_event):
        """Process RUL event and emit maintenance alert."""
        start_time = time.time()

        machine_id = rul_event.get("sensor_id") or rul_event.get("machine_id", "UNKNOWN")
        rul_hours = float(rul_event.get("rul_hours", 0.0))
        status = str(rul_event.get("status", "")).lower()
        confidence = float(rul_event.get("confidence", 0.0))

        if status == "critical" or rul_hours < 24:
            severity = "CRITICAL"
            action = "Schedule immediate maintenance"
            self.critical_count += 1
        elif status == "warning" or rul_hours < 72:
            severity = "HIGH"
            action = "Plan maintenance within 24 hours"
            self.high_count += 1
        else:
            severity = "MEDIUM"
            action = "Continue monitoring based on current RUL"
            self.medium_count += 1

        processing_time = time.time() - start_time

        maintenance_alert = {
            "machine_id": machine_id,
            "severity": severity,
            "action": action,
            "source": "rul",
            "rul_hours": round(rul_hours, 2),
            "rul_status": status,
            "confidence": round(confidence, 4),
            "decision_time_ms": round(processing_time * 1000, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.client.publish("maintenance.alert", maintenance_alert)
        self.total_anomalies += 1
        self.total_processing_time += processing_time

        print(f"[DECISION][RUL] {severity}: {action} for {machine_id} (RUL={rul_hours:.1f}h)")
        return maintenance_alert

    def start(self):
        """Start consuming anomaly and RUL events."""
        metrics_logger.info("DecisionEngine started, listening for edge.anomaly and cloud.rul messages")
        print("[+] Decision Engine waiting for edge.anomaly and cloud.rul events...")

        result = self.client.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        self.client.channel.queue_bind(
            exchange="sensor_exchange",
            queue=queue_name,
            routing_key="edge.anomaly",
        )
        self.client.channel.queue_bind(
            exchange="sensor_exchange",
            queue=queue_name,
            routing_key="cloud.rul",
        )

        def callback(ch, method, properties, body):
            try:
                event = json.loads(body)
                topic = getattr(method, "routing_key", "")
                if topic == "cloud.rul" or "rul_hours" in event:
                    self.process_rul(event)
                else:
                    self.process_anomaly(event)
            except Exception as e:
                print(f"[ERROR] Failed to process decision event: {e}")
                metrics_logger.error(f"Error processing decision event: {e}")

        self.client.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self.client.channel.start_consuming()


if __name__ == "__main__":
    engine = DecisionEngine()
    try:
        engine.start()
    except KeyboardInterrupt:
        print("\n[!] Decision Engine stopped by user")
    finally:
        engine.client.close()
