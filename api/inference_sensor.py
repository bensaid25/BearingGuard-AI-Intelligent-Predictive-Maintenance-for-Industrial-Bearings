"""
api/inference_sensor.py
=========================

Logic for POST /sensor-data: validates and accepts raw ESP32/MPU6050
vibration windows, and computes DIAGNOSTIC per-axis feature values by
reusing the EXACT SAME feature-computation functions api/inference_ims.py
uses for the trained IMS pipeline.

WHY THIS DOES NOT SCORE ANOMALIES (deliberately deferred):
The saved IMS scaler + IsolationForest (per run, in models/production/ims/)
were calibrated on a specific NASA bearing test rig, sampled at 20,000 Hz
over fixed 20,480-sample windows, with a channel count fixed at 4 or 8
(the physical number of accelerometers on that rig). An ESP32 + MPU6050
mounted on an arbitrary motor is:
  - a different sensor, on different hardware, with different amplitude
    characteristics the scaler was never fit on;
  - typically sampled far slower (the example payload uses 100 Hz, not
    20,000 Hz), which changes the whole frequency range the FFT-based
    features are computed over;
  - 3-axis (ax, ay, az) rather than the rig's per-channel single-axis
    layout, with no established count matching IMS_RUN_CHANNEL_COUNTS.

Feeding computed features from this sensor into that scaler would run
without crashing, but the output would not be a statistically meaningful
anomaly score -- it would silently look like a real result while being
uncalibrated for this hardware. Rather than guess, this module computes
and returns the SAME diagnostic features (so the numbers are directly
comparable in kind to what IMS uses) without applying the mismatched
scaler/model. See api/schemas.py's SensorVibrationResponse for the
"note" field explaining this to API callers too.

Once real baseline data has been collected from this exact sensor setup
and a scaler + anomaly model have been fit for it (a modeling task, not
an adapter -- explicitly out of scope here), scoring can be added the
same way inference_ims.py does it today.
"""

import logging
from typing import Dict, List

import numpy as np

from .inference_ims import compute_frequency_domain_features, compute_time_domain_features
from .schemas import AxisFeatureSummary, SensorSample, SensorVibrationRequest, SensorVibrationResponse

logger = logging.getLogger("api.inference_sensor")

AXES = ("ax", "ay", "az")


def _assert_finite(value: float, context: str) -> None:
    """Raise a clear error if a computed feature is NaN or infinite --
    this is what actually catches "insufficient samples" (e.g. a 1-sample
    window makes std=0, which makes crest_factor a NaN division) rather
    than an arbitrary invented minimum-sample-count rule."""
    if not np.isfinite(value):
        raise ValueError(
            f"Non-finite (NaN or infinite) value computing {context}. "
            f"This usually means the submitted window has too few samples "
            f"for a meaningful feature computation."
        )


def _extract_axis_signal(samples: List[SensorSample], axis: str) -> np.ndarray:
    return np.array([getattr(s, axis) for s in samples], dtype=float)


def _compute_axis_feature_summary(signal: np.ndarray, sampling_rate_hz: float, axis: str) -> AxisFeatureSummary:
    # Reuses the EXACT functions inference_ims.py uses for the real IMS
    # pipeline -- not reimplemented, not approximated.
    time_feats = compute_time_domain_features(signal)
    freq_feats = compute_frequency_domain_features(
        signal,
        sampling_freq_hz=sampling_rate_hz,  # the ESP32's ACTUAL rate, not IMS's hardcoded 20kHz
        max_freq_hz=sampling_rate_hz / 2,   # Nyquist for this rate, not IMS's hardcoded 2kHz band
    )

    all_feats = {**time_feats, **freq_feats}
    for name, value in all_feats.items():
        _assert_finite(value, f"{axis}.{name}")

    return AxisFeatureSummary(**all_feats)


def process_sensor_data(request: SensorVibrationRequest) -> SensorVibrationResponse:
    """Validate-and-summarize one ESP32/MPU6050 window. No model scoring."""
    logger.info(
        "Processing sensor window: device_id=%s, samples=%d, sampling_rate_hz=%s",
        request.device_id, len(request.samples), request.sampling_rate_hz,
    )

    feature_summary: Dict[str, AxisFeatureSummary] = {}
    for axis in AXES:
        signal = _extract_axis_signal(request.samples, axis)
        feature_summary[axis] = _compute_axis_feature_summary(signal, request.sampling_rate_hz, axis)

    return SensorVibrationResponse(
        device_id=request.device_id,
        timestamp=request.timestamp,
        samples_received=len(request.samples),
        status="received",
        feature_summary=feature_summary,
    )
