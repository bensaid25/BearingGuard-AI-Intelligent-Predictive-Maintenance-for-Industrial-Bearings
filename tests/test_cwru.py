"""
tests/test_cwru.py
====================

Tests for POST /predict/cwru.

Uses the exact real CWRU sample already validated manually via Swagger/
Postman, where it produced predicted_class == "Ball". If a future change
to the scaler, the model, or the preprocessing ever changes that result
for this exact input, this test will catch it (that's the point of a
regression test).
"""

import math

REAL_CWRU_SAMPLE = {
    "rms": 0.1337138105163796,
    "kurtosis": -0.1007173256513138,
    "skewness": 0.0118660165725503,
    "peak_to_peak": 0.9344893013972057,
    "std": 0.1336768542272595,
    "dominant_freq": 13476.5625,
    "spectral_energy": 0.0089446315778231,
    "spectral_centroid": 10739.134218762923,
    "energy_0_1000": 0.00007277456347761555,
    "energy_1000_2500": 0.000300211021384,
    "energy_2500_5000": 0.0003055405350038,
    "load": 0,
}


def test_valid_real_sample_predicts_ball(client):
    response = client.post("/predict/cwru", json=REAL_CWRU_SAMPLE)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert "predicted_class" in body
    assert "probabilities" in body
    assert body["predicted_class"] == "Ball", (
        f"Regression check failed: this exact real sample previously predicted "
        f"'Ball', but now predicts {body['predicted_class']!r}. The model, "
        f"scaler, or preprocessing may have changed."
    )


def test_missing_required_feature_returns_422(client):
    incomplete_sample = REAL_CWRU_SAMPLE.copy()
    del incomplete_sample["rms"]  # drop one of the 12 required fields

    response = client.post("/predict/cwru", json=incomplete_sample)

    assert response.status_code == 422, (
        f"Expected 422 for a missing required field, got "
        f"{response.status_code}: {response.text}"
    )


def test_wrong_type_returns_422(client):
    bad_sample = REAL_CWRU_SAMPLE.copy()
    bad_sample["rms"] = "hello"  # should be a float, not a string

    response = client.post("/predict/cwru", json=bad_sample)

    assert response.status_code == 422, (
        f"Expected 422 for a wrong-type field, got "
        f"{response.status_code}: {response.text}"
    )


def test_probabilities_are_a_valid_distribution(client):
    response = client.post("/predict/cwru", json=REAL_CWRU_SAMPLE)
    body = response.json()

    probabilities = body.get("probabilities")
    assert probabilities is not None, (
        "probabilities was null -- the CWRU model wrapper may not expose predict_proba()"
    )

    expected_classes = {"Ball", "InnerRace", "Normal", "OuterRace"}
    assert set(probabilities.keys()) == expected_classes, (
        f"Expected probability keys {expected_classes}, got {set(probabilities.keys())}"
    )

    for class_name, prob in probabilities.items():
        assert isinstance(prob, (int, float)), (
            f"{class_name} probability is not numeric: {prob!r}"
        )
        assert math.isfinite(prob), f"{class_name} probability is not finite: {prob!r}"
        assert 0.0 <= prob <= 1.0, f"{class_name} probability out of [0,1]: {prob!r}"

    total = sum(probabilities.values())
    assert math.isclose(total, 1.0, abs_tol=1e-4), (
        f"Probabilities should sum to ~1.0, got {total}"
    )
