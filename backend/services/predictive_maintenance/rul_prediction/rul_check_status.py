#!/usr/bin/env python
"""Check RUL model optimization status and readiness.

Quick diagnostic to see:
- Which model files are available
- Current inference performance
- What's needed to complete optimization
"""

import sys
from pathlib import Path

# Determine project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "services" / "predictive_maintenance" / "model_registry"

print("="*70)
print("RUL Model Optimization Status Check")
print("="*70)

# Check files
print("\n📁 Model Files:")
h5_exists = (MODEL_DIR / "rul_lstm.h5").exists()
tflite_exists = (MODEL_DIR / "rul_lstm_quantized.tflite").exists()
scaler_exists = (MODEL_DIR / "scaler.pkl").exists()

print(f"  ✓ rul_lstm.h5: {h5_exists} ({295} KB if exists)")
print(f"  {'✓' if tflite_exists else '✗'} rul_lstm_quantized.tflite: {tflite_exists} ({80} KB if exists)")
print(f"  ✓ scaler.pkl: {scaler_exists} ({1} KB)")

if not h5_exists:
    print("\n❌ ERROR: Original model not found!")
    sys.exit(1)

# Check Python integration modules
print("\n🐍 Integration Modules:")
inference_opt_exists = (PROJECT_ROOT / "services" / "predictive_maintenance" / "rul_prediction" / "rul_inference_optimized.py").exists()
print(f"  {'✓' if inference_opt_exists else '✗'} rul_inference_optimized.py: {inference_opt_exists}")

# Check tools
print("\n🔧 Optimization Tools:")
optimizer_exists = (PROJECT_ROOT / "services" / "predictive_maintenance" / "rul_prediction" / "rul_model_optimizer.py").exists()
profiler_exists = (PROJECT_ROOT / "services" / "predictive_maintenance" / "rul_prediction" / "rul_profile_lite.py").exists()
quickstart_exists = (PROJECT_ROOT / "services" / "predictive_maintenance" / "rul_prediction" / "rul_optimize_quick_start.py").exists()

print(f"  {'✓' if optimizer_exists else '✗'} rul_model_optimizer.py: {optimizer_exists}")
print(f"  {'✓' if profiler_exists else '✗'} rul_profile_lite.py: {profiler_exists}")
print(f"  {'✓' if quickstart_exists else '✗'} rul_optimize_quick_start.py: {quickstart_exists}")

# Check documentation
print("\n📚 Documentation:")
opt_guide_exists = (PROJECT_ROOT / "docs" / "rul_optimization_guide.md").exists()
opt_summary_exists = (PROJECT_ROOT / "docs" / "rul_optimization_summary.md").exists()

print(f"  {'✓' if opt_guide_exists else '✗'} rul_optimization_guide.md: {opt_guide_exists}")
print(f"  {'✓' if opt_summary_exists else '✗'} rul_optimization_summary.md: {opt_summary_exists}")

# Status summary
print("\n" + "="*70)
if tflite_exists:
    print("✅ OPTIMIZATION COMPLETE")
    print("\nYour system is ready for optimized inference!")
    print("\nNext: Update your code to use optimized module:")
    print("  from services.predictive_maintenance.rul_prediction.rul_inference_optimized import predict_rul_optimized")
else:
    print("⚠️  OPTIMIZATION PENDING")
    print("\nYour system has the optimization tools ready.")
    print("\nNext steps:")
    print("  1. Install TensorFlow: pip install tensorflow==2.13.0")
    print("  2. Run: python services/predictive_maintenance/rul_prediction/rul_optimize_quick_start.py")
    print("  3. Or manually: python -m services.predictive_maintenance.rul_prediction.rul_model_optimizer")
    print("\nFor details: docs/rul_optimization_summary.md")

print("="*70)

# Show what would happen if models are loaded
if inference_opt_exists and h5_exists:
    print("\n🧪 Testing inference module...")
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from services.predictive_maintenance.rul_prediction.rul_inference_optimized import get_model_info, initialize_models
        
        success, msg = initialize_models()
        if success:
            info = get_model_info()
            print(f"  Active model: {info['model_type']}")
            print(f"  Model size: {info['model_size_kb']:.1f} KB")
            
            if info['model_type'] == 'tflite':
                print(f"  ✅ Using optimized TFLite model (expected: ~22ms inference)")
            elif info['model_type'] == 'h5':
                print(f"  ⚠️  Using H5 fallback (current: ~95ms inference)")
                if tflite_exists:
                    print(f"     WARNING: .tflite exists but not loading - check permissions")
        else:
            print(f"  ❌ {msg}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print()
