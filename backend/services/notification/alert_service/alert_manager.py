import json
import logging
import os
from datetime import datetime
from messaging.rabbitmq_client import RabbitMQClient

# Setup alert logging
os.makedirs('data/logs', exist_ok=True)
logging.basicConfig(
    filename='data/logs/maintenance_alerts.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
alert_logger = logging.getLogger('alerts')


class AlertManager:
    def __init__(self):
        self.client = RabbitMQClient()
        self.critical_count = 0
        self.high_count = 0
        self.medium_count = 0
        
        alert_logger.info("=" * 80)
        alert_logger.info("AlertManager initialized")
        alert_logger.info("=" * 80)

    def process_alert(self, alert_event):
        """
        Process maintenance alert events with appropriate logging and color coding.
        
        Args:
            alert_event: Dict with maintenance alert data
        """
        machine_id = alert_event.get('machine_id', 'UNKNOWN')
        severity = alert_event.get('severity', 'UNKNOWN')
        action = alert_event.get('action', '')
        timestamp = alert_event.get('timestamp', '')
        
        # Color codes for console output
        color_map = {
            'CRITICAL': '\033[91m',  # Red
            'HIGH': '\033[93m',       # Yellow
            'MEDIUM': '\033[94m',     # Blue
            'RESET': '\033[0m'        # Reset
        }
        
        color = color_map.get(severity, color_map['RESET'])
        reset = color_map['RESET']
        
        # Count by severity
        if severity == 'CRITICAL':
            self.critical_count += 1
        elif severity == 'HIGH':
            self.high_count += 1
        elif severity == 'MEDIUM':
            self.medium_count += 1
        
        # Log to file
        log_message = f"[{severity:8s}] Machine: {machine_id:10s} | Action: {action:50s} | {timestamp}"
        alert_logger.info(log_message)
        
        # Print to console with color
        console_message = f"{color}[ALERT {severity:8s}]{reset} {machine_id:10s} | {action}"
        print(console_message)
        
        # Log summary every 50 alerts
        total_alerts = self.critical_count + self.high_count + self.medium_count
        if total_alerts % 50 == 0:
            summary = f"\nSUMMARY: Total Alerts: {total_alerts} | Critical: {self.critical_count} | High: {self.high_count} | Medium: {self.medium_count}\n"
            alert_logger.info(summary)
            print(f"\n{summary}\n")

    def start(self):
        """Start consuming maintenance alert events from maintenance.alert queue."""
        alert_logger.info("AlertManager started, listening for maintenance.alert messages")
        print("\n[+] Alert Manager listening for maintenance alerts...\n")
        
        def callback(ch, method, properties, body):
            try:
                alert_event = json.loads(body)
                self.process_alert(alert_event)
            except Exception as e:
                error_msg = f"Error processing alert: {e}"
                alert_logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
        
        self.client.subscribe("maintenance.alert", callback)
