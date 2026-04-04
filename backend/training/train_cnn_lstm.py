from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


def standardize_target(values: np.ndarray, mean: float, std: float) -> np.ndarray:
    return ((values.astype(np.float32) - np.float32(mean)) / np.float32(std)).astype(np.float32)


def inverse_standardize_target(values: np.ndarray, mean: float, std: float) -> np.ndarray:
    return (values.astype(np.float32) * np.float32(std) + np.float32(mean)).astype(np.float32)


def load_dataset(predictions_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_train = np.load(predictions_dir / "X_train.npy")
    y_train = np.load(predictions_dir / "y_train.npy")
    x_test = np.load(predictions_dir / "X_test.npy")
    y_test = np.load(predictions_dir / "y_test.npy")
    return x_train, y_train, x_test, y_test


def build_model(input_shape: tuple[int, int]) -> keras.Model:
    model = keras.Sequential(
        [
            layers.Input(shape=input_shape),
            layers.Conv1D(filters=64, kernel_size=3, activation="relu", padding="same"),
            layers.MaxPooling1D(pool_size=2),
            layers.Conv1D(filters=128, kernel_size=3, activation="relu", padding="same"),
            layers.MaxPooling1D(pool_size=2),
            layers.LSTM(96, return_sequences=True),
            layers.LSTM(64),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.2),
            layers.Dense(32, activation="relu"),
            layers.Dense(1, activation="linear"),
        ]
    )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss=keras.losses.Huber(delta=1.0),
        metrics=[keras.metrics.MeanAbsoluteError(name="mae"), keras.metrics.RootMeanSquaredError(name="rmse")],
    )
    return model


def save_loss_plot(history: keras.callbacks.History, output_path: Path) -> None:
    plt.figure(figsize=(10, 6))
    plt.plot(history.history["loss"], label="train_loss")
    plt.plot(history.history["val_loss"], label="val_loss")
    plt.title("CNN + LSTM Training Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def main() -> None:
    tf.random.set_seed(42)
    np.random.seed(42)

    project_root = Path(__file__).resolve().parents[1]
    predictions_dir = project_root / "data" / "predictions"

    x_train, y_train, x_test, y_test = load_dataset(predictions_dir)
    if x_train.size == 0 or x_test.size == 0:
        raise RuntimeError("Preprocessed dataset is empty. Run preprocessing and verify windowing output.")

    metadata_path = predictions_dir / "preprocessing_metadata.json"
    target_scaling = {"name": "standard_score"}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        target_scaling = metadata.get("target_scaling", target_scaling)

    target_mean = float(target_scaling.get("mean", float(np.mean(y_train))))
    target_std = float(target_scaling.get("std", float(np.std(y_train))))
    if target_std == 0.0:
        target_std = 1.0

    y_train_scaled = standardize_target(y_train, target_mean, target_std)
    y_test_scaled = standardize_target(y_test, target_mean, target_std)

    input_shape = (int(x_train.shape[1]), int(x_train.shape[2]))
    model = build_model(input_shape)

    early_stopping = keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=12,
        restore_best_weights=True,
        mode="min",
    )

    reduce_lr = keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=4,
        min_lr=1e-5,
        mode="min",
    )

    checkpoint_path = project_root / "predictive_maintenance_cnn_lstm.keras"
    checkpoint = keras.callbacks.ModelCheckpoint(
        filepath=checkpoint_path,
        monitor="val_loss",
        save_best_only=True,
        save_weights_only=False,
        mode="min",
    )

    history = model.fit(
        x_train,
        y_train_scaled,
        validation_split=0.2,
        epochs=80,
        batch_size=64,
        callbacks=[early_stopping, reduce_lr, checkpoint],
        verbose=1,
    )

    best_model = keras.models.load_model(checkpoint_path)
    predictions_scaled = best_model.predict(x_test, verbose=0).reshape(-1)
    predictions = inverse_standardize_target(predictions_scaled, target_mean, target_std)
    rmse = float(np.sqrt(np.mean((predictions - y_test) ** 2)))
    mae = float(np.mean(np.abs(predictions - y_test)))

    print(f"Test RMSE: {rmse:.4f}")
    print(f"Test MAE: {mae:.4f}")

    model_path = project_root / "predictive_maintenance_cnn_lstm.keras"
    model.save(model_path)
    best_model.save(checkpoint_path)

    plot_path = predictions_dir / "training_loss_vs_epochs.png"
    save_loss_plot(history, plot_path)

    metrics_path = predictions_dir / "model_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "rmse": rmse,
                "mae": mae,
                "epochs_ran": len(history.history["loss"]),
                "input_shape": [int(input_shape[0]), int(input_shape[1])],
                "model_path": str(model_path),
                "keras_model_path": str(checkpoint_path),
                "loss_plot": str(plot_path),
                "target_scaling": {
                    "name": target_scaling.get("name", "standard_score"),
                    "mean": target_mean,
                    "std": target_std,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
