"""
Centralized topic definitions for Event Bus routing.
All services must use these constants.
"""

# ============================================================
# Sensor Topics
# ============================================================

SENSOR_RAW = "sensor.raw"              # Raw telemetry from edge
SENSOR_CLEANED = "sensor.cleaned"      # Normalized / preprocessed telemetry


# ============================================================
# Edge Intelligence
# ============================================================

EDGE_ANOMALY = "edge.anomaly"          # Anomaly detected at edge


# ============================================================
# Cloud Intelligence
# ============================================================

CLOUD_RUL = "cloud.rul"                # RUL prediction from cloud model


# ============================================================
# Monitoring & MLOps
# ============================================================

DRIFT_ALERT = "drift.alert"            # Data/model drift detected
MODEL_UPDATE = "model.update"          # New model deployed


# ============================================================
# Business Actions
# ============================================================

MAINTENANCE_ALERT = "maintenance.alert"  # Maintenance required