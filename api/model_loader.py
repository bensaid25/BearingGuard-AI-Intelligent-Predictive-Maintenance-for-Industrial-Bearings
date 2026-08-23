"""
api/model_loader.py
====================

Loads every PRODUCTION model and scaler from disk, exactly once. Nothing in
this file does any inference or feature engineering -- it only locates and
loads the saved artifacts, and hands them back as plain Python dicts.

Call load_all_models() one time (at API startup) and keep the result around
-- never call it again per-request. Loading a Keras model or unpickling a
scaler is relatively slow, and these artifacts don't change while the API
is running.
"""

import logging
import os
import sys
from pathlib import Path

import joblib

logger = logging.getLogger("api.model_loader")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# This file lives at <PROJECT_ROOT>/api/model_loader.py, so PROJECT_ROOT is
# just "two levels up" from this file. This works no matter where the
# project folder is on disk. It can still be overridden with an environment
# variable if you ever need to point at a different location.
PROJECT_ROOT = Path(os.environ.get("PM_PROJECT_ROOT", Path(__file__).resolve().parent.parent))
MODEL_ROOT = PROJECT_ROOT / "models" / "production"

CWRU_DIR = MODEL_ROOT / "cwru"
CMAPSS_DIR = MODEL_ROOT / "cmapss"
IMS_DIR = MODEL_ROOT / "ims"

# IMPORTANT: cwru_fault_classifier.joblib was saved as an instance of a
# CUSTOM class (src.models.xgb_wrapper.XGBStringClassifier). joblib needs to
# be able to IMPORT that class to unpickle the file, so PROJECT_ROOT (which
# contains the `src` package) must be on sys.path before that file loads.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The three IMS runs. Each has its OWN model + scaler pair -- these are
# NOT merged into one model. That's a future decision, not something this
# loader should do on its own.
IMS_RUNS = ["1st_test", "2nd_test", "3rd_test"]


# ---------------------------------------------------------------------------
# Small helper: fail clearly and immediately if a file is missing
# ---------------------------------------------------------------------------
def _require_file(path: Path) -> Path:
    """Raise a clear error immediately if the given artifact is missing.

    Without this, joblib/keras would raise their own (sometimes cryptic)
    error further down. This makes "which file is missing" obvious.
    """
    if not path.exists():
        raise FileNotFoundError(f"Required model artifact not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Per-model-group loaders
# ---------------------------------------------------------------------------
def load_cwru() -> dict:
    """Load the CWRU classifier + its scaler. Returns {"model": ..., "scaler": ...}."""
    model_path = _require_file(CWRU_DIR / "cwru_fault_classifier.joblib")
    scaler_path = _require_file(CWRU_DIR / "scaler.joblib")

    logger.info("Loading CWRU model: %s", model_path)
    model = joblib.load(model_path)
    logger.info("Loading CWRU scaler: %s", scaler_path)
    scaler = joblib.load(scaler_path)

    return {"model": model, "scaler": scaler}


def load_cmapss() -> dict:
    """Load the C-MAPSS LSTM model + its scaler. Returns {"model": ..., "scaler": ...}."""
    model_path = _require_file(CMAPSS_DIR / "best.keras")
    scaler_path = _require_file(CMAPSS_DIR / "scaler_fd001.joblib")

    # Imported here (not at module top) so this file can still be imported
    # -- e.g. to load just the CWRU model -- in an environment where
    # tensorflow isn't installed yet.
    from tensorflow import keras

    logger.info("Loading C-MAPSS model: %s", model_path)
    model = keras.models.load_model(model_path)
    logger.info("Loading C-MAPSS scaler: %s", scaler_path)
    scaler = joblib.load(scaler_path)

    return {"model": model, "scaler": scaler}


def load_ims() -> dict:
    """Load all three IMS models + scalers, kept SEPARATE per run.

    Returns a dict keyed by run name, e.g.:
        {
            "1st_test": {"model": ..., "scaler": ...},
            "2nd_test": {"model": ..., "scaler": ...},
            "3rd_test": {"model": ..., "scaler": ...},
        }

    These are intentionally NOT merged into a single model -- that's a
    decision for later, once the final IMS production architecture is
    settled. For now each run's artifacts are loaded and exposed as-is.
    """
    ims_artifacts = {}
    for run in IMS_RUNS:
        model_path = _require_file(IMS_DIR / f"{run}_isolation_forest.joblib")
        scaler_path = _require_file(IMS_DIR / f"{run}_scaler.joblib")

        logger.info("Loading IMS %s model: %s", run, model_path)
        model = joblib.load(model_path)
        logger.info("Loading IMS %s scaler: %s", run, scaler_path)
        scaler = joblib.load(scaler_path)

        ims_artifacts[run] = {"model": model, "scaler": scaler}

    return ims_artifacts


# ---------------------------------------------------------------------------
# Single entry point used by the API at startup
# ---------------------------------------------------------------------------
def load_all_models() -> dict:
    """Load every production model + scaler exactly once.

    Returns:
        {
            "cwru":   {"model": ..., "scaler": ...},
            "cmapss": {"model": ..., "scaler": ...},
            "ims": {
                "1st_test": {"model": ..., "scaler": ...},
                "2nd_test": {"model": ..., "scaler": ...},
                "3rd_test": {"model": ..., "scaler": ...},
            },
        }

    Raises FileNotFoundError (or whatever joblib/keras raises) immediately
    if any artifact is missing or fails to load -- this function does not
    swallow errors, so the caller (api/app.py) can decide how to react.
    """
    logger.info("Loading all production models from %s", MODEL_ROOT)

    artifacts = {
        "cwru": load_cwru(),
        "cmapss": load_cmapss(),
        "ims": load_ims(),
    }

    logger.info("All production models loaded successfully.")
    return artifacts
