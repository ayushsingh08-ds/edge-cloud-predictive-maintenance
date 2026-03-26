"""Lightweight RUL inference profiling - works with minimal dependencies.

Profiles inference speed of available models without requiring TensorFlow
for data processing (only needs numpy for dummy input generation).

Usage:
    python -m services.predictive_maintenance.rul_prediction.rul_profile_lite
"""

import time
import pickle
import numpy as np
from pathlib import Path
from typing import Optional, Tuple

MODEL_DIR = Path(__file__).parent.parent / "model_registry"
SCALER_PATH = MODEL_DIR / "scaler.pkl"


def profile_tflite_lite(
    tflite_path: str, num_runs: int = 100, verbose: bool = True
) -> Optional[dict]:
    """Profile TFLite model without external deps (only TensorFlow Lite needed).
    
    Args:
        tflite_path: Path to .tflite model
        num_runs: Number of inference runs
        verbose: Print results
        
    Returns:
        dict with timing stats or None if failed
    """
    try:
        import tensorflow as tf
    except ImportError:
        print("❌ TensorFlow not installed. Cannot profile TFLite.")
        return None
    
    tflite_path = Path(tflite_path)
    if not tflite_path.exists():
        print(f"❌ Model not found: {tflite_path}")
        return None
    
    try:
        # Load interpreter
        interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
        interpreter.allocate_tensors()
        
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        input_shape = input_details[0]["shape"]
        
        if verbose:
            print(f"📊 TFLite Model: {tflite_path.name}")
            print(f"   Input shape: {input_shape}")
            print(f"   File size: {tflite_path.stat().st_size / 1024:.1f} KB")
        
        # Create dummy input
        dummy_input = np.random.randn(*input_shape).astype(np.float32)
        
        # Warm up (2 runs)
        for _ in range(2):
            interpreter.set_tensor(input_details[0]["index"], dummy_input)
            _ = interpreter.invoke()
        
        # Profile
        times = []
        for _ in range(num_runs):
            start = time.perf_counter()
            interpreter.set_tensor(input_details[0]["index"], dummy_input)
            _ = interpreter.invoke()
            times.append((time.perf_counter() - start) * 1000)  # ms
        
        times = np.array(times)
        stats = {
            "model_type": "tflite",
            "file_size_kb": tflite_path.stat().st_size / 1024,
            "num_runs": num_runs,
            "avg_ms": float(np.mean(times)),
            "std_ms": float(np.std(times)),
            "min_ms": float(np.min(times)),
            "max_ms": float(np.max(times)),
            "p50_ms": float(np.percentile(times, 50)),
            "p95_ms": float(np.percentile(times, 95)),
            "p99_ms": float(np.percentile(times, 99)),
        }
        
        if verbose:
            print(f"   Runs: {num_runs}")
            print(f"   Avg: {stats['avg_ms']:.2f} ms ± {stats['std_ms']:.2f}")
            print(f"   Range: {stats['min_ms']:.2f} - {stats['max_ms']:.2f} ms")
            print(f"   P50: {stats['p50_ms']:.2f} ms")
            print(f"   P95: {stats['p95_ms']:.2f} ms")
            print(f"   P99: {stats['p99_ms']:.2f} ms")
            
            if stats['avg_ms'] < 50:
                print(f"   ✅ Meets <50ms target")
            else:
                print(f"   ⚠️  {stats['avg_ms'] - 50:.1f}ms over target")
        
        return stats
        
    except Exception as e:
        print(f"❌ Profiling failed: {e}")
        return None


def profile_h5_keras(h5_path: str, num_runs: int = 100, verbose: bool = True) -> Optional[dict]:
    """Profile TensorFlow H5 model.
    
    Args:
        h5_path: Path to .h5 model
        num_runs: Number of inference runs
        verbose: Print results
        
    Returns:
        dict with timing stats or None if failed
    """
    try:
        from tensorflow.keras.models import load_model
    except ImportError:
        print("❌ TensorFlow not installed. Cannot profile H5.")
        return None
    
    h5_path = Path(h5_path)
    if not h5_path.exists():
        print(f"❌ Model not found: {h5_path}")
        return None
    
    try:
        model = load_model(h5_path)
        
        if verbose:
            print(f"📊 H5 Model: {h5_path.name}")
            print(f"   Input shape: {model.input_shape}")
            print(f"   File size: {h5_path.stat().st_size / 1024:.1f} KB")
        
        # Create dummy input
        dummy_input = np.random.randn(*model.input_shape).astype(np.float32)
        
        # Warm up
        for _ in range(2):
            _ = model.predict(dummy_input, verbose=0)
        
        # Profile
        times = []
        for _ in range(num_runs):
            start = time.perf_counter()
            _ = model.predict(dummy_input, verbose=0)
            times.append((time.perf_counter() - start) * 1000)  # ms
        
        times = np.array(times)
        stats = {
            "model_type": "h5",
            "file_size_kb": h5_path.stat().st_size / 1024,
            "num_runs": num_runs,
            "avg_ms": float(np.mean(times)),
            "std_ms": float(np.std(times)),
            "min_ms": float(np.min(times)),
            "max_ms": float(np.max(times)),
            "p50_ms": float(np.percentile(times, 50)),
            "p95_ms": float(np.percentile(times, 95)),
            "p99_ms": float(np.percentile(times, 99)),
        }
        
        if verbose:
            print(f"   Runs: {num_runs}")
            print(f"   Avg: {stats['avg_ms']:.2f} ms ± {stats['std_ms']:.2f}")
            print(f"   Range: {stats['min_ms']:.2f} - {stats['max_ms']:.2f} ms")
            print(f"   P50: {stats['p50_ms']:.2f} ms")
            print(f"   P95: {stats['p95_ms']:.2f} ms")
            print(f"   P99: {stats['p99_ms']:.2f} ms")
            
            if stats['avg_ms'] < 50:
                print(f"   ✅ Meets <50ms target")
            else:
                print(f"   ⚠️  {stats['avg_ms'] - 50:.1f}ms over target")
        
        return stats
        
    except Exception as e:
        print(f"❌ Profiling failed: {e}")
        return None


def compare_models(
    tflite_stats: Optional[dict], h5_stats: Optional[dict], verbose: bool = True
) -> None:
    """Compare profiling results between TFLite and H5 models."""
    
    if not tflite_stats and not h5_stats:
        print("❌ No models available to compare")
        return
    
    print("\n" + "=" * 70)
    print("INFERENCE PERFORMANCE COMPARISON")
    print("=" * 70)
    
    if h5_stats:
        print(f"\n📊 H5 Model:")
        print(f"   Size: {h5_stats['file_size_kb']:.1f} KB")
        print(f"   Inference: {h5_stats['avg_ms']:.2f} ms (avg)")
    
    if tflite_stats:
        print(f"\n📊 TFLite Quantized Model:")
        print(f"   Size: {tflite_stats['file_size_kb']:.1f} KB")
        print(f"   Inference: {tflite_stats['avg_ms']:.2f} ms (avg)")
    
    if tflite_stats and h5_stats:
        size_ratio = h5_stats['file_size_kb'] / tflite_stats['file_size_kb']
        speed_ratio = h5_stats['avg_ms'] / tflite_stats['avg_ms']
        size_reduction = (1 - tflite_stats['file_size_kb'] / h5_stats['file_size_kb']) * 100
        
        print(f"\n✨ Improvements:")
        print(f"   Size reduction: {size_reduction:.1f}% ({size_ratio:.1f}x smaller)")
        print(f"   Speed improvement: {speed_ratio:.1f}x faster")
        
        if tflite_stats['avg_ms'] < 50:
            print(f"   Target (<50ms): ✅ ACHIEVED")
        else:
            print(f"   Target (<50ms): ⚠️  MISS by {tflite_stats['avg_ms'] - 50:.1f}ms")
    
    print("\n" + "=" * 70)


def main():
    """Run profiling on available models."""
    print("RUL Model Profiling (Lightweight)")
    print("=" * 70)
    
    h5_path = MODEL_DIR / "rul_lstm.h5"
    tflite_path = MODEL_DIR / "rul_lstm_quantized.tflite"
    
    # Profile available models
    h5_stats = None
    if h5_path.exists():
        print(f"\nProfiling H5 model (100 runs)...\n")
        h5_stats = profile_h5_keras(str(h5_path), num_runs=100)
    else:
        print(f"\n⚠️  H5 model not found: {h5_path}")
    
    tflite_stats = None
    if tflite_path.exists():
        print(f"\nProfiling TFLite model (100 runs)...\n")
        tflite_stats = profile_tflite_lite(str(tflite_path), num_runs=100)
    else:
        print(f"\n⚠️  TFLite model not found: {tflite_path}")
        print(
            "   Generate with: "
            "python -m services.predictive_maintenance.rul_prediction.rul_model_optimizer"
        )
    
    # Compare
    compare_models(tflite_stats, h5_stats)


if __name__ == "__main__":
    main()
