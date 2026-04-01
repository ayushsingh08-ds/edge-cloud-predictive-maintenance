from rabbitmq_client import RabbitMQClient


client = RabbitMQClient()

client.connect()

client.publish('test.topic', {'msg': 'hello'})