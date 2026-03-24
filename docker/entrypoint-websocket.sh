#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until python -c "import psycopg2; psycopg2.connect('postgresql://user:password@postgres:5432/smart_factory')" 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Waiting for RabbitMQ to be ready..."
until python -c "import pika; pika.BlockingConnection(pika.ConnectionParameters('rabbitmq', 5672, '/', pika.PlainCredentials('admin', 'admin123')))" 2>/dev/null; do
  echo "RabbitMQ is unavailable - sleeping"
  sleep 1
done
echo "RabbitMQ is ready!"

echo "Initializing database schema..."
cd /app
python -c "from database.init_db import init_db; init_db()"
echo "Database initialized!"

echo "Starting WebSocket Server on 0.0.0.0:8001..."
uvicorn api.app:app --host 0.0.0.0 --port 8001 --reload
