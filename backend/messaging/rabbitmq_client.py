import pika
import json
import time
import logging
from datetime import date, datetime

from config.env import RABBITMQ_HOST, RABBITMQ_PASS, RABBITMQ_PORT, RABBITMQ_USER

# Suppress pika debug logs
logging.getLogger('pika').setLevel(logging.WARNING)


class RabbitMQClient:

    @staticmethod
    def _json_default(obj):
        """Serialize common non-native types (e.g., numpy scalars, datetimes)."""
        try:
            import numpy as np
            if isinstance(obj, np.generic):
                return obj.item()
        except Exception:
            pass

        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    def __init__(self, host=None, max_retries=3):
        resolved_host = host or RABBITMQ_HOST or "localhost"
        resolved_user = RABBITMQ_USER or "admin"
        resolved_pass = RABBITMQ_PASS or "admin123"
        resolved_port = int(RABBITMQ_PORT) if RABBITMQ_PORT else 5672

        credentials = pika.PlainCredentials(resolved_user, resolved_pass)

        parameters = pika.ConnectionParameters(
            host=resolved_host,
            port=resolved_port,
            credentials=credentials
        )

        self.connection = None
        self.channel = None
        
        # Try to connect with retries
        for attempt in range(max_retries):
            try:
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # create exchange
                self.channel.exchange_declare(
                    exchange="sensor_exchange",
                    exchange_type="topic",
                    durable=True
                )
                pass  # Connection successful, silent
                return
            except pika.exceptions.AMQPConnectionError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise

    def publish(self, topic, message):
        self.channel.basic_publish(
            exchange="sensor_exchange",
            routing_key=topic,
            body=json.dumps(message, default=self._json_default)
        )

    def subscribe(self, topic, callback):
        # Create exclusive queue
        result = self.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        # Bind queue to topic
        self.channel.queue_bind(
            exchange="sensor_exchange",
            queue=queue_name,
            routing_key=topic
        )

        # Start consuming
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True
        )

        self.channel.start_consuming()

    def close(self):
        if self.connection:
            self.connection.close()
