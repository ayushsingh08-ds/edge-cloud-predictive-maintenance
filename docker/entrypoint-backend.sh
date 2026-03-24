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

echo "Starting service: $SERVICE_TYPE"
case $SERVICE_TYPE in
  alert_manager)
    python scripts/run_alert_manager.py
    ;;
  decision_engine)
    python scripts/run_decision_engine.py
    ;;
  anomaly_detector)
    python -m services.edge.anomaly_detection.anomaly_detector
    ;;
  data_adapter)
    python scripts/run_adapter.py
    ;;
  rul_predictor)
    python scripts/run_rul_predictor.py
    ;;
  sensor_simulator)
    python scripts/run_sensor_simulator.py
    ;;
  *)
    echo "Unknown service type: $SERVICE_TYPE"
    exit 1
    ;;
esac
