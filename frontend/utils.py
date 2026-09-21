"""Shared helpers: data entry point, status rule and formatting (no drawing code, see theme.py).

The dashboard (app.py) gets ALL its data from get_dashboard_data(). Switching between
mock data and the real backend never touches the UI code.
"""
from __future__ import annotations

from datetime import datetime

import api_client
import mock_data

DEFAULT_BASE_URL = api_client.DEFAULT_BASE_URL
SOURCE_MOCK = "Demo mode (mock data)"
SOURCE_BACKEND = "FastAPI backend"
SCENARIOS = mock_data.SCENARIOS

# --- Display rules (dashboard heuristics, NOT model outputs) --------------------------
RUL_WARNING_CYCLES = 60
RUL_CRITICAL_CYCLES = 30
CWRU_MIN_CONFIDENCE = 0.70
IMS_HIGHER_IS_ANOMALOUS = True   # flip if the backend score is lower = more anomalous



# --- Single data entry point ----------------------------------------------------------
def get_dashboard_data(source: str, machine_id: str, scenario: str = "normal",
                       base_url: str = DEFAULT_BASE_URL) -> dict:
    if source == SOURCE_MOCK:
        return mock_data.generate_mock_dashboard_data(machine_id, scenario)
    return api_client.get_backend_dashboard_data(base_url, machine_id)


# --- Overall status --------------------------------------------------------------------
def compute_overall_status(d: dict) -> tuple[str, list[str]]:
    """Combine the three model outputs into NORMAL / WARNING / CRITICAL (or UNKNOWN)."""
    levels: list[int] = []
    reasons: list[str] = []

    cw = d["cwru"]
    if cw.get("available"):
        fault = str(cw["fault_class"])
        conf = cw.get("confidence") or 0
        if fault.lower() != "normal" and conf >= CWRU_MIN_CONFIDENCE:
            levels.append(1)
            reasons.append(f"CWRU classifies the bearing as '{fault}' ({conf:.0%} confidence).")
        else:
            levels.append(0)

    ims = d["ims"]
    if ims.get("available"):
        if ims.get("is_anomaly"):
            levels.append(1)
            reasons.append(f"IMS reports an anomaly (score {ims['score']:.2f}).")
        else:
            levels.append(0)

    rul = d["cmapss"]
    if rul.get("available") and rul.get("rul") is not None:
        v = float(rul["rul"])
        if v < RUL_CRITICAL_CYCLES:
            levels.append(2)
            reasons.append(f"Predicted RUL is {v:.0f} cycles, under {RUL_CRITICAL_CYCLES}.")
        elif v < RUL_WARNING_CYCLES:
            levels.append(1)
            reasons.append(f"Predicted RUL is {v:.0f} cycles, under {RUL_WARNING_CYCLES}.")
        else:
            levels.append(0)

    if not levels:
        return "UNKNOWN", ["No AI result is available yet."]
    top = max(levels)
    if top == 1 and sum(l >= 1 for l in levels) >= 2:
        top = 2
        reasons.append("Two or more indicators are raised at the same time.")
    if top == 0:
        reasons = ["All available indicators are in their normal range."]
    return ("NORMAL", "WARNING", "CRITICAL")[top], reasons


# --- Formatting ------------------------------------------------------------------------
def fmt_time(ts: datetime | None) -> str:
    return ts.strftime("%H:%M:%S") if ts else "n/a"


def fmt_age(ts: datetime | None) -> str:
    if not ts:
        return ""
    s = max(0, int((datetime.now() - ts).total_seconds()))
    return "just now" if s < 2 else f"{s} s ago"

RUL_DISPLAY_MAX = 150          # only sets the size of the RUL ring, it is not a model limit
IMS_GAUGE_MIN_MAX = 1.0        # IMS gauge shows at least 0 to 1, and grows if the score exceeds it
VIB_GAUGE_MAX_G = 0.6          # full-scale of the vibration gauge (display only)
