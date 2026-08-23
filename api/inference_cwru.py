"""
api/inference_cwru.py
======================
CWRU fault-classification inference.

"""

import logging

import numpy as np
import pandas as pd

from .schemas import CWRURequest, CWRUResponse

logger = logging.getLogger("api.inference_cwru")


# Exact feature order used by the saved production scaler.
# Confirmed via scaler.feature_names_in_.
CWRU_FEATURE_ORDER = [
    "rms",
    "kurtosis",
    "skewness",
    "peak_to_peak",
    "std",
    "dominant_freq",
    "spectral_energy",
    "spectral_centroid",
    "energy_0_1000",
    "energy_1000_2500",
    "energy_2500_5000",
    "load",
]

assert len(CWRU_FEATURE_ORDER) == 12


def _assert_finite(array: np.ndarray, context: str) -> None:
    """Raise a clear error if any value is NaN or infinite."""
    if not np.all(np.isfinite(array)):
        raise ValueError(
            f"Non-finite (NaN or infinite) value found in {context}."
        )


def predict_cwru(
    request: CWRURequest,
    cwru_artifacts: dict,
) -> CWRUResponse:

    model = cwru_artifacts["model"]
    scaler = cwru_artifacts["scaler"]

    feature_df = pd.DataFrame(
        [[
            request.rms,
            request.kurtosis,
            request.skewness,
            request.peak_to_peak,
            request.std,
            request.dominant_freq,
            request.spectral_energy,
            request.spectral_centroid,
            request.energy_0_1000,
            request.energy_1000_2500,
            request.energy_2500_5000,
            request.load,
        ]],
        columns=CWRU_FEATURE_ORDER,
    )
    _assert_finite(
        feature_df.to_numpy(dtype=float),
        "CWRU request features",
    )

    scaled = scaler.transform(feature_df)

    predicted_class = str(model.predict(scaled)[0])

    probabilities = None

    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(scaled)[0]
            classes = getattr(model, "classes_", None)

            if classes is not None:
                probabilities = {
                    str(c): float(p)
                    for c, p in zip(classes, proba)
                }

        except Exception as exc:
            logger.warning(
                "CWRU model has predict_proba but it raised: %s",
                exc,
            )

    return CWRUResponse(
        predicted_class=predicted_class,
        probabilities=probabilities,
    )