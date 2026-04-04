from pathlib import Path
import pandas as pd

base_dir = Path(__file__).resolve().parent
csv_path = base_dir / "IndFD-PM-DT dataset.csv"

df = pd.read_csv(csv_path)
print(df["RUL"].min(), df["RUL"].max(), df["RUL"].mean())