from __future__ import annotations

import pika

from config.config import get_settings


def get_rabbitmq_connection() -> pika.BlockingConnection:
    settings = get_settings()

    credentials = pika.PlainCredentials(
        username=settings.rabbitmq_user,
        password=settings.rabbitmq_pass,
    )
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=5672,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=30,
    )

    return pika.BlockingConnection(parameters)


def rabbitmq_healthcheck() -> bool:
    connection = None
    try:
        connection = get_rabbitmq_connection()
        return connection.is_open
    except Exception:
        return False
    finally:
        if connection and connection.is_open:
            connection.close()
