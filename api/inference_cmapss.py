"""
api/inference_cmapss.py
========================

C-MAPSS Remaining-Useful-Life inference.
"""

import numpy as np
import pandas as pd

from .schemas import (
    CMAPSS_FEATURE_ORDER,
    CMAPSS_SEQUENCE_LENGTH,
    CMAPSSRequest,
    CMAPSSResponse,
)


def _assert_finite(array: np.ndarray, context: str) -> None:
    """Raise a clear error if any value is NaN or infinite."""
    if not np.all(np.isfinite(array)):
        raise ValueError(
            f"Non-finite (NaN or infinite) value found in {context}."
        )


def predict_cmapss(
    request: CMAPSSRequest,
    cmapss_artifacts: dict,
) -> CMAPSSResponse:

    model = cmapss_artifacts["model"]
    scaler = cmapss_artifacts["scaler"]

    matrix = np.array(
        [
            [row[name] for name in CMAPSS_FEATURE_ORDER]
            for row in request.sequence
        ],
        dtype=float,
    )

    # Verify the expected dimensions before continuing.
    if matrix.shape != (
        CMAPSS_SEQUENCE_LENGTH,
        len(CMAPSS_FEATURE_ORDER),
    ):
        raise ValueError(
            "Invalid C-MAPSS feature matrix shape: "
            f"expected "
            f"({CMAPSS_SEQUENCE_LENGTH}, {len(CMAPSS_FEATURE_ORDER)}), "
            f"got {matrix.shape}."
        )

    _assert_finite(
        matrix,
        "C-MAPSS request features",
    )

    features_df = pd.DataFrame(
        matrix,
        columns=CMAPSS_FEATURE_ORDER,
    )

    scaled = scaler.transform(features_df)

    sequence_input = scaled.reshape(
        1,
        CMAPSS_SEQUENCE_LENGTH,
        len(CMAPSS_FEATURE_ORDER),
    )

    
    # Run the saved Keras model.
    
    prediction = model(
    sequence_input,
    training=False,
)

    prediction_array = np.asarray(prediction)

    if prediction_array.size != 1:
        raise ValueError(
            f"Unexpected C-MAPSS model output shape: "
            f"{prediction_array.shape}. Expected exactly one RUL value."
        )

    predicted_rul = prediction_array.reshape(-1)[0].item()

    return CMAPSSResponse(
        predicted_rul=predicted_rul,
    )