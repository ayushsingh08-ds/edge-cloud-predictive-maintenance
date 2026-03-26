"""Optimized RUL inference with TensorFlow Lite fallback.

Supports both:
1. TensorFlow Lite (quantized) - ~10x smaller, fast inference
2. Original H5 model - fallback if TFLite not available

Automatically selects the best available model.
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path
from typing import Tuple


import numpy as np


MODEL_DIR = Path(__file__).parent.parent / "model_registry"
H5_MODEL_PATH = MODEL_DIR / "rul_lstm.h5"
TFLITE_MODEL_PATH = MODEL_DIR / "rul_lstm_quantized.tflite"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
BENCHMARK_PATH = MODEL_DIR / "rul_benchmark.json"

# Cached artifacts
_MODEL = None
_SCALER = None
_INTERPRETER = None
_INPUT_DETAILS = None
_OUTPUT_DETAILS = None
_MODEL_TYPE = None  # "h5" or "tflite"

# Health thresholds in hours
HEALTHY_HOURS = 72.0
WARNING_HOURS = 24.0


def _status_from_hours(hours: float) -> str:
    """Map predicted RUL to health status."""
    if hours >= HEALTHY_HOURS:
        return "healthy"
    if hours >= WARNING_HOURS:
        return "warning"
    return "critical"


def _confidence_from_hours(hours: float) -> float:
    """Heuristic confidence based on distance from decision boundaries."""
    distance = min(abs(hours - WARNING_HOURS), abs(hours - HEALTHY_HOURS))
    confidence = 0.50 + min(distance / 96.0, 0.49)
    return float(np.clip(confidence, 0.50, 0.99))


def _load_tflite_model():
    """Load TensorFlow Lite quantized model."""
    global _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS, _MODEL_TYPE
    
    if not TFLITE_MODEL_PATH.exists():
        return False
    
    try:
        import tensorflow as tf
    except ImportError:
        return False
    
    try:
        _INTERPRETER = tf.lite.Interpreter(model_path=str(TFLITE_MODEL_PATH))
        _INTERPRETER.allocate_tensors()
        _INPUT_DETAILS = _INTERPRETER.get_input_details()
        _OUTPUT_DETAILS = _INTERPRETER.get_output_details()
        _MODEL_TYPE = "tflite"
        return True
    except Exception:
        return False


def _load_h5_model():
    """Load original TensorFlow H5 model."""
    global _MODEL, _MODEL_TYPE
    
    if not H5_MODEL_PATH.exists():
        return False
    
    try:
        from tensorflow.keras.models import load_model
    except ImportError:
        return False
    
    try:
        _MODEL = load_model(H5_MODEL_PATH, compile=False)
        _MODEL_TYPE = "h5"
        return True
    except Exception:
        return False


def _load_scaler():
    """Load feature scaler."""
    global _SCALER
    
    if _SCALER is not None:
        return True
    
    if not SCALER_PATH.exists():
        return False
    
    try:
        with open(SCALER_PATH, "rb") as f:
            _SCALER = pickle.load(f)
        return True
    except Exception:
        return False


def initialize_models() -> Tuple[bool, str]:
    """Initialize and load models, preferring TFLite.
    
    Returns:
        (success, model_type_used)
    """
    global _MODEL_TYPE
    
    # Try TFLite first (preferred)
    if _load_tflite_model():
        if not _load_scaler():
            return False, "Error: Scaler not loaded"
        return True, "TensorFlow Lite (Quantized)"
    
    # Fallback to H5
    if _load_h5_model():
        if not _load_scaler():
            return False, "Error: Scaler not loaded"
        return True, "TensorFlow H5"
    
    return False, "Error: No model loaded"


def predict_rul_optimized(sequence: np.ndarray | list) -> Tuple[float, float, str, dict]:
    """Predict RUL with inference timing info.
    
    Args:
        sequence: Shape (50, features) or (1, 50, features)
    
    Returns:
        (hours, confidence, status, metadata)
        metadata contains: inference_ms, model_type, etc.
    """
    # Ensure models are loaded
    if _MODEL_TYPE is None:
        success, msg = initialize_models()
        if not success:
            raise RuntimeError(msg)
    
    arr = np.asarray(sequence, dtype=np.float32)
    
    # Reshape to 3D (1, timesteps, features)
    if arr.ndim == 2:
        arr = np.expand_dims(arr, axis=0)
    elif arr.ndim != 3 or arr.shape[0] != 1:
        raise ValueError(f"Expected shape (50, features), got {arr.shape}")
    
    if arr.shape[1] != 50:
        raise ValueError(f"Expected 50 timesteps, got {arr.shape[1]}")
    
    # Scale features
    n_features = arr.shape[2]
    arr_scaled = _SCALER.transform(arr.reshape(-1, n_features)).reshape(1, 50, n_features)
    
    # Predict with timing
    start_time = time.perf_counter()
    
    if _MODEL_TYPE == "tflite":
        # TFLite inference
        _INTERPRETER.set_tensor(_INPUT_DETAILS[0]["index"], arr_scaled)
        _INTERPRETER.invoke()
        pred = _INTERPRETER.get_tensor(_OUTPUT_DETAILS[0]["index"])
    else:
        # H5 inference
        pred = _MODEL.predict(arr_scaled, verbose=0)
    
    inference_ms = (time.perf_counter() - start_time) * 1000
    
    hours = float(max(0.0, float(pred.reshape(-1)[0])))
    status = _status_from_hours(hours)
    confidence = _confidence_from_hours(hours)
    
    metadata = {
        "inference_ms": round(inference_ms, 3),
        "model_type": _MODEL_TYPE,
        "status": status,
    }
    
    return hours, confidence, status, metadata


def predict_rul(sequence: np.ndarray | list) -> Tuple[float, float, str]:
    """Original signature for backward compatibility.
    
    Delegates to optimized version but only returns (hours, confidence, status).
    """
    hours, confidence, status, _ = predict_rul_optimized(sequence)
    return hours, confidence, status


def get_model_info() -> dict:
    """Return current model configuration and performance info."""
    if _MODEL_TYPE is None:
        initialize_models()
    
    if _MODEL_TYPE == "tflite":
        size_bytes = TFLITE_MODEL_PATH.stat().st_size if TFLITE_MODEL_PATH.exists() else 0
    else:
        size_bytes = H5_MODEL_PATH.stat().st_size if H5_MODEL_PATH.exists() else 0
    
    info = {
        "model_type": _MODEL_TYPE or "not_loaded",
        "model_size_kb": size_bytes / 1024,
        "h5_available": H5_MODEL_PATH.exists(),
        "tflite_available": TFLITE_MODEL_PATH.exists(),
        "scaler_available": SCALER_PATH.exists(),
    }
    
    # Add benchmark if available
    if BENCHMARK_PATH.exists():
        try:
            with open(BENCHMARK_PATH, "r") as f:
                info["benchmark"] = json.load(f)
        except Exception:
            pass
    
    return info


if __name__ == "__main__":
    # Demo: Show model info and perform sample inference
    info = get_model_info()
    print("RUL Model Configuration:")
    print(f"  Active model: {info['model_type']}")
    print(f"  Size: {info['model_size_kb']:.1f} KB")
    print(f"  H5 available: {info['h5_available']}")
    print(f"  TFLite available: {info['tflite_available']}")
    
    if info.get("benchmark"):
        print(f"\nBenchmark (100 runs):")
        benchmark = info["benchmark"]
        for key, val in benchmark.items():
            if key.endswith("_ms"):
                print(f"  {key}: {val:.2f}")
