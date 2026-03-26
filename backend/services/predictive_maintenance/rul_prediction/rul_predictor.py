"""RUL Prediction Service - Wraps inference with buffering and messaging.

This service:
1. Subscribes to cleaned sensor data (sensor.cleaned topic)
2. Buffers incoming data by sensor_id (50-sample windows)
3. Performs RUL inference when buffer reaches 50 samples
4. Publishes predictions to cloud.rul topic
5. Handles errors gracefully with fallback modes
"""

import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable, Optional, Dict, Any

import numpy as np
from pika import BlockingConnection, ConnectionParameters, PlainCredentials

from .rul_inference_optimized import (
    initialize_models,
    predict_rul_optimized,
    get_model_info,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SensorReading:
    """Single sensor reading with metadata."""
    timestamp: str
    sensor_id: str
    feature_vector: list  # 14 features
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RULPrediction:
    """RUL prediction result with confidence and status."""
    timestamp: str
    sensor_id: str
    rul_hours: float
    confidence: float
    status: str  # healthy, warning, critical
    samples_count: int
    model_type: str
    inference_ms: float
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


class RULPredictor:
    """RUL Prediction Service with buffering and real-time inference.
    
    Workflow:
    1. Subscribe to sensor.cleaned events
    2. Buffer 50 timesteps per sensor
    3. Run inference when buffer full
    4. Publish predictions to cloud.rul
    5. Maintain rolling window (slide by 1 sample)
    """
    
    # Configuration
    BUFFER_SIZE = 50  # samples per window
    INPUT_FEATURES = 14  # sensor features
    EXCHANGE_NAME = "sensor_exchange"
    SENSOR_TOPIC = "sensor.cleaned"
    OUTPUT_TOPIC = "cloud.rul"
    
    def __init__(self, 
                 rabbitmq_host: str = "localhost",
                 rabbitmq_port: int = 5672,
                 rabbitmq_user: str = "admin",
                 rabbitmq_password: str = "admin123"):
        """Initialize RUL Predictor service.
        
        Args:
            rabbitmq_host: RabbitMQ server host
            rabbitmq_port: RabbitMQ server port
            rabbitmq_user: RabbitMQ username
            rabbitmq_password: RabbitMQ password
        """
        self.host = rabbitmq_host
        self.port = rabbitmq_port
        self.user = rabbitmq_user
        self.password = rabbitmq_password
        
        # Connection and channel (initialized in start())
        self.connection: Optional[BlockingConnection] = None
        self.channel = None
        
        # Sensor data buffers: sensor_id -> deque(max_length=50)
        self.buffers: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.BUFFER_SIZE)
        )
        
        # Model state
        self.model_loaded = False
        self.model_info: Dict[str, Any] = {}
        
        # Statistics
        self.stats = {
            "messages_received": 0,
            "buffers_full": 0,
            "predictions_made": 0,
            "predictions_failed": 0,
        }
    
    def initialize_model(self) -> bool:
        """Load RUL model (TFLite preferred, H5 fallback).
        
        Returns:
            True if model loaded successfully, False otherwise
        """
        try:
            success, model_type = initialize_models()
            if success:
                self.model_loaded = True
                self.model_info = get_model_info()
                logger.info(f"✓ RUL Model loaded: {model_type}")
                logger.info(f"  Model size: {self.model_info['model_size_kb']:.1f} KB")
                return True
            else:
                logger.error(f"✗ Model initialization failed: {model_type}")
                return False
        except Exception as e:
            logger.error(f"✗ Exception loading model: {e}")
            return False

    def _extract_sensor_payload(self, message: Dict[str, Any]) -> tuple[str, list]:
        """Extract canonical sensor_id and a 14-feature vector from incoming payload.

        Supports both:
        1. Native RUL payload: {sensor_id, features:[14]}
        2. Adapter payload: {machine_id, temperature, vibration, pressure, features:{...}}
        """
        sensor_id = message.get("sensor_id") or message.get("machine_id") or "unknown"

        features = message.get("features", [])
        if isinstance(features, list):
            return sensor_id, features

        if isinstance(features, dict):
            vector = [
                float(message.get("temperature", 0.0)),
                float(message.get("vibration", 0.0)),
                float(message.get("pressure", 0.0)),
                float(features.get("temp_mean", 0.0)),
                float(features.get("vib_std", 0.0)),
                float(features.get("pressure_rate", 0.0)),
            ]

            # Pad engineered feature vector to the model's expected width.
            if len(vector) < self.INPUT_FEATURES:
                vector.extend([0.0] * (self.INPUT_FEATURES - len(vector)))

            return sensor_id, vector[: self.INPUT_FEATURES]

        return sensor_id, []
    
    def process_message(self, ch, method, properties, body: bytes) -> None:
        """Process incoming sensor message.
        
        Args:
            ch: Channel (pika)
            method: Delivery method
            properties: Message properties
            body: Message body (JSON)
        """
        try:
            self.stats["messages_received"] += 1
            
            # Parse message
            message = json.loads(body)
            sensor_id, features = self._extract_sensor_payload(message)
            
            if len(features) != self.INPUT_FEATURES:
                logger.warning(
                    f"Invalid feature count for {sensor_id}: "
                    f"expected {self.INPUT_FEATURES}, got {len(features)}"
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Add to buffer
            reading = SensorReading(
                timestamp=message.get("timestamp", datetime.utcnow().isoformat()),
                sensor_id=sensor_id,
                feature_vector=features,
            )
            self.buffers[sensor_id].append(reading)
            
            # Check if buffer is full (deque auto-pops oldest)
            if len(self.buffers[sensor_id]) == self.BUFFER_SIZE:
                self.stats["buffers_full"] += 1
                self._perform_inference(sensor_id)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def _perform_inference(self, sensor_id: str) -> None:
        """Perform RUL inference on buffered data.
        
        Args:
            sensor_id: Sensor identifier
        """
        try:
            if not self.model_loaded:
                logger.warning(f"Model not loaded, skipping inference for {sensor_id}")
                return
            
            # Extract feature vectors from buffer
            buffer_data = self.buffers[sensor_id]
            if len(buffer_data) < self.BUFFER_SIZE:
                logger.warning(f"Buffer incomplete for {sensor_id}: {len(buffer_data)}/{self.BUFFER_SIZE}")
                return
            
            # Create input sequence: (50, 14)
            sequence = np.array(
                [reading.feature_vector for reading in buffer_data],
                dtype=np.float32
            )
            
            # Validate sequence shape
            if sequence.shape != (self.BUFFER_SIZE, self.INPUT_FEATURES):
                logger.error(
                    f"Sequence shape mismatch for {sensor_id}: {sequence.shape}"
                )
                self.stats["predictions_failed"] += 1
                return
            
            # Run inference
            rul_hours, confidence, status, metadata = predict_rul_optimized(sequence)
            
            # Create prediction event
            prediction = RULPrediction(
                timestamp=datetime.utcnow().isoformat(),
                sensor_id=sensor_id,
                rul_hours=round(rul_hours, 1),
                confidence=round(confidence, 3),
                status=status,
                samples_count=self.BUFFER_SIZE,
                model_type=metadata["model_type"],
                inference_ms=metadata["inference_ms"],
            )
            
            # Publish result
            self._publish_prediction(prediction)
            
            self.stats["predictions_made"] += 1
            logger.info(
                f"✓ RUL Prediction {sensor_id}: "
                f"{prediction.rul_hours}h ({prediction.status}) "
                f"conf={prediction.confidence:.2%} "
                f"time={prediction.inference_ms:.2f}ms"
            )
            
        except Exception as e:
            logger.error(f"Inference failed for {sensor_id}: {e}")
            self.stats["predictions_failed"] += 1
    
    def _publish_prediction(self, prediction: RULPrediction) -> None:
        """Publish RUL prediction to cloud.rul topic.
        
        Args:
            prediction: RUL prediction result
        """
        try:
            if not self.channel:
                logger.error("Channel not available, cannot publish")
                return
            
            # Declare exchange and queue (idempotent)
            self.channel.exchange_declare(
                exchange=self.EXCHANGE_NAME,
                exchange_type="topic",
                durable=True,
            )
            
            # Publish message
            self.channel.basic_publish(
                exchange=self.EXCHANGE_NAME,
                routing_key=self.OUTPUT_TOPIC,
                body=prediction.to_json(),
                properties=None,
            )
            
        except Exception as e:
            logger.error(f"Failed to publish prediction: {e}")
    
    def start(self) -> None:
        """Start RUL predictor service - connect and subscribe.
        
        Blocks indefinitely listening for messages.
        """
        try:
            # Initialize model
            if not self.initialize_model():
                logger.error("Failed to initialize model, exiting")
                return
            
            # Connect to RabbitMQ
            logger.info(
                f"Connecting to RabbitMQ: {self.host}:{self.port} "
                f"as {self.user}"
            )
            credentials = PlainCredentials(self.user, self.password)
            parameters = ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            
            self.connection = BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchange and queue
            self.channel.exchange_declare(
                exchange=self.EXCHANGE_NAME,
                exchange_type="topic",
                durable=True,
            )
            
            # Create queue for sensor.cleaned events
            result = self.channel.queue_declare(
                queue="rul_predictor_queue",
                durable=True,
            )
            queue_name = result.method.queue
            
            # Bind queue to sensor.cleaned topic
            self.channel.queue_bind(
                exchange=self.EXCHANGE_NAME,
                queue=queue_name,
                routing_key=self.SENSOR_TOPIC,
            )
            
            logger.info(f"✓ Connected to RabbitMQ")
            logger.info(f"✓ Subscribed to: {self.SENSOR_TOPIC}")
            logger.info(f"✓ Publishing to: {self.OUTPUT_TOPIC}")
            logger.info("✓ RUL Predictor service started, waiting for messages...")
            
            # Set up callback and start consuming
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self.process_message,
            )
            
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("\n✓ Shutting down RUL Predictor...")
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error in RUL Predictor: {e}")
            raise
    
    def stop(self) -> None:
        """Stop service and close connections."""
        try:
            if self.channel:
                self.channel.stop_consuming()
                self.channel.close()
            if self.connection:
                self.connection.close()
            
            logger.info("✓ RUL Predictor stopped")
            logger.info(f"  Stats: {self.stats}")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_buffer_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current buffer status for all sensors.
        
        Returns:
            Dict mapping sensor_id to buffer info
        """
        status = {}
        for sensor_id, buffer in self.buffers.items():
            status[sensor_id] = {
                "samples": len(buffer),
                "ready": len(buffer) == self.BUFFER_SIZE,
                "percentage_full": (len(buffer) / self.BUFFER_SIZE) * 100,
            }
        return status
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dict with message and prediction counts
        """
        return {
            **self.stats,
            "active_sensors": len(self.buffers),
            "model_info": self.model_info,
        }


if __name__ == "__main__":
    # Run service
    predictor = RULPredictor()
    predictor.start()
