import json
from pathlib import Path
import pandas as pd
import numpy as np

def run_comparison():
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "backend" / "data" / "predictions"
    
    # We expect these files to exist after training scripts have run
    metrics_files = {
        "XGBoost": data_dir / "xgb_metrics.json",
        "Transformer": data_dir / "transformer_metrics.json",
        "CNN-LSTM": data_dir / "model_metrics.json" # Baseline name used in CNN-LSTM script
    }
    
    results = []
    
    for name, path in metrics_files.items():
        if path.exists():
            with open(path, "r") as f:
                m = json.load(f)
                results.append({
                    "Model": name,
                    "MAE": round(m.get("mae", 0), 4),
                    "RMSE": round(m.get("rmse", 0), 4),
                    "R2": round(m.get("r2", 0), 4),
                    "Critical MAE": round(m.get("critical_zone", {}).get("mae", 0), 4),
                    "Over-Pred Rate": round(m.get("critical_zone", {}).get("over_pred_rate", 0), 4)
                })
        else:
            print(f"Warning: Metrics for {name} not found at {path}")

    if not results:
        print("No results found. Ensure you have run the training scripts first.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values(by="MAE")
    
    report_path = data_dir / "model_comparison_report.json"
    df.to_json(report_path, orient="records", indent=2)
    
    print("\nModel Comparison Table:")
    print(df.to_string(index=False))
    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    run_comparison()
