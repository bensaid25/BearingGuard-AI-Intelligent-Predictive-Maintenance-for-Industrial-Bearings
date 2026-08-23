"""
tests/test_health.py
======================

Tests for GET /health.
"""


def test_health_returns_200_with_ok_status(client):
    response = client.get("/health")

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()

    assert "status" in body, "Response is missing the 'status' field"
    assert body["status"] == "ok", (
        f"Expected status 'ok' (all production models loaded), got "
        f"{body['status']!r}. models_loaded={body.get('models_loaded')}"
    )

    assert "models_loaded" in body, "Response is missing the 'models_loaded' field"
    for group in ("cwru", "cmapss", "ims"):
        assert body["models_loaded"].get(group) is True, (
            f"Model group '{group}' did not load -- check the server logs for details"
        )
