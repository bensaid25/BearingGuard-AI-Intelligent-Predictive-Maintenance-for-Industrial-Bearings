# Predictive Maintenance Dashboard (frontend)

Streamlit presentation layer for *Intelligent Bearing Fault Detection and Remaining Health Assessment*.
It only displays data. It never loads, retrains or duplicates a model, and it never contains inference logic.

## Run

From the project root:

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

The dashboard starts in **DEMO MODE — MOCK DATA**. No backend is needed.

The look follows a dark "digital twin" HUD: navy glass panels, cyan glow, semicircle and ring gauges. The fonts (Orbitron, Rajdhani) load from Google Fonts, so the first load needs internet; without it the browser falls back to a system font.

## Files

| File | Role |
|---|---|
| `app.py` | The page: sidebar, status, sensor cards, AI results, charts, system table |
| `mock_data.py` | Simulated data (three scenarios: healthy / degrading / faulty) |
| `api_client.py` | HTTP client for FastAPI, real sample payloads, and response-shape transforms |
| `utils.py` | `get_dashboard_data()`, status rule, formatting |
| `theme.py` | Dark HUD look: CSS, SVG gauges, chart styling (drawing only, no data logic) |
| `sample_payloads/` | Real, validated sample request bodies for the CWRU/C-MAPSS/IMS models |

`app.py` only calls `utils.get_dashboard_data(...)`. Both data sources return the same dictionary, so the UI does not change when you switch.

## Connecting the real backend — status: done

Both the **AI model panels** and the **live sensor panel** are wired to real data. Select **FastAPI backend** in the sidebar (default URL `http://localhost:8000`, or set `FASTAPI_BASE_URL`) once the Docker container is running.

### AI model panels (CWRU, IMS, C-MAPSS)

Each panel sends a **fixed, real, previously-validated sample** to its `/predict/*` endpoint — not live sensor data (see "What is and isn't connected," below, for why). The samples live in `sample_payloads/`:

| Model | Sample source | Notes |
|---|---|---|
| CWRU | `api_client.py`'s `CWRU_REAL_SAMPLE` (from `tests/test_cwru.py`) | Regression-tested; expected result is `"Ball"` |
| C-MAPSS | `sample_payloads/cmapss_payload_real.json` | 30 real engine cycles, 225 features each |
| IMS | `sample_payloads/ims_payload_real_2nd_test_latest.json` | 4 channels, 20,480 samples each, run `2nd_test` |

Because the real endpoint responses aren't flat dictionaries, `api_client.py` uses small **response transform functions** instead of a simple field-name lookup:

- **CWRU** returns a `probabilities` dict keyed by class name, not a single confidence number — the transform reads out the probability of the *predicted* class specifically.
- **IMS** returns a `results` array (one entry per channel, since the model scores 4 channels independently), not one score — the transform reports the **most anomalous channel** (highest `anomaly_score`), since that's the one that should drive a machine-status display.
- **C-MAPSS** is already flat (`predicted_rul`) — a direct rename.

If a sample payload is ever missing, that panel shows an honest "not connected" state with the reason — it never falls back to invented numbers.

### Live sensor panel (ESP32 + MPU6050)

This panel shows the backend's cached most-recent reading from the physical rig, via a dedicated `GET /sensor-data/latest` endpoint added to `api/app.py`. Every time the ESP32 POSTs a vibration window to `/sensor-data`, the backend also updates a small in-memory cache (mean ax/ay/az from the already-computed feature summary, plus a combined vibration magnitude and up to 200 points of history) — purely for display, with no effect on the existing `/sensor-data` response contract.

The combined vibration magnitude uses each axis's **standard deviation**, not raw RMS. Raw RMS on the z-axis is dominated by the ~9.8 m/s² gravity offset, which would drown out the much smaller vibration signal; standard deviation measures fluctuation around each axis's own mean instead, so gravity's constant offset drops out. This is the same approach already used to validate the sensor (comparing motor running vs. stopped), reused here rather than inventing a separate metric for the dashboard.

If no `/sensor-data` POST has been received yet (rig not running, or ESP32 not connected), the panel says so plainly rather than showing stale or fabricated values.

## Things to keep honest

- **The live sensor panel and the three AI prediction panels are independent.** Switching to "FastAPI backend" does not change what the CWRU/IMS/C-MAPSS panels send — they always use the fixed real samples above, regardless of whether the motor is running. The sensor panel's live ax/ay/az/rms values are never fed into any `/predict/*` call.
- **Why the live rig's data isn't scored by the trained models:** the IMS model was calibrated on the NASA bearing rig's specific hardware (20 kHz sampling, 4–8 channels); CWRU's scaler and required `load` field are similarly specific to its own dataset's acquisition setup. Feeding this rig's ~50 Hz, 3-axis data through either would not error, but would produce a statistically meaningless result. Training a model calibrated to this exact rig is a defined next step, not an oversight (see `api/inference_sensor.py`'s module docstring).
- `/sensor-data` (ESP32 + MPU6050) itself is ingestion/diagnostic only — it returns computed features, never an anomaly verdict.
- The NORMAL / WARNING / CRITICAL badge is a display rule in `utils.py` (RUL under 60 or 30 cycles, CWRU fault above 70% confidence, IMS anomaly flag). Adjust the constants there.
- The mock IMS score assumes "higher = more anomalous". If your backend uses the opposite sign, set `IMS_HIGHER_IS_ANOMALOUS = False` in `utils.py`.
