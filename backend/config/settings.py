"""
Global configuration for Predictive Maintenance System.
All thresholds and operational constants are defined here.
"""

from config.env import API_HOST as ENV_API_HOST, API_PORT as ENV_API_PORT, DATABASE_URL as ENV_DATABASE_URL


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


# ============================================================
# Environment-backed Runtime Configuration
# ============================================================

API_HOST = ENV_API_HOST or "0.0.0.0"
API_PORT = int(ENV_API_PORT) if ENV_API_PORT else 8000
DATABASE_URL = ENV_DATABASE_URL or "sqlite:///./data/smart_factory_dev.db"