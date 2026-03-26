from collections import deque, defaultdict
import json
import logging
from statistics import mean, pstdev
from messaging.rabbitmq_client import RabbitMQClient

# Buffer: last 50 readings per sensor
sensor_buffers = defaultdict(lambda: {
    "temperature": deque(maxlen=50),
    "vibration": deque(maxlen=50),
    "pressure": deque(maxlen=50)
})


client = RabbitMQClient()
# client.connect()  # Connection established in __init__

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

message_count = 0


# ----------- Helper Functions -----------

def z_score_normalize(value, values):
    if len(values) < 2:
        return value  # not enough data

    mean_val = mean(values)
    std = pstdev(values)

    if std == 0:
        return 0

    return (value - mean_val) / std


def compute_features(sensor_id):
    buffer = sensor_buffers[sensor_id]

    temp_values = list(buffer["temperature"])
    vib_values = list(buffer["vibration"])
    pres_values = list(buffer["pressure"])

    features = {}

    # Rolling mean (temperature)
    if len(temp_values) >= 10:
        features["temp_mean"] = mean(temp_values[-10:])
    else:
        features["temp_mean"] = temp_values[-1]

    # Rolling std (vibration)
    if len(vib_values) >= 10:
        features["vib_std"] = pstdev(vib_values[-10:])
    else:
        features["vib_std"] = 0

    # Pressure rate of change
    if len(pres_values) >= 2:
        features["pressure_rate"] = pres_values[-1] - pres_values[-2]
    else:
        features["pressure_rate"] = 0

    return features


# ----------- Main Handler -----------

def handle_raw_event(ch, method, properties, body):
    data = json.loads(body)

    global message_count
    message_count += 1

    sensor_id = data["machine_id"]

    temp = data["temperature"]
    vib = data["vibration"]
    pres = data.get("pressure", 1.0)  # fallback if missing

    # Store in buffer
    sensor_buffers[sensor_id]["temperature"].append(temp)
    sensor_buffers[sensor_id]["vibration"].append(vib)
    sensor_buffers[sensor_id]["pressure"].append(pres)

    # Normalize
    norm_temp = z_score_normalize(temp, sensor_buffers[sensor_id]["temperature"])
    norm_vib = z_score_normalize(vib, sensor_buffers[sensor_id]["vibration"])
    norm_pres = z_score_normalize(pres, sensor_buffers[sensor_id]["pressure"])

    # Features
    features = compute_features(sensor_id)

    cleaned_event = {
        "machine_id": sensor_id,
        "temperature": norm_temp,
        "vibration": norm_vib,
        "pressure": norm_pres,
        "features": features
    }

    if message_count % 10 == 0:
        logger.info(f"Processed message {message_count} for sensor {sensor_id}, features: {features}")

    if message_count % 100 == 0:
        total_sensors = len(sensor_buffers)
        buffer_stats = {}
        for sid, buffers in sensor_buffers.items():
            buffer_stats[sid] = {k: len(v) for k, v in buffers.items()}
        logger.info(f"Statistics: Total messages processed: {message_count}, Sensors: {total_sensors}, Buffer sizes: {buffer_stats}")

    print("Cleaned Event:", cleaned_event)

    # Publish cleaned data
    client.publish("sensor.cleaned", cleaned_event)


# ----------- Start Consumer -----------

def start():
    logger.info("Data adapter started, listening on sensor.raw")
    client.subscribe("sensor.raw", handle_raw_event)


if __name__ == "__main__":
    start()