from rabbitmq_client import RabbitMQClient


def handle_message(message):
    print("Received:", message)


client = RabbitMQClient()

client.connect()

client.subscribe('test.topic', handle_message)