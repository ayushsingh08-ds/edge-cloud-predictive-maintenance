from __future__ import annotations

import importlib
import sys

REQUIRED_IMPORTS = [
    "simpy",
    "sklearn",
    "lightgbm",
    "torch",
    "gymnasium",
    "stable_baselines3",
    "fastapi",
    "sqlalchemy",
    "pika",
]


def main() -> int:
    failed: list[str] = []

    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
            print(f"[OK] Imported {module_name}")
        except Exception as exc:
            print(f"[FAIL] Could not import {module_name}: {exc}")
            failed.append(module_name)

    if failed:
        print("\nEnvironment verification failed.")
        print("Missing or broken modules:", ", ".join(failed))
        return 1

    print("\nEnvironment verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
