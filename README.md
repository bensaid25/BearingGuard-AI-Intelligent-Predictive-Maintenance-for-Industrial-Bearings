# Predictive Maintenance 🤖🔧

A predictive maintenance project covering three independent industrial ML problems — bearing fault classification, bearing anomaly detection, and turbofan remaining-useful-life prediction — served through a single FastAPI backend.

Project root: `Predictive Maintenance/`

## ⚙️ Overview

The project has three self-contained model pipelines, each trained on a different public dataset, plus a thin API layer that serves all three:

| Model | Dataset | Task | Output |
|---|---|---|---|
| **CWRU** | Case Western Reserve bearing dataset | Fault classification | `Ball`, `InnerRace`, `Normal`, `OuterRace` + confidence |
| **C-MAPSS** | NASA turbofan degradation dataset | Remaining useful life (RUL) regression | Predicted cycles remaining |
| **IMS** | IMS bearing run-to-failure dataset | Unsupervised anomaly detection | Anomaly score + normal/anomaly flag |

The API layer is intentionally minimal: it loads the already-trained production models and exposes them over HTTP. It does **not** retrain or modify any model, and does not include the ESP32/IoT ingestion hardware or a dashboard — those are explicitly out of scope for this phase.

## Status

- All three model pipelines have production artifacts saved under `models/production/` and are loaded and serving successfully.
- The FastAPI backend (`/health` + three `/predict/*` endpoints) is built and verified end-to-end against real data via Postman:
  - **CWRU** → predicted class `Ball` at 99.93% confidence
  - **C-MAPSS** → predicted RUL of 114.71 cycles ("Healthy")
  - **IMS** → all 4 channels flagged anomalous on a real `2nd_test` signal (cross-check against the original notebook's own scoring still pending)
- Automated pytest suite: **13 passed, 0 failed** against the real app and real models (no mocking).
- An optional agentic layer (LLM-based classifier agent → predictor agent, via local Ollama) was prototyped but is **not wired into the running service** — the project deliberately stayed a plain FastAPI service for simplicity given time constraints.

## Project structure

```
models/
  production/
    cwru/    cwru_fault_classifier.joblib, scaler.joblib
    cmapss/  best.keras, scaler_fd001.joblib
    ims/     per-run IsolationForest + scaler (1st_test, 2nd_test, 3rd_test)
api/
  app.py                 # FastAPI app, lifespan model loading, route registration
  schemas.py              # Pydantic request/response models per endpoint
  model_loader.py         # Loads production models into memory on startup
  inference_cwru.py       # CWRU prediction logic
  inference_ims.py        # IMS feature extraction + anomaly scoring
  inference_cmapss.py     # C-MAPSS sequence scaling + RUL prediction
tools/
  inspect_models.py                  # Inspect saved model artifacts
  test_api.py                         # Manual smoke-test script
  generate_real_test_payloads.py      # Builds real sample payloads for pytest fixtures
  sample_payloads/                    # Generated real payloads used by tests
tests/
  test_health.py, test_cwru.py, test_ims.py, test_cmapss.py
agents/                    # Prototype only, NOT wired into api/app.py (see below)
  llm_client.py, classifier_agent.py, predictor_agent.py, router.py
```

## Models

### CWRU — Bearing Fault Classification
A custom XGBoost wrapper (`src.models.xgb_wrapper.XGBStringClassifier`) classifying bearing condition from 12 pre-computed vibration features (`rms, kurtosis, skewness, peak_to_peak, std, dominant_freq, spectral_energy, spectral_centroid, energy_0_1000, energy_1000_2500, energy_2500_5000, load`), standardized with a saved `StandardScaler`.

### C-MAPSS — Remaining Useful Life
An LSTM (`best.keras`, named `baseline_lstm`) predicting RUL from a 30-cycle sequence of 225 engineered features per cycle. Features are built from 15 raw sensors: rolling mean/std/min/max over 5/10/20-cycle windows (grouped per engine unit), plus 10- and 20-cycle OLS trend slopes for every sensor — scaled with a saved `MinMaxScaler`.

### IMS — Unsupervised Anomaly Detection
A separate IsolationForest + StandardScaler pair per experimental run (`1st_test`, `2nd_test`, `3rd_test`), scoring 11 features per channel (8 time-domain + 3 frequency-domain) computed from raw 20,480-sample vibration snapshots. Anomaly score is `-model.decision_function(...)` (higher = more anomalous); the anomaly flag is the IsolationForest's own `predict()` output, with no additional threshold applied.

## API

### `GET /health`
Reports load status for all three production models.

### `POST /predict/cwru`
Takes the 12 pre-computed CWRU features directly — no raw-signal extraction happens in the API. Returns predicted class + probabilities.

### `POST /predict/ims`
Takes the **raw vibration signal per channel**; the API computes all 11 features itself (sampling rate 20,000 Hz, max frequency 2,000 Hz, linear detrend before FFT). One request covers all channels for a run at once — 8 channels for `1st_test`, 4 for `2nd_test`/`3rd_test`.

### `POST /predict/cmapss`
Takes already-engineered 225-feature rows for the last 30 cycles; the API only scales and stacks them into the (30, 225) sequence — no raw feature engineering happens in the API.

## Running locally

```bash
uvicorn api.app:app --reload
```

## Testing

```bash
pytest
```

Runs against the real FastAPI app with real production models loaded via the app's lifespan (no mocking). CWRU tests use a hardcoded real sample as a regression check. IMS and C-MAPSS tests load real payloads from `tools/sample_payloads/` (generate them first with `tools/generate_real_test_payloads.py` if missing — fixtures skip cleanly with a clear message otherwise).

## Optional / unused: agentic layer

`agents/` contains a standalone prototype of a two-agent pipeline (a classifier agent that decides which model to route to, then a predictor agent that runs it and summarizes the result) built around a local Ollama model (`llama3.1:8b`). It was built per an early direction from the supervisor but was ultimately **not integrated** into `api/app.py` — the project settled on a plain FastAPI service instead. The code is left in place as optional groundwork, not a required part of the running system.

## Out of scope

- ESP32 / IoT sensor ingestion hardware and firmware
- Dashboard / frontend
- Model retraining or modification

## Open items

- `tools/test_api.py` still needs a real (non-dummy) C-MAPSS input wired in for its sanity check to be meaningful (the endpoint itself returns 200 and works).
- IMS anomaly results on the `2nd_test` run haven't yet been cross-checked against the original notebook's own scoring.
