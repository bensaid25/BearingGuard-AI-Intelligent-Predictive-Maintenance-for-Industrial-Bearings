"""
api/app.py
==========

The FastAPI application itself. At this stage it only:
  - Loads every production model + scaler ONCE, at startup (via
    api/model_loader.py).
  - Exposes GET /health, which reports whether that loading succeeded.

Prediction endpoints (/predict/cwru, /predict/cmapss, /predict/ims) are
deliberately NOT implemented yet -- those come once the inference modules
are built.

Run with (from the project root):
    uvicorn api.app:app --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict

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


@app.post("/sensor-data", response_model=SensorVibrationResponse)
def sensor_data_endpoint(request: SensorVibrationRequest) -> SensorVibrationResponse:
    """Ingests a raw ESP32/MPU6050 vibration window. Validates input and
    returns diagnostic per-axis features (reusing the IMS feature-
    computation code) -- does NOT run anomaly scoring. See
    api/inference_sensor.py for why that's deliberately deferred."""
    logger.info(
        "Received /sensor-data request (device_id=%s, samples=%d)",
        request.device_id, len(request.samples),
    )
    try:
        return process_sensor_data(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Sensor data processing failed")
        raise HTTPException(status_code=500, detail=f"Sensor data processing failed: {exc}")
