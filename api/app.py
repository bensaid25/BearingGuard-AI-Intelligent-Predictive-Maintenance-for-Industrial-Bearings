"""
api/app.py
==========

The FastAPI application itself. At this stage it:
  - Loads every production model + scaler ONCE, at startup (via
    api/model_loader.py).
  - Exposes GET /health, which reports whether that loading succeeded.
  - Exposes the /predict/* endpoints and /sensor-data ingestion.
  - Caches the most recent /sensor-data reading in memory, so a dashboard
    can poll GET /sensor-data/latest to show live vibration values without
    needing its own separate storage layer. This is intentionally a plain
    in-memory cache (not a database) -- it exists purely for live display,
    holds at most SENSOR_HISTORY_MAXLEN points, and is lost on restart.
    It is NOT used for anomaly scoring or any /predict/* logic.

Run with (from the project root):
    uvicorn api.app:app --reload
"""

import logging
import math
from collections import deque
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException

from .inference_cmapss import predict_cmapss
from .inference_cwru import predict_cwru
from .inference_ims import predict_ims
from .inference_sensor import process_sensor_data
from .model_loader import load_all_models
from .schemas import (
    CMAPSSRequest,
    CMAPSSResponse,
    CWRURequest,
    CWRUResponse,
    HealthResponse,
    IMSRequest,
    IMSResponse,
    SensorVibrationRequest,
    SensorVibrationResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("api.app")

# Simple in-memory state, filled in once at startup by the lifespan function
# below. app_state["models"] holds the loaded artifacts (see model_loader.py
# for the exact shape); app_state["models_loaded"] is a quick success flag.
app_state: Dict[str, object] = {"models": None, "models_loaded": False}

# --- Live sensor cache (display only, not used for inference) -----------------
SENSOR_HISTORY_MAXLEN = 200
app_state["latest_sensor"] = None  # type: Optional[dict]
app_state["sensor_history"] = deque(maxlen=SENSOR_HISTORY_MAXLEN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup -----------------------------------------------------
    logger.info("Startup: loading production models...")
    try:
        app_state["models"] = load_all_models()
        app_state["models_loaded"] = True
        logger.info("Startup complete: all models loaded successfully.")
    except Exception:
        # Deliberately NOT re-raised: the server still starts, so GET
        # /health can report the problem clearly (status: "degraded")
        # instead of the process just failing to come up with no
        # explanation visible to whoever is checking on it.
        app_state["models"] = None
        app_state["models_loaded"] = False
        logger.exception("Model loading FAILED during startup. "
                          "The API will run, but /health will report 'degraded'.")

    yield

    # ---- Shutdown ------------------------------------------------------
    app_state["models"] = None
    app_state["models_loaded"] = False
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Predictive Maintenance API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Reports overall status, plus whether each model group loaded."""
    models = app_state.get("models") or {}
    return HealthResponse(
        status="ok" if app_state.get("models_loaded") else "degraded",
        models_loaded={
            "cwru": "cwru" in models,
            "cmapss": "cmapss" in models,
            "ims": "ims" in models,
        },
    )


def _require_models_loaded() -> Dict[str, object]:
    """Shared guard for every /predict/* endpoint: refuse to run inference
    if startup model loading failed, instead of crashing with a confusing
    KeyError deep inside an inference module."""
    if not app_state.get("models_loaded"):
        raise HTTPException(
            status_code=503,
            detail="Models are not loaded. Check GET /health for details.",
        )
    return app_state["models"]  # type: ignore[return-value]


@app.post("/predict/cwru", response_model=CWRUResponse)
def predict_cwru_endpoint(request: CWRURequest) -> CWRUResponse:
    logger.info("Received /predict/cwru request")
    models = _require_models_loaded()
    try:
        return predict_cwru(request, models["cwru"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("CWRU prediction failed")
        raise HTTPException(status_code=500, detail=f"CWRU prediction failed: {exc}")


@app.post("/predict/cmapss", response_model=CMAPSSResponse)
def predict_cmapss_endpoint(request: CMAPSSRequest) -> CMAPSSResponse:
    logger.info("Received /predict/cmapss request")
    models = _require_models_loaded()
    try:
        return predict_cmapss(request, models["cmapss"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("C-MAPSS prediction failed")
        raise HTTPException(status_code=500, detail=f"C-MAPSS prediction failed: {exc}")


@app.post("/predict/ims", response_model=IMSResponse)
def predict_ims_endpoint(request: IMSRequest) -> IMSResponse:
    logger.info("Received /predict/ims request (run=%s, channels=%d)", request.run, len(request.channels))
    models = _require_models_loaded()
    try:
        ims_run_artifacts = models["ims"][request.run]
        return predict_ims(request, ims_run_artifacts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("IMS prediction failed")
        raise HTTPException(status_code=500, detail=f"IMS prediction failed: {exc}")


def _update_sensor_cache(request: SensorVibrationRequest, response: SensorVibrationResponse) -> None:
    """Store a lightweight, display-only summary of this window: the mean
    reading per axis (from the already-computed feature summary, not
    recomputed here) and a combined vibration magnitude.

    The combined magnitude uses per-axis STANDARD DEVIATION, not raw RMS --
    std is gravity-independent (it measures fluctuation around each axis's
    own mean), so az's ~9.8 m/s^2 gravity offset doesn't drown out the
    smaller ax/ay vibration signal. This mirrors the same std-based
    comparison already used to validate the sensor (running vs. stopped),
    not a new/different metric invented for the dashboard.
    """
    fs = response.feature_summary
    ax_std, ay_std, az_std = fs["ax"].std, fs["ay"].std, fs["az"].std
    combined_magnitude = math.sqrt(ax_std**2 + ay_std**2 + az_std**2)

    point = {
        "device_id": response.device_id,
        "timestamp": response.timestamp,
        "sampling_rate_hz": request.sampling_rate_hz,
        "ax": fs["ax"].mean,
        "ay": fs["ay"].mean,
        "az": fs["az"].mean,
        "rms": combined_magnitude,
    }
    app_state["latest_sensor"] = point
    app_state["sensor_history"].append(point)  # type: ignore[union-attr]


@app.post("/sensor-data", response_model=SensorVibrationResponse)
def sensor_data_endpoint(request: SensorVibrationRequest) -> SensorVibrationResponse:
    """Ingests a raw ESP32/MPU6050 vibration window. Validates input and
    returns diagnostic per-axis features (reusing the IMS feature-
    computation code) -- does NOT run anomaly scoring. See
    api/inference_sensor.py for why that's deliberately deferred.

    Also updates the in-memory latest-reading cache (see
    _update_sensor_cache) so GET /sensor-data/latest can serve it to a
    live dashboard. This has no effect on the response returned here.
    """
    logger.info(
        "Received /sensor-data request (device_id=%s, samples=%d)",
        request.device_id, len(request.samples),
    )
    try:
        response = process_sensor_data(request)
        _update_sensor_cache(request, response)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Sensor data processing failed")
        raise HTTPException(status_code=500, detail=f"Sensor data processing failed: {exc}")


@app.get("/sensor-data/latest")
def sensor_data_latest() -> dict:
    """Returns the most recent /sensor-data reading, plus recent history for
    charting, for live-display purposes only (e.g. a dashboard). This is a
    plain in-memory cache: it is empty until at least one /sensor-data POST
    has been received, and is lost on server restart. It performs no
    computation of its own and is not part of the inference contract.
    """
    latest = app_state.get("latest_sensor")
    if latest is None:
        return {
            "available": False,
            "reason": "No /sensor-data reading has been received yet.",
        }
    return {
        "available": True,
        "latest": latest,
        "history": list(app_state["sensor_history"]),  # type: ignore[arg-type]
    }
