from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.edge.anomaly import EdgeAnomalyDetector
from services.edge.sensor_stream import SensorRecord


def test_step5_anomaly_pipeline_runs() -> None:
    detector = EdgeAnomalyDetector(
        contamination=0.08,
        warmup_samples=15,
        sustained_threshold=2,
    )

    # Warmup with mostly normal points.
    for i in range(20):
        detector.process(
            SensorRecord(
                timestamp=float(i),
                machine_id=0,
                temperature=68.0,
                vibration=0.42,
                pressure=100.0,
            ),
            publish_alerts=False,
        )

    flagged = 0
    for i in range(8):
        result = detector.process(
            SensorRecord(
                timestamp=30.0 + i,
                machine_id=0,
                temperature=91.0,
                vibration=1.02,
                pressure=132.0,
            ),
            publish_alerts=False,
        )
        if result["is_anomaly"]:
            flagged += 1

    assert flagged > 0
