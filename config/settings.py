"""
Global configuration for Predictive Maintenance System.
All thresholds and operational constants are defined here.
"""


# ============================================================
# Anomaly Detection
# ============================================================

ANOMALY_THRESHOLD = 0.7        # Score above this is considered anomaly


# ============================================================
# RUL Thresholds (in hours)
# ============================================================

RUL_CRITICAL_HOURS = 24        # Immediate maintenance required
RUL_WARNING_HOURS = 72         # Schedule maintenance soon


# ============================================================
# Drift Detection
# ============================================================

DRIFT_WINDOW_SIZE = 1000       # Number of recent samples to monitor
DRIFT_THRESHOLD = 0.3          # Statistical distance threshold