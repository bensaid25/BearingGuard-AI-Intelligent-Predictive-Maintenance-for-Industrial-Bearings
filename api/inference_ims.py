"""
api/inference_ims.py
=====================

IMS anomaly-detection inference. Takes the raw vibration signal per
channel, computes the same 11 time/frequency-domain features the models
were trained on (ported from 02_IMS_Feature_Engineering.ipynb), scales
with the SAVED scaler for that run, and scores with the SAVED Isolation
Forest for that run.

Anomaly convention (matches the user's own score_run() function):
    anomaly_score = -model.decision_function(scaled_X)   # higher = more anomalous
    is_anomaly    = model.predict(scaled_X) == -1          # sklearn's own label

This module knows nothing about FastAPI or HTTP -- it raises plain
ValueError on bad input, and the endpoint in api/app.py turns that into an
HTTP error response.
"""

from typing import Dict

import numpy as np
from scipy import stats
from scipy.signal import detrend as linear_detrend

from .schemas import (
    IMS_FEATURE_ORDER,
    IMS_RUN_CHANNEL_COUNTS,
    IMSChannelResult,
    IMSRequest,
    IMSResponse,
)

# Signal constants from 02_IMS_Feature_Engineering.ipynb.
IMS_SAMPLING_FREQ_HZ = 20000
IMS_MAX_FREQ_HZ = 2000


def _assert_finite(array: np.ndarray, context: str) -> None:
    if not np.all(np.isfinite(array)):
        raise ValueError(f"Non-finite (NaN or infinite) value found in {context}.")


def compute_time_domain_features(signal: np.ndarray) -> Dict[str, float]:
    """Time-domain features. crest_factor is NaN (not inf) if RMS is 0,
    matching the notebook's behavior -- caught by _assert_finite() below.
    """
    signal = np.asarray(signal, dtype=float)

    mean = np.mean(signal)
    std = np.std(signal)
    rms = np.sqrt(np.mean(signal ** 2))
    peak_abs_amplitude = np.max(np.abs(signal))
    peak_to_peak = np.ptp(signal)
    skewness = stats.skew(signal)
    kurtosis = stats.kurtosis(signal)  # excess (Fisher) kurtosis
    crest_factor = (peak_abs_amplitude / rms) if rms != 0 else np.nan

    return {
        "mean": mean,
        "std": std,
        "rms": rms,
        "peak_abs_amplitude": peak_abs_amplitude,
        "peak_to_peak": peak_to_peak,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "crest_factor": crest_factor,
    }


def compute_frequency_domain_features(
    signal: np.ndarray,
    sampling_freq_hz: int = IMS_SAMPLING_FREQ_HZ,
    max_freq_hz: int = IMS_MAX_FREQ_HZ,
) -> Dict[str, float]:
    """FFT-based features. Steps must match the notebook exactly:
    linear detrend -> rfft -> single-sided amplitude scaling -> zero the
    0 Hz bin -> restrict to [0, max_freq_hz].
    """
    signal = np.asarray(signal, dtype=float)
    detrended = linear_detrend(signal)

    n = len(detrended)
    fft_vals = np.fft.rfft(detrended)
    freqs = np.fft.rfftfreq(n, d=1 / sampling_freq_hz)
    magnitude = np.abs(fft_vals) / n
    magnitude[1:-1] *= 2  # single-sided correction (skip DC and Nyquist bins)
    magnitude[0] = 0      # zero the DC bin

    band_mask = freqs <= max_freq_hz
    freqs_band = freqs[band_mask]
    magnitude_band = magnitude[band_mask]

    if len(magnitude_band) > 0 and np.any(magnitude_band > 0):
        dominant_idx = np.argmax(magnitude_band)
        dominant_frequency_hz = freqs_band[dominant_idx]
    else:
        dominant_frequency_hz = np.nan

    spectral_energy = np.sum(magnitude_band ** 2)

    magnitude_sum = np.sum(magnitude_band)
    spectral_centroid_hz = (
        np.sum(freqs_band * magnitude_band) / magnitude_sum if magnitude_sum > 0 else np.nan
    )

    return {
        "dominant_frequency_hz": dominant_frequency_hz,
        "spectral_energy": spectral_energy,
        "spectral_centroid_hz": spectral_centroid_hz,
    }


def compute_ims_feature_vector(signal: np.ndarray) -> np.ndarray:
    """The 11 IMS features for one channel, in IMS_FEATURE_ORDER."""
    time_feats = compute_time_domain_features(signal)
    freq_feats = compute_frequency_domain_features(signal)
    all_feats = {**time_feats, **freq_feats}
    return np.array([all_feats[name] for name in IMS_FEATURE_ORDER], dtype=float)


def predict_ims(request: IMSRequest, ims_run_artifacts: dict) -> IMSResponse:
    """Run IMS inference for one run's worth of channels.

    ims_run_artifacts must be {"model": <IsolationForest>, "scaler": <StandardScaler>}
    for the SPECIFIC run in request.run -- i.e. app.py is responsible for
    picking models["ims"][request.run] before calling this function.
    """
    expected_count = IMS_RUN_CHANNEL_COUNTS[request.run]
    if len(request.channels) != expected_count:
        raise ValueError(
            f"{request.run} expects {expected_count} channels, "
            f"got {len(request.channels)}"
        )

    model = ims_run_artifacts["model"]
    scaler = ims_run_artifacts["scaler"]

    feature_rows = [
        compute_ims_feature_vector(np.array(reading.signal, dtype=float))
        for reading in request.channels
    ]
    feature_matrix = np.array(feature_rows)
    _assert_finite(feature_matrix, f"IMS computed features ({request.run})")

    scaled = scaler.transform(feature_matrix)  # .transform() only

    raw_decision = model.decision_function(scaled)
    anomaly_score = -raw_decision
    model_predict = model.predict(scaled)

    results = [
        IMSChannelResult(
            channel=reading.channel,
            anomaly_score=float(score),
            is_anomaly=bool(pred == -1),
            model_predict=int(pred),
        )
        for reading, score, pred in zip(request.channels, anomaly_score, model_predict)
    ]
    return IMSResponse(run=request.run, results=results)
