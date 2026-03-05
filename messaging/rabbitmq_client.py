import pika
import json


class RabbitMQClient:

    def __init__(self, host='localhost', port=5672, username='admin', password='admin'):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.connection = None
        self.channel = None

    def connect(self):

        credentials = pika.PlainCredentials(self.username, self.password)

        params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials
        )

        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()

        self.channel.exchange_declare(
            exchange='events_exchange',
            exchange_type='topic',
            durable=True
        )

        print("Connected to RabbitMQ")