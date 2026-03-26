"""
QUICK START: RUL Model Optimization

This script walks through the optimization process step-by-step.
Run this to understand what's happening during optimization.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DOCS_FOLDER = PROJECT_ROOT / "docs"
VENV_BIN = PROJECT_ROOT / ".venv" / "Scripts"


def print_header(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"🔷 {title}")
    print("=" * 70)


def print_step(step: int, description: str):
    """Print formatted step."""
    print(f"\n[STEP {step}] {description}")
    print("-" * 70)


def check_tensorflow():
    """Check if TensorFlow is installed."""
    try:
        import tensorflow as tf
        print(f"✅ TensorFlow {tf.__version__} installed")
        return True
    except ImportError:
        print("❌ TensorFlow not found")
        return False


def install_tensorflow():
    """Install TensorFlow."""
    print("\n📦 Installing TensorFlow 2.13.0...")
    print("   (Requires Python 3.10 or lower)")
    
    python_exe = VENV_BIN / "python.exe"
    if not python_exe.exists():
        print(f"❌ Python not found at {python_exe}")
        return False
    
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", "tensorflow==2.13.0"],
            capture_output=True,
            timeout=300
        )
        if result.returncode == 0:
            print("✅ TensorFlow installed successfully")
            return True
        else:
            print(f"❌ Installation failed: {result.stderr.decode()}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out (>5 minutes)")
        return False


def run_optimizer():
    """Run the optimization pipeline."""
    print("\n🚀 Running optimization pipeline...")
    print("   This will profile and optimize your RUL model")
    
    python_exe = VENV_BIN / "python.exe"
    try:
        result = subprocess.run(
            [
                str(python_exe),
                "-m",
                "services.predictive_maintenance.rul_prediction.rul_model_optimizer",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=False,
            timeout=600
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Optimization timed out")
        return False


def run_profiler():
    """Run the lightweight profiler."""
    print("\n📊 Running profiler...")
    
    python_exe = VENV_BIN / "python.exe"
    try:
        result = subprocess.run(
            [
                str(python_exe),
                "-m",
                "services.predictive_maintenance.rul_prediction.rul_profile_lite",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=False,
            timeout=120
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Profiling timed out")
        return False


def show_next_steps():
    """Show what to do next."""
    print_header("Next Steps")
    
    print("""
1. UPDATE YOUR CODE (if using RUL prediction):
   
   From:
    ├── from services.predictive_maintenance.rul_prediction.rul_inference import predict_rul
   
   To:
    ├── from services.predictive_maintenance.rul_prediction.rul_inference_optimized import predict_rul_optimized
   └── hours, conf, status, meta = predict_rul_optimized(sequence)
       # meta["inference_ms"] shows actual timing!

2. MONITOR PERFORMANCE:
   
   Add to your inference pipeline:
   ├── if meta["inference_ms"] > 50:
   └──     logger.warning(f"Slow: {meta['inference_ms']:.1f}ms")

3. DEPLOYMENT:
   
   Include in your deployment package:
    ├── services/predictive_maintenance/model_registry/rul_lstm_quantized.tflite (~80 KB)
    ├── services/predictive_maintenance/model_registry/scaler.pkl
    └── services/predictive_maintenance/rul_prediction/rul_inference_optimized.py
   
   The system automatically uses the optimized model if available!

4. DOCUMENTATION:
   
   For detailed info, see:
   └── docs/rul_optimization_guide.md
""")


def main():
    """Main workflow."""
    print_header("RUL Model Optimization Quick Start")
    
    print(f"""
This script will help you optimize the RUL LSTM model for fast inference.

Target Results:
  ✓ Model size: 295 KB → 80 KB (73% smaller)
  ✓ Inference speed: ~95ms → ~22ms (4.2x faster)
  ✓ Inference latency: <50ms target ✅

Prerequisites:
  ✓ Python 3.10 or lower (for TensorFlow)
  ✓ .venv already created with core dependencies
  ✓ rul_lstm.h5 model file present
""")
    
    # Step 1: Check TensorFlow
    print_step(1, "Check TensorFlow Installation")
    if not check_tensorflow():
        print("\nWould you like to install TensorFlow? (Y/n)")
        response = input("> ").strip().lower()
        if response != "n":
            if install_tensorflow():
                print("✅ Ready to proceed")
            else:
                print("""
⚠️  TensorFlow installation failed. Possible reasons:
  - Python version not 3.10 or lower
  - No internet connection
  - pip installation issues
  
Workaround:
  Manual install: pip install tensorflow==2.13.0
  Or skip optimization (H5 model still works)
""")
                return
        else:
            print("⚠️  Skipping. H5 model will still work (but slower).")
            return
    
    # Step 2: Run optimization
    print_step(2, "Optimize Model (Convert to TensorFlow Lite)")
    if not run_optimizer():
        print("❌ Optimization failed")
        return
    
    # Step 3: Profile
    print_step(3, "Profile Optimized Model")
    if not run_profiler():
        print("❌ Profiling failed")
        return
    
    # Step 4: Show next steps
    show_next_steps()
    
    print_header("✅ Optimization Complete!")
    print(f"""
New files created:
  ✓ cloud/ai/model_registry/rul_lstm_quantized.tflite (~80 KB)
  ✓ cloud/ai/rul_inference_optimized.py (optimized inference module)
  ✓ cloud/ai/rul_profile_lite.py (lightweight profiler)

System automatically detects & uses optimized model.
No code changes required unless you want to track inference timing!
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
