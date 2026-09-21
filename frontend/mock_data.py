"""Simulated dashboard data. NOTHING in this file comes from a model or a sensor.

The values are generated from the clock, so the time series keep the same shape
between auto-refreshes and simply slide forward, like a live stream would.

Conventions used here (they are assumptions of the simulation, not backend facts):
- IMS score: higher = more anomalous, threshold is a single number.
- C-MAPSS RUL: measured in cycles.
- CWRU classes: generic labels, replace with the labels your classifier really returns.
"""
from __future__ import annotations

import zlib
from datetime import datetime

import numpy as np
import pandas as pd

SCENARIOS = {
    "normal": "Healthy machine",
    "warning": "Degrading machine",
    "critical": "Faulty machine",
}

_PARAMS = {
    "normal": dict(s=0.07, ims_base=0.28, ims_trend=0.00, rul=118, rul_slope=0.3,
                   fault="Normal", conf=0.97),
    "warning": dict(s=0.16, ims_base=0.36, ims_trend=0.14, rul=52, rul_slope=0.8,
                    fault="Normal", conf=0.81),
    "critical": dict(s=0.38, ims_base=0.55, ims_trend=0.25, rul=14, rul_slope=1.0,
                     fault="Inner Race", conf=0.93),
}

IMS_THRESHOLD = 0.60
SAMPLING_RATE_HZ = 500


def _noise(k: np.ndarray, seed: int) -> np.ndarray:
    """Deterministic pseudo-noise in [-1, 1] that depends only on k and seed."""
    x = np.sin(k * 12.9898 + seed * 78.233) * 43758.5453
    return (x - np.floor(x)) * 2 - 1


def generate_mock_dashboard_data(machine_id: str = "BEARING-01",
                                 scenario: str = "normal",
                                 n_points: int = 120) -> dict:
    p = _PARAMS.get(scenario, _PARAMS["normal"])
    seed = zlib.crc32(machine_id.encode()) % 1000
    now = datetime.now()
    t_end = int(now.timestamp())
    k = np.arange(t_end - n_points + 1, t_end + 1)          # one point per second
    timestamps = pd.to_datetime([datetime.fromtimestamp(int(x)) for x in k])   # local time
    frac = np.linspace(0, 1, n_points)

    # --- sensor (each point stands for one 1-second window) -------------------
    scale = p["s"] * (1 + 0.25 * np.sin(k / 23.0))
    ax = scale * _noise(k, seed + 1)
    ay = scale * _noise(k, seed + 2)
    az = 1.0 + scale * _noise(k, seed + 3)                   # gravity on Z
    if scenario == "critical":                                # occasional impacts
        spikes = (_noise(k, seed + 4) > 0.9) * 0.25
        ax, ay = ax + spikes, ay - spikes
    power = pd.Series(ax**2 + ay**2 + (az - 1.0) ** 2)
    rms = np.sqrt(power.rolling(5, min_periods=1).mean()).to_numpy()   # smoothed over 5 windows
    sensor_hist = pd.DataFrame({"timestamp": timestamps, "ax": ax, "ay": ay, "az": az, "rms": rms})
    last = sensor_hist.iloc[-1]

    # --- IMS ------------------------------------------------------------------
    score = (p["ims_base"] + p["ims_trend"] * frac
             + 0.03 * _noise(k, seed + 5) + 0.02 * np.sin(k / 17.0)).clip(0, 1)
    ims_hist = pd.DataFrame({"timestamp": timestamps, "score": score})
    ims_score = float(score[-1])

    # --- C-MAPSS (RUL trend over the last 60 cycles) ---------------------------
    n_cyc = 60
    j = np.arange(n_cyc)
    cycles = 140 - n_cyc + 1 + j
    rul_vals = p["rul"] + p["rul_slope"] * (n_cyc - 1 - j) + 2 * _noise(cycles.astype(float), seed + 6)
    rul_vals[-1] = p["rul"]
    rul_hist = pd.DataFrame({"cycle": cycles, "rul": rul_vals.clip(0)})

    return {
        "mode": "mock",
        "is_mock": True,
        "machine_id": machine_id,
        "generated_at": now,
        "sensor": {
            "available": True,
            "latest": {
                "rms": float(last["rms"]), "ax": float(last["ax"]),
                "ay": float(last["ay"]), "az": float(last["az"]),
                "sampling_rate_hz": SAMPLING_RATE_HZ, "timestamp": now,
            },
            "history": sensor_hist,
            "note": None,
        },
        "cwru": {"available": True, "fault_class": p["fault"], "confidence": p["conf"]},
        "ims": {
            "available": True, "score": ims_score, "threshold": IMS_THRESHOLD,
            "is_anomaly": ims_score > IMS_THRESHOLD, "history": ims_hist,
        },
        "cmapss": {"available": True, "rul": float(p["rul"]), "unit": "cycles", "history": rul_hist},
        "system": {
            "backend": ("Not used", "Demo mode does not call FastAPI"),
            "models": {
                "cwru": ("Simulated", "XGBoost classifier is not loaded"),
                "ims": ("Simulated", "Isolation Forest is not loaded"),
                "cmapss": ("Simulated", "LSTM is not loaded"),
            },
            "data_source": "Mock data (generated in mock_data.py)",
            "connection": ("Offline by design", "No network request is made"),
        },
    }
