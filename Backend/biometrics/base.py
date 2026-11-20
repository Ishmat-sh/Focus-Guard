from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol


class BiometricSource(Protocol):
    def read(self) -> list[dict[str, float | str | None]]:
        ...


class HealthExportSource:
    """Read real values from a JSON or CSV health export, never synthetic data."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"Biometric export not found: {self.path}")

    def read(self) -> list[dict[str, float | str | None]]:
        if self.path.suffix.lower() == ".json":
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("Health export JSON must contain a list")
            rows = data
        elif self.path.suffix.lower() == ".csv":
            with self.path.open(newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))
        else:
            raise ValueError("Health export must be JSON or CSV")

        normalized: list[dict[str, float | str | None]] = []
        for row in rows:
            heart_rate_raw = row.get("heart_rate")
            hrv_raw = row.get("hrv")
            timestamp_raw = row.get("timestamp")
            if heart_rate_raw in (None, ""):
                continue
            heart_rate = float(heart_rate_raw)
            hrv = None if hrv_raw in (None, "") else float(hrv_raw)
            timestamp = float(timestamp_raw) if timestamp_raw not in (None, "") else None
            if heart_rate < 0 or (hrv is not None and hrv < 0):
                raise ValueError("Heart rate and HRV must be non-negative")
            normalized.append(
                {
                    "timestamp": timestamp,
                    "heart_rate": heart_rate,
                    "hrv": hrv,
                    "source_device": str(row.get("source_device") or "health_export"),
                }
            )
        return normalized
