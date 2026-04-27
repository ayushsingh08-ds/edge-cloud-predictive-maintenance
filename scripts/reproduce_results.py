import json
import numpy as np
from pathlib import Path
from tensorflow import keras
from sklearn.metrics import mean_squared_error, mean_absolute_error

def reproduce_paper_metrics():
    print("=== Edge-Cloud Framework: Results Reproducibility Tool ===")
    
    project_root = Path(__file__).resolve().parent
    model_path = project_root / "backend" / "predictive_maintenance_cnn_lstm.keras"
    test_data_path = project_root / "backend" / "data" / "predictions"
    
    # 1. Load Model
    if not model_path.exists():
        print(f"Error: Model not found at {model_path}")
        return
    
    print(f"Loading model: {model_path.name}...")
    model = keras.models.load_model(model_path)
    
    # 2. Load Test Data
    try:
        X_test = np.load(test_data_path / "X_test.npy")
        y_test = np.load(test_data_path / "y_test.npy")
    except FileNotFoundError:
        print("Error: Test datasets (X_test.npy, y_test.npy) not found in backend/data/predictions/")
        return

    print(f"Dataset loaded: {len(X_test)} test sequences.")

    # 3. Inference
    print("Running inference...")
    y_pred_scaled = model.predict(X_test, verbose=0).flatten()
    
    # 4. Inverse Scaling (Based on paper's Huber/Standard scaling)
    # Note: Using metadata if available, otherwise assuming raw RUL scale
    metadata_path = test_data_path / "preprocessing_metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            meta = json.load(f)
            target_mean = meta['target_scaling']['mean']
            target_std = meta['target_scaling']['std']
            y_pred = (y_pred_scaled * target_std) + target_mean
            y_true = (y_test * target_std) + target_mean
    else:
        y_pred = y_pred_scaled
        y_true = y_test

    # 5. Calculate Metrics
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)

    print("\n--- Final Results ---")
    print(f"Test RMSE: {rmse:.2f} (Paper Claim: 57.29)")
    print(f"Test MAE:  {mae:.2f} (Paper Claim: 37.42)")
    
    if abs(rmse - 57.29) < 2.0:
        print("\nSUCCESS: Results are consistent with conference paper claims.")
    else:
        print("\nWARNING: Results deviate from paper claims. Check preprocessing/scaling.")

if __name__ == "__main__":
    reproduce_paper_metrics()
