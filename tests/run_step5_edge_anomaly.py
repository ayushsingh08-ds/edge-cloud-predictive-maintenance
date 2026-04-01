from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.edge.anomaly import EdgeAnomalyDetector
from services.edge.sensor_stream import generate_sensor_stream


def main() -> None:
    detector = EdgeAnomalyDetector(
        contamination=0.06,
        warmup_samples=35,
        sustained_threshold=3,
    )

    stream = generate_sensor_stream(
        duration_seconds=600,
        sample_period_seconds=2.0,
        num_machines=4,
        seed=11,
        anomaly_probability=0.07,
    )

    anomaly_events = 0
    sustained_alerts = 0
    warmup_events = 0

    for record in stream:
        result = detector.process(record, publish_alerts=False)
        if result["status"] == "warmup":
            warmup_events += 1
            continue
        if result["is_anomaly"]:
            anomaly_events += 1
        if result["sustained_anomaly"]:
            sustained_alerts += 1

    print("STEP 5 - Edge Anomaly Detection")
    print("records_processed:", len(stream))
    print("warmup_events:", warmup_events)
    print("anomaly_events:", anomaly_events)
    print("sustained_alerts:", sustained_alerts)


if __name__ == "__main__":
    main()
