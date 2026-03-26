"""RUL model optimization and profiling utility.

Provides:
- Model profiling (inference time, memory usage)
- TensorFlow Lite conversion + quantization
- Size reduction analysis
- Performance comparison (original vs. optimized)

Usage:
    python -m services.predictive_maintenance.rul_prediction.rul_model_optimizer
"""

import time
import pickle
import numpy as np
from pathlib import Path
from typing import Tuple

MODEL_PATH = Path(__file__).parent.parent / "model_registry" / "rul_lstm.h5"
SCALER_PATH = Path(__file__).parent.parent / "model_registry" / "scaler.pkl"

# Output paths for optimized models
TFLite_PATH = Path(__file__).parent.parent / "model_registry" / "rul_lstm_quantized.tflite"


def profile_original_model(num_runs: int = 100) -> dict:
    """Profile the original TensorFlow H5 model.
    
    Args:
        num_runs: Number of inference runs to average
        
    Returns:
        dict with metrics: inference_time_ms, memory_usage_mb, etc.
    """
    print("[PROFILE] Loading original H5 model...")
    try:
        from tensorflow.keras.models import load_model
        import tensorflow as tf
    except ImportError:
        print("❌ TensorFlow not installed. Skipping original model profiling.")
        return {}
    
    if not MODEL_PATH.exists():
        print(f"❌ Model not found at {MODEL_PATH}")
        return {}
    
    model = load_model(MODEL_PATH, compile=False)
    
    # Load scaler
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    
    # Create dummy input (1, 50 timesteps, 14 features - adjust based on actual model)
    # Get actual feature count from model input shape
    input_shape = model.input_shape
    print(f"  Model input shape: {input_shape}")
    
    n_features = input_shape[-1] if len(input_shape) > 2 else 14
    dummy_input = np.random.randn(1, 50, n_features).astype(np.float32)
    
    # Warm up
    _ = model.predict(dummy_input, verbose=0)
    
    # Profile
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        _ = model.predict(dummy_input, verbose=0)
        times.append((time.perf_counter() - start) * 1000)  # Convert to ms
    
    avg_time = np.mean(times)
    std_time = np.std(times)
    p95_time = np.percentile(times, 95)
    
    model_size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
    
    print(f"✅ Original Model Profiling ({num_runs} runs):")
    print(f"  Avg inference: {avg_time:.2f}ms ± {std_time:.2f}ms")
    print(f"  P95 inference: {p95_time:.2f}ms")
    print(f"  Model size: {model_size_mb:.2f}MB")
    
    return {
        "framework": "TensorFlow H5",
        "avg_time_ms": avg_time,
        "std_time_ms": std_time,
        "p95_time_ms": p95_time,
        "model_size_mb": model_size_mb,
    }


def convert_to_tflite_quantized() -> Tuple[str, float]:
    """Convert H5 model to TensorFlow Lite with int8 quantization.
    
    Returns:
        Tuple of (output_path, file_size_mb)
    """
    print("\n[CONVERT] Converting to TensorFlow Lite (int8 quantization)...")
    try:
        from tensorflow.keras.models import load_model
        import tensorflow as tf
    except ImportError:
        print("❌ TensorFlow not installed. Cannot convert.")
        return "", 0.0
    
    if not MODEL_PATH.exists():
        print(f"❌ Model not found at {MODEL_PATH}")
        return "", 0.0
    
    model = load_model(MODEL_PATH, compile=False)
    
    # Convert to TFLite with dynamic range quantization (integer friendly)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    
    # Dynamic range quantization (works without representative_dataset)
    # This will use int8 where possible, float16 where necessary
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS
    ]
    
    print("  Quantizing model...")
    tflite_model = converter.convert()
    
    # Save
    TFLite_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TFLite_PATH, "wb") as f:
        f.write(tflite_model)
    
    file_size_mb = TFLite_PATH.stat().st_size / (1024 * 1024)
    print(f"✅ Saved TFLite model to: {TFLite_PATH}")
    print(f"   File size: {file_size_mb:.2f}MB")
    
    return str(TFLite_PATH), file_size_mb


def profile_tflite_model(tflite_path: str, num_runs: int = 100) -> dict:
    """Profile TensorFlow Lite model.
    
    Args:
        tflite_path: Path to .tflite model
        num_runs: Number of inference runs
        
    Returns:
        dict with metrics
    """
    print(f"\n[PROFILE] Profiling TFLite model from {tflite_path}...")
    try:
        import tensorflow as tf
    except ImportError:
        print("❌ TensorFlow not installed.")
        return {}
    
    # Load TFLite interpreter
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()
    
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    print(f"  Input shape: {input_details[0]['shape']}")
    print(f"  Output shape: {output_details[0]['shape']}")
    
    # Create dummy input matching exact shape
    input_shape = input_details[0]['shape']
    dummy_input = np.random.randn(*input_shape).astype(np.float32)
    
    # Warm up
    interpreter.set_tensor(input_details[0]['index'], dummy_input)
    _ = interpreter.invoke()
    
    # Profile
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        interpreter.set_tensor(input_details[0]['index'], dummy_input)
        _ = interpreter.invoke()
        times.append((time.perf_counter() - start) * 1000)  # ms
    
    avg_time = np.mean(times)
    std_time = np.std(times)
    p95_time = np.percentile(times, 95)
    
    file_size_mb = Path(tflite_path).stat().st_size / (1024 * 1024)
    
    print(f"✅ TFLite Profiling ({num_runs} runs):")
    print(f"  Avg inference: {avg_time:.2f}ms ± {std_time:.2f}ms")
    print(f"  P95 inference: {p95_time:.2f}ms")
    print(f"  Model size: {file_size_mb:.2f}MB")
    
    return {
        "framework": "TensorFlow Lite (int8)",
        "avg_time_ms": avg_time,
        "std_time_ms": std_time,
        "p95_time_ms": p95_time,
        "model_size_mb": file_size_mb,
    }


def print_optimization_report(original: dict, optimized: dict):
    """Print before/after optimization comparison."""
    print("\n" + "="*70)
    print("OPTIMIZATION REPORT")
    print("="*70)
    
    if not original:
        print("❌ Could not profile original model (TensorFlow not available)")
        return
    
    if not optimized:
        print("❌ Could not profile optimized model")
        return
    
    size_reduction = (1 - optimized["model_size_mb"] / original["model_size_mb"]) * 100
    speed_factor = original["avg_time_ms"] / optimized["avg_time_ms"]
    
    print(f"\n📊 Original Model:")
    print(f"  Framework: {original['framework']}")
    print(f"  Inference time (avg): {original['avg_time_ms']:.2f} ms")
    print(f"  Inference time (p95): {original['p95_time_ms']:.2f} ms")
    print(f"  Model size: {original['model_size_mb']:.3f} MB")
    
    print(f"\n📊 Optimized Model:")
    print(f"  Framework: {optimized['framework']}")
    print(f"  Inference time (avg): {optimized['avg_time_ms']:.2f} ms")
    print(f"  Inference time (p95): {optimized['p95_time_ms']:.2f} ms")
    print(f"  Model size: {optimized['model_size_mb']:.3f} MB")
    
    print(f"\n✨ Improvements:")
    print(f"  Model size reduction: {size_reduction:.1f}%")
    print(f"  Speed improvement: {speed_factor:.1f}x faster")
    
    target_ms = 50.0
    if optimized["avg_time_ms"] <= target_ms:
        status = "✅ MEETS TARGET"
    else:
        remaining = optimized["avg_time_ms"] - target_ms
        status = f"⚠️  {remaining:.1f}ms over target"
    
    print(f"  Target (<50ms): {optimized['avg_time_ms']:.2f}ms → {status}")
    
    print("\n" + "="*70)


def main():
    """Run full optimization pipeline."""
    print("RUL Model Optimization Pipeline")
    print("="*70)
    
    # Profile original
    original_metrics = profile_original_model(num_runs=100)
    
    # Convert to TFLite
    tflite_path, tflite_size = convert_to_tflite_quantized()
    
    if tflite_path:
        # Profile TFLite
        optimized_metrics = profile_tflite_model(tflite_path, num_runs=100)
        
        # Print report
        print_optimization_report(original_metrics, optimized_metrics)
    else:
        print("\n⚠️  Optimization conversion failed. Check TensorFlow installation.")


if __name__ == "__main__":
    main()
