import pika
import json


class RabbitMQClient:

    def __init__(self, host="localhost"):
        credentials = pika.PlainCredentials("admin", "admin")

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