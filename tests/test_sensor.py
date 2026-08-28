"""
tests/test_sensor.py
======================

Tests for POST /sensor-data.

Unlike test_cwru.py / test_ims.py / test_cmapss.py, this endpoint has no
"already validated real sample" yet -- it's brand new, ingestion-only (see
api/inference_sensor.py for why anomaly scoring is deliberately deferred).
These tests use synthetic-but-realistic accelerometer values (small
oscillation around gravity on the z-axis) purely to exercise the HTTP
contract -- validation and response shape -- not to claim real-world
validation against an actual ESP32.
"""

import math


def _make_payload(num_samples=50, sampling_rate_hz=100):
    return {
        "device_id": "motor_01",
        "timestamp": "2026-08-28T12:00:00Z",
        "sampling_rate_hz": sampling_rate_hz,
        "samples": [
            {
                "ax": 0.1 * math.sin(i / 5),
                "ay": 0.05 * math.cos(i / 7),
                "az": 9.8 + 0.02 * math.sin(i / 3),
            }
            for i in range(num_samples)
        ],
    }


def test_valid_sensor_payload_returns_feature_summary(client):
    response = client.post("/sensor-data", json=_make_payload())

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body["device_id"] == "motor_01"
    assert body["samples_received"] == 50
    assert body["status"] == "received"
    assert "note" in body  # explains no anomaly scoring is performed here

    assert set(body["feature_summary"].keys()) == {"ax", "ay", "az"}
    for axis in ("ax", "ay", "az"):
        axis_features = body["feature_summary"][axis]
        for key in (
            "mean", "std", "rms", "peak_abs_amplitude", "peak_to_peak",
            "skewness", "kurtosis", "crest_factor", "dominant_frequency_hz",
            "spectral_energy", "spectral_centroid_hz",
        ):
            assert key in axis_features, f"{axis} feature summary missing '{key}'"
            assert isinstance(axis_features[key], (int, float))
            assert math.isfinite(axis_features[key]), f"{axis}.{key} is not finite"

    # This endpoint deliberately does NOT produce an anomaly verdict --
    # confirm that design decision holds in the actual response.
    assert "anomaly" not in body
    assert "anomaly_score" not in body


def test_empty_samples_returns_422(client):
    payload = _make_payload()
    payload["samples"] = []

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for empty samples, got {response.status_code}: {response.text}"
    )


def test_malformed_sample_returns_422(client):
    payload = _make_payload()
    payload["samples"] = [{"ax": 0.1, "ay": 0.1}]  # missing az

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for a malformed sample (missing az), got "
        f"{response.status_code}: {response.text}"
    )


def test_wrong_numeric_type_returns_422(client):
    payload = _make_payload()
    payload["samples"] = [{"ax": "not-a-number", "ay": 0.1, "az": 9.8}]

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for a wrong-type field, got "
        f"{response.status_code}: {response.text}"
    )


def test_insufficient_samples_returns_400(client):
    # A single sample makes std=0 for that axis, which makes crest_factor
    # a NaN division -- this is what actually defines "insufficient" here
    # (see inference_sensor.py's _assert_finite), not an arbitrary invented
    # minimum sample count.
    payload = _make_payload(num_samples=1)

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 400, (
        f"Expected 400 for an insufficient (1-sample) window, got "
        f"{response.status_code}: {response.text}. Note: this is 400 "
        f"(a ValueError from feature computation), not 422 -- matching the "
        f"same convention the existing CWRU/IMS/C-MAPSS endpoints already "
        f"use for non-finite computed values."
    )


def test_missing_device_id_returns_422(client):
    payload = _make_payload()
    del payload["device_id"]

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for a missing device_id, got {response.status_code}: {response.text}"
    )


def test_invalid_timestamp_returns_422(client):
    payload = _make_payload()
    payload["timestamp"] = "not-a-valid-timestamp"

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for an invalid timestamp, got {response.status_code}: {response.text}"
    )


def test_non_positive_sampling_rate_returns_422(client):
    payload = _make_payload()
    payload["sampling_rate_hz"] = 0

    response = client.post("/sensor-data", json=payload)

    assert response.status_code == 422, (
        f"Expected 422 for a non-positive sampling_rate_hz, got "
        f"{response.status_code}: {response.text}"
    )
