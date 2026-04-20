from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


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


class RULDataset(Dataset):
    """Custom Dataset for loading RUL sequence data."""
    def __init__(self, x_data: np.ndarray, y_data: np.ndarray):
        self.x = torch.from_numpy(x_data.astype(np.float32))
        self.y = torch.from_numpy(y_data.astype(np.float32))

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.x[idx], self.y[idx]


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding to inject sequence order info."""
    def __init__(self, d_model: int, max_len: int = 100):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor, shape [batch_size, seq_len, d_model]
        """
        x = x + self.pe[:, :x.size(1), :]
        return x


class RULTransformerModel(nn.Module):
    """Transformer Encoder based model for RUL prediction."""
    def __init__(self, n_features: int, d_model: int = 128, nhead: int = 8, 
                 num_layers: int = 4, dim_feedforward: int = 512, dropout: float = 0.1):
        super().__init__()
        self.feature_projection = nn.Linear(n_features, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        
        encoder_layers = nn.TransformerEncoderLayer(
            d_model, nhead, dim_feedforward, dropout, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers)
        
        self.regressor = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor, shape [batch_size, seq_len, n_features]
        """
        # Map features to embedding dimension
        x = self.feature_projection(x) # (B, T, d_model)
        x = self.pos_encoder(x)
        
        # Transformer encoding
        x = self.transformer_encoder(x) # (B, T, d_model)
        
        # Global pooling (mean over time steps)
        x = torch.mean(x, dim=1) # (B, d_model)
        
        # Final regression
        return self.regressor(x).squeeze(-1)


class EarlyStopping:
    """Helper to stop training if validation loss doesn't improve."""
    def __init__(self, patience: int = 5, min_delta: float = 0):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = float('inf')
        self.early_stop = False

    def __call__(self, val_loss: float):
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True


class TransformerTrainer:
    """Modular trainer for the RUL Transformer model."""
    def __init__(self, model: nn.Module, device: torch.device, lr: float = 1e-4):
        self.model = model.to(device)
        self.device = device
        self.optimizer = optim.Adam(model.parameters(), lr=lr)
        self.criterion = nn.HuberLoss(delta=1.0) # More robust than MSE for RUL

    def train_epoch(self, dataloader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0
        for x, y in dataloader:
            x, y = x.to(self.device), y.to(self.device)
            
            self.optimizer.zero_grad()
            outputs = self.model(x)
            loss = self.criterion(outputs, y)
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
        return total_loss / len(dataloader)

    def validate(self, dataloader: DataLoader) -> float:
        self.model.eval()
        total_loss = 0.0
        with torch.no_grad():
            for x, y in dataloader:
                x, y = x.to(self.device), y.to(self.device)
                outputs = self.model(x)
                loss = self.criterion(outputs, y)
                total_loss += loss.item()
        return total_loss / len(dataloader)

    def evaluate(self, dataloader: DataLoader) -> dict[str, Any]:
        self.model.eval()
        all_preds = []
        all_true = []
        with torch.no_grad():
            for x, y in dataloader:
                x, y = x.to(self.device), y.to(self.device)
                outputs = self.model(x)
                all_preds.append(outputs.cpu().numpy())
                all_true.append(y.cpu().numpy())
        
        preds = np.concatenate(all_preds)
        true = np.concatenate(all_true)
        
        mae = mean_absolute_error(true, preds)
        rmse = np.sqrt(mean_squared_error(true, preds))
        r2 = r2_score(true, preds)
        
        critical = evaluate_critical_zone(true, preds)

        print("\nFinal Test Metrics:")
        print(f"  Overall MAE: {mae:.4f}")
        print(f"  Overall RMSE: {rmse:.4f}")
        print(f"  Overall R2: {r2:.4f}")
        
        print(f"\nCritical Zone (RUL <= 30) Results:")
        print(f"  Critical MAE: {critical['mae']:.4f}")
        print(f"  Critical RMSE: {critical['rmse']:.4f}")
        print(f"  Overprediction Rate: {critical['over_pred_rate']*100:.1f}%")

        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "critical_zone": critical
        }


def main():
    # --- Config ---
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data" / "predictions"
    model_save_path = project_root / "predictive_maintenance_transformer.pt"
    metrics_path = data_dir / "transformer_metrics.json"

    # --- Load Data ---
    try:
        x_train_raw = np.load(data_dir / "X_train.npy")
        y_train_raw = np.load(data_dir / "y_train.npy")
        x_test_raw = np.load(data_dir / "X_test.npy")
        y_test_raw = np.load(data_dir / "y_test.npy")
    except FileNotFoundError:
        print("Error: Dataset files not found. Run preprocessing.py first.")
        return

    # Basic train-validation split (15%)
    val_split = int(len(x_train_raw) * 0.85)
    x_train, x_val = x_train_raw[:val_split], x_train_raw[val_split:]
    y_train, y_val = y_train_raw[:val_split], y_train_raw[val_split:]

    train_loader = DataLoader(RULDataset(x_train, y_train), batch_size=64, shuffle=True)
    val_loader = DataLoader(RULDataset(x_val, y_val), batch_size=64)
    test_loader = DataLoader(RULDataset(x_test_raw, y_test_raw), batch_size=64)

    # --- Build Model ---
    n_features = x_train_raw.shape[2]
    model = RULTransformerModel(n_features=n_features, d_model=128, nhead=8, num_layers=3)
    trainer = TransformerTrainer(model, device)
    early_stopping = EarlyStopping(patience=5)

    # --- Training Loop ---
    epochs = 50
    print("Starting Transformer training...")
    for epoch in range(1, epochs + 1):
        train_loss = trainer.train_epoch(train_loader)
        val_loss = trainer.validate(val_loader)
        
        print(f"Epoch {epoch:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")
        
        early_stopping(val_loss)
        if early_stopping.early_stop:
            print("Early stopping triggered.")
            break

    # --- Final Evaluation ---
    metrics = trainer.evaluate(test_loader)
    print("\nFinal Test Metrics:")
    for k, v in metrics.items():
        print(f"  {k.upper()}: {v:.4f}")

    # --- Save Results ---
    torch.save(model.state_dict(), model_save_path)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nModel saved to: {model_save_path}")
    print(f"Metrics saved to: {metrics_path}")


if __name__ == "__main__":
    main()
