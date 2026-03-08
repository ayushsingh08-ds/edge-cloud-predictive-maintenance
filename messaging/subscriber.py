import pika
import json


class SensorSubscriber:

    def __init__(self):

        credentials = pika.PlainCredentials("admin", "admin")

        parameters = pika.ConnectionParameters(
            host="localhost",
            port=5672,
            credentials=credentials
        )

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # Declare exchange
        self.channel.exchange_declare(
            exchange="sensor_exchange",
            exchange_type="topic",
            durable=True
        )

        # Create queue
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.queue_name = result.method.queue

        # Bind queue to topic
        self.channel.queue_bind(
            exchange="sensor_exchange",
            queue=self.queue_name,
            routing_key="sensor.raw"
        )

    def callback(self, ch, method, properties, body):

        data = json.loads(body)

        print("Received sensor data:")
        print(data)
        print("-" * 40)

    def start(self):

        print("Waiting for sensor data...")

        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.callback,
            auto_ack=True
        )

        self.channel.start_consuming()


if __name__ == "__main__":
    subscriber = SensorSubscriber()
    subscriber.start()