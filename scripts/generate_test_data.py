import pandas as pd
import numpy as np
import os

np.random.seed(42)


def generate_synthetic_data(
    scenario: str,
    n_samples: int,
    machine_id: str
):

    timestamps = pd.date_range(
        start="2025-01-01",
        periods=n_samples,
        freq="5min"
    )

    n = len(timestamps)

    # Operating conditions
    load = 0.6 + 0.3 * np.sin(np.linspace(0, 4 * np.pi, n))
    operating_mode = np.random.choice(
        ["idle", "normal", "high-load"],
        n,
        p=[0.2, 0.6, 0.2]
    )

    ambient_temperature = 30 + 5 * np.sin(np.linspace(0, 2 * np.pi, n))

    # Base signals
    base_T = 580 + load * 80
    base_Vib = 0.018 + load * 0.025
    base_Press = 21 + load * 5
    base_RPM = 1480 + load * 250

    if scenario == "normal":

        noise = np.random.normal(0, [3.0, 0.0025, 0.35, 12], (n, 4))

        T = base_T + noise[:, 0]
        Vib = base_Vib + noise[:, 1]
        Press = base_Press + noise[:, 2]
        RPM = base_RPM + noise[:, 3]

        rul = np.full(n, np.nan)

    elif scenario == "gradual":

        t_norm = np.linspace(0, 1, n)
        degradation = t_norm ** 1.8
        noise_scale = 1 + 5 * degradation

        T = base_T + degradation * 110 + np.random.normal(0, 6 * noise_scale)
        Vib = base_Vib + degradation * 0.22 + np.random.normal(0, 0.004 * noise_scale)
        Press = base_Press - degradation * 3.5 + np.random.normal(0, 0.8 * noise_scale)
        RPM = base_RPM - degradation * 65 + np.random.normal(0, 25 * noise_scale)

        rul = (n - np.arange(n)) * 5 / 60.0

    elif scenario == "sudden":

        t_fail = int(n * 0.65)
        degradation = (np.arange(n) / n) ** 1.8 * 0.15

        T = base_T + degradation * 110
        Vib = base_Vib + degradation * 0.22
        Press = base_Press - degradation * 3.5
        RPM = base_RPM - degradation * 65

        mask = np.arange(n) >= t_fail

        T[mask] += 25 + np.arange(mask.sum()) * 0.8
        Vib[mask] += 0.35
        Press[mask] -= 7
        RPM[mask] -= 180

        T[mask] += np.random.normal(0, 12, mask.sum())
        Vib[mask] += np.random.normal(0, 0.09, mask.sum())
        Press[mask] += np.random.normal(0, 2.5, mask.sum())
        RPM[mask] += np.random.normal(0, 45, mask.sum())

        rul = np.where(mask, 0, (n - np.arange(n)) * 5 / 60.0)

    df = pd.DataFrame({
        "event_type": "sensor_reading",
        "version": "1.0",
        "timestamp": timestamps,
        "machine_id": machine_id,
        "sensor_id": "MAIN_SENSOR",
        "temperature": T.round(3),
        "vibration": Vib.round(4),
        "pressure": Press.round(3),
        "rotation_speed": RPM.round(2),
        "load": load.round(3),
        "ambient_temperature": ambient_temperature.round(2),
        "operating_mode": operating_mode,
        "rul_hours": np.round(rul, 2),
        "scenario": scenario
    })

    return df


def main():

    total_samples = 10000

    normal_samples = int(total_samples * 0.80)
    gradual_samples = int(total_samples * 0.15)
    sudden_samples = int(total_samples * 0.05)

    print("Generating dataset...")
    print("Normal:", normal_samples)
    print("Gradual:", gradual_samples)
    print("Sudden:", sudden_samples)

    df_normal = generate_synthetic_data(
        "normal",
        normal_samples,
        "M001"
    )

    df_gradual = generate_synthetic_data(
        "gradual",
        gradual_samples,
        "M002"
    )

    df_sudden = generate_synthetic_data(
        "sudden",
        sudden_samples,
        "M003"
    )

    df_all = pd.concat(
        [df_normal, df_gradual, df_sudden],
        ignore_index=True
    )

    os.makedirs("data/raw", exist_ok=True)

    output_path = "data/raw/training_data_large.csv"

    df_all.to_csv(output_path, index=False)

    print("Dataset saved to:", output_path)
    print("Total rows:", len(df_all))
    print(df_all.head())


if __name__ == "__main__":
    main()