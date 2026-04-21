from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import shap
import matplotlib.pyplot as plt


def evaluate_critical_zone(
    y_true: np.ndarray, y_pred: np.ndarray, threshold: float = 30.0
) -> dict[str, float]:
    mask = y_true <= float(threshold)
    if not np.any(mask):
        return {"count": 0.0, "mae": 0.0, "rmse": 0.0, "over_pred_rate": 0.0}

    yt = y_true[mask]
    yp = y_pred[mask]
    # Dangerous direction: predicting longer life than actual
    over_pred_rate = float(np.mean(yp > yt))
    return {
        "count": float(yt.shape[0]),
        "mae": float(np.mean(np.abs(yp - yt))),
        "rmse": float(np.sqrt(np.mean((yp - yt) ** 2))),
        "over_pred_rate": over_pred_rate,
    }


class XGBoostDataManager:
    """Handles loading and flattening of RUL sequence data."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def load_and_flatten(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Loads sequence data (N, T, F) and flattens it to (N, T*F).
        Returns (X_train, y_train, X_test, y_test).
        """
        x_train_seq = np.load(self.data_dir / "X_train.npy")
        y_train = np.load(self.data_dir / "y_train.npy")
        x_test_seq = np.load(self.data_dir / "X_test.npy")
        y_test = np.load(self.data_dir / "y_test.npy")

        # Shape check and flattening
        # Expected shape: (N, 30, 10) -> Flattened: (N, 300)
        n_train, t, f = x_train_seq.shape
        n_test = x_test_seq.shape[0]

        X_train = x_train_seq.reshape(n_train, t * f)
        X_test = x_test_seq.reshape(n_test, t * f)

        print(f"Flattened training data: {x_train_seq.shape} -> {X_train.shape}")
        print(f"Flattened testing data: {x_test_seq.shape} -> {X_test.shape}")

        return X_train, y_train, X_test, y_test


class XGBoostTrainer:
    """Handles the training of the XGBoost regressor."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        self.model = xgb.XGBRegressor(
            n_estimators=1000,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            n_jobs=-1,
            random_state=self.random_seed,
            objective="reg:squarederror"
        )

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        """Trains the model on the provided data."""
        print("Starting XGBoost training...")
        self.model.fit(
            X_train, 
            y_train,
            verbose=True
        )
        print("Training complete.")
        return self.model


class XGBoostEvaluator:
    """Evaluates the model performance using standard regression metrics."""

    @staticmethod
    def evaluate(y_true: np.ndarray, y_pred: np.ndarray, model: xgb.XGBRegressor, X_test: np.ndarray, data_dir: Path, project_root: Path) -> dict[str, Any]:
        """Computes MAE, RMSE, R2, and critical zone metrics."""
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred))
        critical = evaluate_critical_zone(y_true, y_pred)

        # --- SHAP Explainability ---
        print("\nComputing SHAP values for model interpretability...")
        
        # We use a subset for background to speed up model-agnostic explanation
        # and bypass the TreeExplainer config parsing bug.
        # Use KernelExplainer on a small subset for stability
        # sample down to 20 for KernelExplainer as it is slow but foolproof
        X_test_sample = X_test[:20]
        
        explainer = shap.KernelExplainer(model.predict, shap.sample(X_test, 10))
        shap_values = explainer.shap_values(X_test_sample)
        
        # 1. Global Feature Importance (Aggregated over 30 timesteps)
        shap_abs = np.abs(shap_values) # (20, 390)
        global_importance = np.mean(shap_abs, axis=0) # (390,)
        
        # Reshape to (Timesteps=30, Features=13)
        reshaped_importance = global_importance.reshape(30, 13)
        sensor_importance = np.mean(reshaped_importance, axis=0)
        
        # 2. Temporal Importance (Importance vs Time)
        # Sum importance across all sensors for each timestep
        temporal_importance = np.sum(reshaped_importance, axis=1) # (30,)
        
        # Feature names
        feature_names = [
            "temperature", "vibration", "pressure", "speed", "load", "flow", 
            "humidity", "wear", "health", "operating_time", 
            "queue_length", "machine_utilization", "routing_load"
        ]
        
        shap_report = {
            "sensor_importance": {name: float(imp) for name, imp in zip(feature_names, sensor_importance)},
            "temporal_importance": temporal_importance.tolist()
        }
        
        # Generate Feature Importance Plot
        plt.figure(figsize=(10, 6))
        sorted_idx = np.argsort(sensor_importance)
        plt.barh([feature_names[i] for i in sorted_idx], sensor_importance[sorted_idx], color="skyblue")
        plt.xlabel("Mean Absolute SHAP Value")
        plt.title("XGBoost Sensor Importance (Global)")
        plt.tight_layout()
        plt.savefig(data_dir / "xgb_sensor_importance.png")
        plt.close()

        # Generate Temporal Importance Plot
        plt.figure(figsize=(10, 5))
        plt.plot(range(1, 31), temporal_importance, marker='o', linestyle='-', color="teal")
        plt.xlabel("Timesteps (T-30 to T-0)")
        plt.ylabel("Total SHAP Impact")
        plt.title("Temporal Feature Importance (Contribution vs Time)")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(data_dir / "xgb_temporal_importance.png")
        plt.close()

        metrics = {
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "critical_zone": critical,
            "shap_importance": shap_report
        }
        
        print("\nEvaluation Results:")
        print(f"  MAE: {mae:.4f}")
        print(f"  RMSE: {rmse:.4f}")
        print(f"  R2: {r2:.4f}")
        print(f"  Critical Zone (RUL <= 30) MAE: {critical['mae']:.4f}")
        print(f"  Critical Zone (RUL <= 30) RMSE: {critical['rmse']:.4f}")
        print(f"  Critical Zone (RUL <= 30) Overprediction Rate: {critical['over_pred_rate']*100:.1f}%")
            
        return metrics


class XGBoostPersistence:
    """Handles saving and loading the model and metrics."""

    def __init__(self, model_path: Path, metrics_path: Path):
        self.model_path = model_path
        self.metrics_path = metrics_path

    def save_model(self, model: xgb.XGBRegressor):
        """Saves the XGBoost model using joblib."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self.model_path)
        print(f"Model saved to: {self.model_path}")

    def save_metrics(self, metrics: dict[str, float]):
        """Saves the metrics to a JSON file."""
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"Metrics saved to: {self.metrics_path}")


def main():
    # --- Configuration ---
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data" / "predictions"
    model_output = project_root / "predictive_maintenance_xgb.joblib"
    metrics_output = data_dir / "xgb_metrics.json"
    
    # 1. Load and Flatten Data
    data_manager = XGBoostDataManager(data_dir)
    try:
        X_train, y_train, X_test, y_test = data_manager.load_and_flatten()
    except FileNotFoundError as e:
        print(f"Error: Could not find dataset files. Ensure preprocessing.py has been run. {e}")
        return

    # 2. Train Model
    trainer = XGBoostTrainer(random_seed=42)
    model = trainer.train(X_train, y_train)

    # 3. Evaluate
    y_pred = model.predict(X_test)
    evaluator = XGBoostEvaluator()
    metrics = evaluator.evaluate(y_test, y_pred, model, X_test, data_dir, project_root)

    # 4. Save Results
    persistence = XGBoostPersistence(model_output, metrics_output)
    persistence.save_model(model)
    persistence.save_metrics(metrics)


if __name__ == "__main__":
    main()
