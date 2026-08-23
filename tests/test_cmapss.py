"""
tests/test_cmapss.py
======================

Tests for POST /predict/cmapss.

Uses a REAL C-MAPSS sample -- 30 real engine cycles (see conftest.py's
real_cmapss_payload fixture, generated from the actual engineered feature
dataframe). If that hasn't been generated yet, these tests are SKIPPED
with a clear message rather than substituting made-up feature values.
"""

import math


def test_valid_real_sample_returns_finite_rul(client, real_cmapss_payload):
    response = client.post("/predict/cmapss", json=real_cmapss_payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert "predicted_rul" in body

    rul = body["predicted_rul"]
    assert isinstance(rul, (int, float)), f"predicted_rul should be numeric, got {rul!r}"
    assert math.isfinite(rul), f"predicted_rul should be finite, got {rul!r}"

    # NOTE: predicted_rul is NOT guaranteed to be >= 0 -- there is no
    # clipping in api/inference_cmapss.py's postprocessing, so a negative
    # value (an out-of-distribution / past-end-of-life signal) is a
    # technically valid output. We only assert finiteness here, not a
    # non-negative bound -- asserting >= 0 would be testing a contract
    # the current implementation doesn't actually guarantee.


def test_invalid_sequence_length_returns_422(client, real_cmapss_payload):
    # Drop one timestep -- the API requires exactly 30.
    malformed_payload = {"sequence": real_cmapss_payload["sequence"][:-1]}

    response = client.post("/predict/cmapss", json=malformed_payload)

    assert response.status_code == 422, (
        f"Expected 422 for a 29-timestep sequence, got "
        f"{response.status_code}: {response.text}"
    )


def test_missing_feature_in_timestep_returns_422(client, real_cmapss_payload):
    # Take one real timestep and remove one of its 225 required feature keys.
    malformed_row = dict(real_cmapss_payload["sequence"][0])
    malformed_row.pop("sensor_2")

    malformed_payload = {
        "sequence": [malformed_row] + real_cmapss_payload["sequence"][1:]
    }

    response = client.post("/predict/cmapss", json=malformed_payload)

    assert response.status_code == 422, (
        f"Expected 422 for a timestep missing a required feature, got "
        f"{response.status_code}: {response.text}"
    )


def test_malformed_sequence_type_returns_422(client):
    # sequence should be a list of feature dicts, not a flat list of numbers.
    malformed_payload = {"sequence": [1, 2, 3]}

    response = client.post("/predict/cmapss", json=malformed_payload)

    assert response.status_code == 422, (
        f"Expected 422 for a malformed sequence type, got "
        f"{response.status_code}: {response.text}"
    )
