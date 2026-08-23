"""
tests/test_ims.py
===================

Tests for POST /predict/ims.

Uses a REAL IMS raw-signal sample (see conftest.py's real_ims_payload
fixture -- generated from an actual raw snapshot file). If that hasn't
been generated yet, these tests are SKIPPED with a clear message rather
than substituting made-up signal data.
"""


def test_valid_real_sample_returns_expected_fields(client, real_ims_payload):
    response = client.post("/predict/ims", json=real_ims_payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert "run" in body
    assert "results" in body
    assert len(body["results"]) == len(real_ims_payload["channels"]), (
        "Number of results should match number of channels submitted"
    )

    for result in body["results"]:
        assert "channel" in result
        assert "anomaly_score" in result
        assert "is_anomaly" in result
        assert "model_predict" in result

        assert isinstance(result["anomaly_score"], (int, float)), (
            f"anomaly_score should be numeric, got {result['anomaly_score']!r}"
        )
        assert result["anomaly_score"] == result["anomaly_score"], (  # NaN check (NaN != NaN)
            "anomaly_score is NaN"
        )
        assert isinstance(result["is_anomaly"], bool)
        assert result["model_predict"] in (1, -1), (
            f"model_predict should be 1 (inlier) or -1 (outlier), "
            f"got {result['model_predict']!r}"
        )
        # This is the API's own stated contract: is_anomaly must agree with model_predict.
        assert result["is_anomaly"] == (result["model_predict"] == -1), (
            "is_anomaly should be True exactly when model_predict == -1"
        )


def test_missing_required_field_returns_422(client, real_ims_payload):
    incomplete_payload = {"run": real_ims_payload["run"]}  # "channels" missing entirely

    response = client.post("/predict/ims", json=incomplete_payload)

    assert response.status_code == 422, (
        f"Expected 422 for a missing 'channels' field, got "
        f"{response.status_code}: {response.text}"
    )


def test_wrong_type_returns_422(client, real_ims_payload):
    bad_payload = {
        "run": real_ims_payload["run"],
        "channels": "this should be a list of channel objects, not a string",
    }

    response = client.post("/predict/ims", json=bad_payload)

    assert response.status_code == 422, (
        f"Expected 422 for a malformed 'channels' field, got "
        f"{response.status_code}: {response.text}"
    )


def test_wrong_signal_length_returns_422(client, real_ims_payload):
    # Take one real channel and truncate it -- the API requires exactly
    # 20,480 samples per channel.
    real_signal = real_ims_payload["channels"][0]["signal"]
    malformed_payload = {
        "run": real_ims_payload["run"],
        "channels": [{"channel": "channel_1", "signal": real_signal[:100]}],
    }

    response = client.post("/predict/ims", json=malformed_payload)

    assert response.status_code == 422, (
        f"Expected 422 for a wrong-length signal, got "
        f"{response.status_code}: {response.text}"
    )
