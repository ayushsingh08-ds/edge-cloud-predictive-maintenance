import json
import logging
import time
import os
from datetime import datetime
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
        
        # Determine severity and action based on anomaly status
        # For now, use inference_time as proxy for severity (higher = more anomalous)
        # In real scenario, would use actual anomaly_score from model
        anomaly_score = min(1.0, inference_time / 10.0) if is_anomaly else 0.0
        
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

    def start(self):
        """Start consuming anomaly events from edge.anomaly queue."""
        metrics_logger.info("DecisionEngine started, listening for edge.anomaly messages")
        print("[+] Decision Engine waiting for anomaly events...")
        
        def callback(ch, method, properties, body):
            try:
                anomaly_event = json.loads(body)
                self.process_anomaly(anomaly_event)
            except Exception as e:
                print(f"[ERROR] Failed to process anomaly: {e}")
                metrics_logger.error(f"Error processing anomaly: {e}")
        
        self.client.subscribe("edge.anomaly", callback)
