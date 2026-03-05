from messaging.rabbitmq_client import RabbitMQClient
from config.topics import TOPICS


def setup_topics():

    client = RabbitMQClient()
    client.connect()

    for topic in TOPICS:
        # declare a queue for each topic
        queue_name = topic.replace(".", "_")

        client.channel.queue_declare(queue=queue_name, durable=True)

        client.channel.queue_bind(
            exchange="events_exchange",
            queue=queue_name,
            routing_key=topic
        )

        print(f"Created topic binding: {topic} -> {queue_name}")

    client.close()


if __name__ == "__main__":
    setup_topics()