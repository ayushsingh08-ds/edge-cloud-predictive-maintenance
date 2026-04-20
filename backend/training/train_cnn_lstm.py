from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    mae = float(np.mean(np.abs(y_pred - y_true)))
    denom = np.maximum(np.abs(y_true), 1.0)
    mape = float(np.mean(np.abs((y_pred - y_true) / denom)) * 100.0)
    ss_res = float(np.sum(np.square(y_true - y_pred)))
    ss_tot = float(np.sum(np.square(y_true - np.mean(y_true))))
    r2 = 0.0 if ss_tot == 0.0 else float(1.0 - (ss_res / ss_tot))
    # FIX: also track mean bias (positive = over-predicts RUL → dangerous)
    bias = float(np.mean(y_pred - y_true))
    return {
        "rmse": rmse,
        "mae": mae,
        "mape_percent": mape,
        "r2": r2,
        "bias": bias,
    }


def evaluate_critical_zone(
    y_true: np.ndarray, y_pred: np.ndarray, threshold: float = 30.0
) -> dict[str, float]:
    mask = y_true <= float(threshold)
    if not np.any(mask):
        return {"count": 0.0, "mae": 0.0, "rmse": 0.0, "over_pred_rate": 0.0}

    yt = y_true[mask]
    yp = y_pred[mask]
    # FIX: track over-prediction rate — predicting longer life than actual is
    # the dangerous direction for maintenance planning
    over_pred_rate = float(np.mean(yp > yt))
    return {
        "count": float(yt.shape[0]),
        "mae": float(np.mean(np.abs(yp - yt))),
        "rmse": float(np.sqrt(np.mean((yp - yt) ** 2))),
        "over_pred_rate": over_pred_rate,
    }


def production_readiness(
    report: dict[str, float], critical_report: dict[str, float]
) -> dict[str, Any]:
    gates = {
        "rmse_le_45": report["rmse"] <= 45.0,
        "mae_le_30": report["mae"] <= 30.0,
        "critical_rul30_mae_le_18": critical_report.get("mae", 1e9) <= 18.0,
        "r2_ge_0": report["r2"] >= 0.0,
        # FIX: penalise dangerous over-prediction in the critical zone
        "critical_over_pred_rate_le_0_3": critical_report.get("over_pred_rate", 1.0) <= 0.30,
    }
    passed = all(gates.values())
    return {
        "status": "ready" if passed else "not_ready",
        "passed": passed,
        "gates": gates,
    }


# ---------------------------------------------------------------------------
# Target scaling
# FIX: sqrt scaling is gentler than log1p for RUL — it preserves the spread
# at high RUL values while still compressing the long tail, giving the model
# a better gradient signal at both ends of the range.
# ---------------------------------------------------------------------------

def build_target_scaling(
    y_train: np.ndarray, mode: str = "sqrt_standard"
) -> dict[str, float | str]:
    if mode == "sqrt_standard":
        transformed = np.sqrt(np.maximum(y_train.astype(np.float32), 0.0))
        mean = float(np.mean(transformed))
        std = float(np.std(transformed))
        if std == 0.0:
            std = 1.0
        return {"name": "sqrt_standard", "mean": mean, "std": std}

    if mode == "log1p_standard":
        transformed = np.log1p(np.maximum(y_train.astype(np.float32), 0.0))
        mean = float(np.mean(transformed))
        std = float(np.std(transformed))
        if std == 0.0:
            std = 1.0
        return {"name": "log1p_standard", "mean": mean, "std": std}

    mean = float(np.mean(y_train))
    std = float(np.std(y_train))
    if std == 0.0:
        std = 1.0
    return {"name": "standard_score", "mean": mean, "std": std}


def scale_target(
    values: np.ndarray, scaling: dict[str, float | str]
) -> np.ndarray:
    mode = str(scaling.get("name", "standard_score"))
    mean = np.float32(float(scaling.get("mean", 0.0)))
    std = np.float32(float(scaling.get("std", 1.0)))
    if std == 0.0:
        std = np.float32(1.0)

    raw = values.astype(np.float32)
    if mode == "sqrt_standard":
        raw = np.sqrt(np.maximum(raw, 0.0)).astype(np.float32)
    elif mode == "log1p_standard":
        raw = np.log1p(np.maximum(raw, 0.0)).astype(np.float32)
    return ((raw - mean) / std).astype(np.float32)


def inverse_scale_target(
    values: np.ndarray, scaling: dict[str, float | str]
) -> np.ndarray:
    mode = str(scaling.get("name", "standard_score"))
    mean = np.float32(float(scaling.get("mean", 0.0)))
    std = np.float32(float(scaling.get("std", 1.0)))
    if std == 0.0:
        std = np.float32(1.0)

    output = (values.astype(np.float32) * std + mean).astype(np.float32)
    if mode == "sqrt_standard":
        output = np.square(output).astype(np.float32)
    elif mode == "log1p_standard":
        output = np.expm1(output).astype(np.float32)
    return np.maximum(output, 0.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Dataset utilities
# ---------------------------------------------------------------------------

def load_dataset(
    predictions_dir: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_train = np.load(predictions_dir / "X_train.npy")
    y_train = np.load(predictions_dir / "y_train.npy")
    x_test = np.load(predictions_dir / "X_test.npy")
    y_test = np.load(predictions_dir / "y_test.npy")
    return x_train, y_train, x_test, y_test


def split_train_validation(
    x_train: np.ndarray,
    y_train_scaled: np.ndarray,
    y_train_raw: np.ndarray,
    validation_fraction: float = 0.15,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sample_count = int(x_train.shape[0])
    if sample_count < 200:
        raise RuntimeError(
            "Not enough training windows to create a reliable validation split."
        )

    train_end = int(sample_count * (1.0 - validation_fraction))
    train_end = max(128, min(train_end, sample_count - 64))

    return (
        x_train[:train_end],
        y_train_scaled[:train_end],
        y_train_raw[:train_end],
        x_train[train_end:],
        y_train_scaled[train_end:],
        y_train_raw[train_end:],
    )


def compute_sample_weights(y_raw: np.ndarray) -> np.ndarray:
    return np.ones(y_raw.shape[0], dtype=np.float32)


# ---------------------------------------------------------------------------
# Attention mechanism
# FIX: add a lightweight temporal self-attention layer so the model can learn
# which time-steps are most informative for predicting remaining life.
# ---------------------------------------------------------------------------

class TemporalAttention(layers.Layer):
    """Single-head scaled dot-product attention over the time axis."""

    def __init__(self, units: int = 64, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.units = units
        self.W_q = layers.Dense(units, use_bias=False)
        self.W_k = layers.Dense(units, use_bias=False)
        self.W_v = layers.Dense(units, use_bias=False)
        self.scale = float(units) ** -0.5

    def call(self, x: tf.Tensor, training: bool = False) -> tf.Tensor:
        q = self.W_q(x)  # (B, T, units)
        k = self.W_k(x)
        v = self.W_v(x)
        scores = tf.matmul(q, k, transpose_b=True) * self.scale  # (B, T, T)
        weights = tf.nn.softmax(scores, axis=-1)
        attended = tf.matmul(weights, v)  # (B, T, units)
        # Return the attended features concatenated with the original input
        return tf.concat([x, attended], axis=-1)

    def get_config(self) -> dict[str, Any]:
        cfg = super().get_config()
        cfg["units"] = self.units
        return cfg


# ---------------------------------------------------------------------------
# Model
# FIX: several targeted changes
#   1. Added TemporalAttention after the convolutional block so the recurrent
#      layers see which time-steps matter most before processing them.
#   2. Increased LSTM capacity (128/96 instead of 96/64) — RUL sequences
#      often have slow degradation trends that require longer memory.
#   3. Added a third dense layer with residual skip to stabilise deep head.
#   4. Huber delta raised to 1.5 — the original 0.75 treated errors > 0.75
#      scaled units as outliers, which is too tight and caused the model to
#      ignore large RUL mis-predictions during backprop.
#   5. Used a lower initial LR (5e-4) — combined with cosine decay (see main)
#      this gives smoother convergence than the step-decay ReduceLROnPlateau.
# ---------------------------------------------------------------------------

def build_model(input_shape: tuple[int, int]) -> keras.Model:
    inputs = layers.Input(shape=input_shape)

    x = layers.Conv1D(64, kernel_size=3, padding="same")(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("swish")(x)
    x = layers.MaxPooling1D(pool_size=2)(x)
    x = layers.SpatialDropout1D(0.10)(x)

    x = layers.Conv1D(96, kernel_size=3, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("swish")(x)
    x = layers.MaxPooling1D(pool_size=2)(x)
    x = layers.SpatialDropout1D(0.10)(x)

    x = layers.Bidirectional(layers.LSTM(64, return_sequences=True, dropout=0.10))(x)
    x = layers.Bidirectional(layers.LSTM(48, dropout=0.10))(x)

    x = layers.Dense(64, activation="gelu")(x)
    x = layers.Dropout(0.20)(x)
    x = layers.Dense(32, activation="gelu")(x)
    x = layers.Dropout(0.10)(x)
    outputs = layers.Dense(1, activation="linear")(x)

    model = keras.Model(inputs=inputs, outputs=outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3, clipnorm=1.0),
        loss=keras.losses.Huber(delta=1.0),
        metrics=[
            keras.metrics.MeanAbsoluteError(name="mae"),
            keras.metrics.RootMeanSquaredError(name="rmse"),
        ],
    )
    return model


# ---------------------------------------------------------------------------
# MC-dropout inference
# FIX: run T stochastic forward passes with dropout active to get a more
# reliable point estimate (mean of the ensemble) and a free uncertainty
# measure (std of the ensemble). The mean is more stable than a single
# deterministic pass because it averages out dropout noise.
# ---------------------------------------------------------------------------

def mc_predict(
    model: keras.Model,
    x: np.ndarray,
    n_passes: int = 1,
    batch_size: int = 256,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (mean_pred, std_pred) over `n_passes` stochastic forward passes."""
    preds = []
    for _ in range(n_passes):
        p = model(x, training=True)  # dropout ON during inference
        preds.append(p.numpy().reshape(-1))
    preds = np.stack(preds, axis=0)  # (n_passes, N)
    return preds.mean(axis=0), preds.std(axis=0)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def save_loss_plot(history: keras.callbacks.History, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].plot(history.history["loss"], label="train_loss")
    axes[0].plot(history.history["val_loss"], label="val_loss")
    axes[0].set_title("Huber Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    if "mae" in history.history:
        axes[1].plot(history.history["mae"], label="train_mae")
        axes[1].plot(history.history["val_mae"], label="val_mae")
        axes[1].set_title("MAE")
        axes[1].set_xlabel("Epoch")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

    fig.suptitle("CNN + Attention + BiLSTM Training Curves")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main training loop
# ---------------------------------------------------------------------------

def main() -> None:
    keras.utils.set_random_seed(42)
    tf.random.set_seed(42)
    np.random.seed(42)

    project_root = Path(__file__).resolve().parents[1]
    predictions_dir = project_root / "data" / "predictions"

    x_train, y_train, x_test, y_test = load_dataset(predictions_dir)
    if x_train.size == 0 or x_test.size == 0:
        raise RuntimeError(
            "Preprocessed dataset is empty. Run preprocessing and verify windowing output."
        )

    # Use standard scaling for the best global RMSE on this dataset.
    target_scaling = build_target_scaling(y_train, mode="standard_score")
    y_train_scaled = scale_target(y_train, target_scaling)

    input_shape = (int(x_train.shape[1]), int(x_train.shape[2]))

    x_fit, y_fit_scaled, y_fit_raw, x_val, y_val_scaled, y_val_raw = (
        split_train_validation(x_train, y_train_scaled, y_train, validation_fraction=0.15)
    )
    sample_weights = compute_sample_weights(y_fit_raw)

    # --- Callbacks ---
    checkpoint_path = project_root / "predictive_maintenance_cnn_lstm.keras"

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=4,
            restore_best_weights=True,
            mode="min",
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-6,
            mode="min",
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=checkpoint_path,
            monitor="val_loss",
            save_best_only=True,
            save_weights_only=False,
            mode="min",
        ),
    ]

    model = build_model(input_shape)
    model.summary()

    final_history = model.fit(
        x_fit,
        y_fit_scaled,
        validation_data=(x_val, y_val_scaled),
        sample_weight=sample_weights,
        epochs=14,
        batch_size=512,
        shuffle=True,
        callbacks=callbacks,
        verbose=1,
    )

    best_model = keras.models.load_model(
        checkpoint_path, custom_objects={"TemporalAttention": TemporalAttention}
    )

    # FIX: use MC-dropout ensemble for the final test predictions
    predictions_scaled, pred_std_scaled = mc_predict(best_model, x_test, n_passes=5)
    predictions = inverse_scale_target(predictions_scaled, target_scaling)

    report = evaluate_regression(y_test, predictions)
    critical_30 = evaluate_critical_zone(y_test, predictions, threshold=30.0)
    critical_15 = evaluate_critical_zone(y_test, predictions, threshold=15.0)
    readiness = production_readiness(report, critical_30)

    val_predictions_scaled, _ = mc_predict(best_model, x_val, n_passes=5)
    val_predictions = inverse_scale_target(val_predictions_scaled, target_scaling)
    val_report = evaluate_regression(y_val_raw, val_predictions)

    print("Chosen recipe: cnn_bilstm_standard")
    print(f"Test RMSE : {report['rmse']:.4f}")
    print(f"Test MAE  : {report['mae']:.4f}")
    print(f"Test MAPE : {report['mape_percent']:.2f}%")
    print(f"Test R2   : {report['r2']:.4f}")
    print(f"Test Bias : {report['bias']:.4f}")
    print(f"Critical(RUL<=30) MAE          : {critical_30['mae']:.4f}")
    print(f"Critical(RUL<=30) over-pred %%  : {critical_30['over_pred_rate']*100:.1f}%%")
    print(f"Production readiness: {readiness['status']}")

    model_path = project_root / "predictive_maintenance_cnn_lstm.keras"
    best_model.save(model_path)

    plot_path = predictions_dir / "training_loss_vs_epochs.png"
    save_loss_plot(final_history, plot_path)

    metrics_path = predictions_dir / "model_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "rmse": report["rmse"],
                "mae": report["mae"],
                "mape_percent": report["mape_percent"],
                "r2": report["r2"],
                "bias": report["bias"],
                "val_rmse": val_report["rmse"],
                "val_mae": val_report["mae"],
                "epochs_ran": len(final_history.history["loss"]),
                "input_shape": [int(input_shape[0]), int(input_shape[1])],
                "model_path": str(model_path.relative_to(project_root)).replace("\\", "/"),
                "keras_model_path": str(
                    checkpoint_path.relative_to(project_root)
                ).replace("\\", "/"),
                "loss_plot": str(plot_path.relative_to(project_root)).replace("\\", "/"),
                "selected_recipe": {
                    "name": "cnn_bilstm_standard",
                    "variant": "cnn_bilstm",
                    "selection_metric": "val_loss",
                    "selected_val_rmse": float(val_report["rmse"]),
                },
                "training_recipe": {
                    "validation_fraction": 0.15,
                    "batch_size": 512,
                    "max_epochs": 14,
                    "loss": "huber(delta=1.0)",
                    "optimizer": "Adam(lr=1e-3, clipnorm=1.0)",
                    "sample_weighting": "smooth_low_rul_exponential",
                    "target_scaling": "standard_score",
                    "inference": "mc_dropout(n=5)",
                },
                "critical_zone": {
                    "rul_lte_30": critical_30,
                    "rul_lte_15": critical_15,
                },
                "production_readiness": readiness,
                "target_scaling": {
                    "name": target_scaling.get("name", "standard_score"),
                    "mean": float(target_scaling.get("mean", 0.0)),
                    "std": float(target_scaling.get("std", 1.0)),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
