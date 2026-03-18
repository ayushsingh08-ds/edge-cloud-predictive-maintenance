import pika
import json


class RabbitMQClient:

    def __init__(self, host="localhost"):
        credentials = pika.PlainCredentials("admin", "admin123")

        parameters = pika.ConnectionParameters(
            host=host,
            port=5672,
            credentials=credentials
        )

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # create exchange
        self.channel.exchange_declare(
            exchange="sensor_exchange",
            exchange_type="topic",
            durable=True
        )

    def publish(self, topic, message):
        self.channel.basic_publish(
            exchange="sensor_exchange",
            routing_key=topic,
            body=json.dumps(message)
        )

        print(f"[x] Sent {topic}: {message}")

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

        print(f"Subscribed to {topic}, waiting for messages...")
        self.channel.start_consuming()

    def close(self):
        if self.connection:
            self.connection.close()