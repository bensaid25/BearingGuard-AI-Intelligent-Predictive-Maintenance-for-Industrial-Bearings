"""
api/schemas.py
===============

Pydantic models describing every request body and response body the API
uses. Keeping these in one file means the "shape" of the API is defined in
exactly one place, separate from the model-loading logic and (later) the
inference logic.

Nothing in this file loads a model or does any inference -- it only
validates data going in and structures data coming out.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------
# These counts are the REAL, confirmed contracts (checked against the saved
# scalers' feature_names_in_ and the Keras model's input_shape) -- not
# guesses. They're used below purely for validation (checking lengths),
# not for feature computation (that comes later, in the inference modules).
CWRU_FEATURE_COUNT = 12
CMAPSS_SEQUENCE_LENGTH = 30
CMAPSS_FEATURE_COUNT = 225
IMS_FEATURE_COUNT = 11  # not directly used yet -- see IMS section below


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    """Response for GET /health."""
    status: Literal["ok", "degraded"]
    # Per-model-group loaded flags, e.g. {"cwru": true, "cmapss": true, "ims": true}
    models_loaded: Dict[str, bool]


# ---------------------------------------------------------------------------
# CWRU -- fully known contract (12 named features, in this exact order)
# ---------------------------------------------------------------------------
class CWRURequest(BaseModel):
    """The 12 pre-computed CWRU features, already extracted by the caller.

    Field order below matches the order the saved scaler.joblib expects
    (confirmed via scaler.feature_names_in_): rms, kurtosis, skewness,
    peak_to_peak, std, dominant_freq, spectral_energy, spectral_centroid,
    energy_0_1000, energy_1000_2500, energy_2500_5000, load.
    """
    rms: float
    kurtosis: float
    skewness: float
    peak_to_peak: float
    std: float
    dominant_freq: float
    spectral_energy: float
    spectral_centroid: float
    energy_0_1000: float
    energy_1000_2500: float
    energy_2500_5000: float
    load: float


class CWRUResponse(BaseModel):
    """Response for POST /predict/cwru (once that endpoint exists)."""
    predicted_class: Literal["Ball", "InnerRace", "Normal", "OuterRace"]
    # Per-class probabilities, if the model exposes predict_proba(). Optional
    # because not every classifier wrapper is guaranteed to support it.
    probabilities: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# C-MAPSS -- now fully known (named-feature contract, no longer temporary)
# ---------------------------------------------------------------------------
# Confirmed against scaler_fd001.joblib's feature_names_in_ (order matters):
#   raw sensors (15) -> rolling_mean (45) -> rolling_std (45)
#   -> rolling_min (45) -> rolling_max (45) -> trend_slope (30) = 225
CMAPSS_SENSOR_COLS = [
    "sensor_2", "sensor_3", "sensor_4", "sensor_6", "sensor_7", "sensor_8",
    "sensor_9", "sensor_11", "sensor_12", "sensor_13", "sensor_14",
    "sensor_15", "sensor_17", "sensor_20", "sensor_21",
]
CMAPSS_ROLLING_WINDOWS = [5, 10, 20]
CMAPSS_TREND_WINDOWS = [10, 20]

CMAPSS_FEATURE_ORDER = (
    list(CMAPSS_SENSOR_COLS)
    + [f"{c}_roll{w}_mean" for w in CMAPSS_ROLLING_WINDOWS for c in CMAPSS_SENSOR_COLS]
    + [f"{c}_roll{w}_std" for w in CMAPSS_ROLLING_WINDOWS for c in CMAPSS_SENSOR_COLS]
    + [f"{c}_roll{w}_min" for w in CMAPSS_ROLLING_WINDOWS for c in CMAPSS_SENSOR_COLS]
    + [f"{c}_roll{w}_max" for w in CMAPSS_ROLLING_WINDOWS for c in CMAPSS_SENSOR_COLS]
    + [f"{c}_trend{w}" for w in CMAPSS_TREND_WINDOWS for c in CMAPSS_SENSOR_COLS]
)
assert len(CMAPSS_FEATURE_ORDER) == CMAPSS_FEATURE_COUNT
assert len(set(CMAPSS_FEATURE_ORDER)) == CMAPSS_FEATURE_COUNT  # no duplicates


class CMAPSSRequest(BaseModel):
    """The last 30 timesteps, each a dict of the 225 named engineered features.

    Each entry in `sequence` must be a dict whose keys are EXACTLY the 225
    names in CMAPSS_FEATURE_ORDER. Using names (not list position) means
    JSON key order can never silently misalign a value with the wrong
    feature -- the inference module looks each one up by name.
    """
    sequence: List[Dict[str, float]]

    @field_validator("sequence")
    @classmethod
    def check_sequence_shape(cls, value: List[Dict[str, float]]):
        if len(value) != CMAPSS_SEQUENCE_LENGTH:
            raise ValueError(
                f"sequence must have exactly {CMAPSS_SEQUENCE_LENGTH} "
                f"timesteps, got {len(value)}"
            )
        expected_keys = set(CMAPSS_FEATURE_ORDER)
        for i, row in enumerate(value):
            row_keys = set(row.keys())
            if row_keys != expected_keys:
                missing = expected_keys - row_keys
                extra = row_keys - expected_keys
                raise ValueError(
                    f"timestep {i}: missing features {sorted(missing)}; "
                    f"unexpected features {sorted(extra)}"
                )
        return value


class CMAPSSResponse(BaseModel):
    """Response for POST /predict/cmapss (once that endpoint exists).

    Confirmed via best.keras's output_shape: a single RUL value per request.
    """
    predicted_rul: float


# ---------------------------------------------------------------------------
# IMS -- known 11-feature contract, raw-signal request
# ---------------------------------------------------------------------------
# Feature order (from the IMS feature-engineering notebook, confirmed
# against n_features_in_ == 11 on the saved scalers):
#   mean, std, rms, peak_abs_amplitude, peak_to_peak, skewness, kurtosis,
#   crest_factor, dominant_frequency_hz, spectral_energy, spectral_centroid_hz
# This list isn't used directly in this file (it belongs to the inference
# module that will compute these 11 values from the raw signal below) --
# it's noted here so the contract is documented next to the schema it feeds.
IMS_FEATURE_ORDER = [
    "mean", "std", "rms", "peak_abs_amplitude", "peak_to_peak", "skewness",
    "kurtosis", "crest_factor", "dominant_frequency_hz", "spectral_energy",
    "spectral_centroid_hz",
]
assert len(IMS_FEATURE_ORDER) == IMS_FEATURE_COUNT

# Expected channel count per run -- also confirmed, used for validation.
IMS_RUN_CHANNEL_COUNTS = {"1st_test": 8, "2nd_test": 4, "3rd_test": 4}
IMS_SAMPLES_PER_SNAPSHOT = 20480  # confirmed sample count per channel signal


class IMSChannelReading(BaseModel):
    """One channel's raw vibration signal."""
    channel: str  # a label for this channel, e.g. "channel_1" -- echoed back in the response
    signal: List[float]

    @field_validator("signal")
    @classmethod
    def check_signal_length(cls, value: List[float]):
        if len(value) != IMS_SAMPLES_PER_SNAPSHOT:
            raise ValueError(
                f"signal must have exactly {IMS_SAMPLES_PER_SNAPSHOT} "
                f"samples, got {len(value)}"
            )
        return value


class IMSRequest(BaseModel):
    """Request for POST /predict/ims (once that endpoint exists).

    One request = all channels for the given run at once, since channel
    count differs by run (1st_test=8 channels, 2nd_test/3rd_test=4).
    """
    run: Literal["1st_test", "2nd_test", "3rd_test"]
    channels: List[IMSChannelReading]

    @field_validator("channels")
    @classmethod
    def check_channels_not_empty(cls, value: List[IMSChannelReading]):
        if len(value) == 0:
            raise ValueError("channels must not be empty")
        return value


class IMSChannelResult(BaseModel):
    channel: str
    anomaly_score: float  # higher = more anomalous
    is_anomaly: bool      # True when the model's own predict() says outlier (-1)
    model_predict: int    # raw sklearn label: 1 = inlier, -1 = outlier


class IMSResponse(BaseModel):
    run: str
    results: List[IMSChannelResult]
