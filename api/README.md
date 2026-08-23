# Predictive Maintenance API

A FastAPI backend that exposes three trained predictive-maintenance models over HTTP: a bearing fault classifier (CWRU), a turbofan remaining-useful-life predictor (C-MAPSS), and a bearing anomaly detector (IMS).

## Status

Phase 1 complete: all three production models load once at startup, all three prediction endpoints are implemented and validated against real data, and an automated regression test suite passes end to end (13/13) against the real production models.

## Architecture

```
                       FastAPI
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
 /predict/cwru      /predict/ims      /predict/cmapss
        │                 │                 │
        ▼                 ▼                 ▼
    CWRU model         IMS model        C-MAPSS model
        │                 │                 │
        ▼                 ▼                 ▼
      Fault            Anomaly              RUL
```

Deliberately kept simple: no agentic/multi-agent orchestration layer, no ESP32/IoT ingestion, no dashboard. Each endpoint calls its own model directly. An agentic layer (classifier agent → predictor agent, via a local LLM) was prototyped separately (see `agents/`, unused/not wired in) and set aside to prioritize a solid, fully-tested core API given project time constraints.

## Project structure

```
Predictive Maintenance/
├── api/
│   ├── app.py               # FastAPI app: loads models at startup, exposes all endpoints
│   ├── schemas.py            # Pydantic request/response models -- the API's data contract
│   ├── model_loader.py       # Loads every production model + scaler exactly once
│   ├── inference_cwru.py     # CWRU scale + classify logic
│   ├── inference_ims.py      # IMS feature computation + anomaly scoring logic
│   └── inference_cmapss.py   # C-MAPSS scale + sequence + RUL prediction logic
├── models/production/        # Saved model + scaler artifacts (cwru/, cmapss/, ims/)
├── tests/                    # Automated pytest suite (see Testing below)
├── tools/
│   ├── inspect_models.py             # Introspects saved artifacts (shapes, feature names, classes)
│   ├── test_api.py                   # Manual smoke-test script (dummy data)
│   └── generate_real_test_payloads.py # Generates real request payloads from actual project data
├── notebooks/                # Model training / feature engineering notebooks (source of truth for all contracts below)
├── data/
├── results/
├── agents/                   # Prototype agentic layer -- NOT wired into the running API
├── requirements.txt
└── pytest.ini
```

## Endpoints

### `GET /health`

Reports whether each production model group loaded successfully at startup.

```json
{
  "status": "ok",
  "models_loaded": { "cwru": true, "cmapss": true, "ims": true }
}
```

### `POST /predict/cwru` — bearing fault classification

**Request**: 12 pre-computed vibration features (caller is responsible for feature extraction upstream — see `notebooks/` for the exact extraction method).

```json
{
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
  "load": 0
}
```

**Response**: predicted fault class (`Ball`, `InnerRace`, `Normal`, or `OuterRace`) plus per-class probabilities.

```json
{
  "predicted_class": "Ball",
  "probabilities": { "Ball": 0.9993, "InnerRace": 0.0001, "Normal": 0.0001, "OuterRace": 0.0005 }
}
```

Validated manually with real data: **99.93% confidence on "Ball"**, confirmed correct by the automated regression test.

### `POST /predict/ims` — bearing anomaly detection

**Request**: the raw 20,480-sample vibration signal for every channel of one run. Channel count depends on the run: `1st_test` = 8 channels, `2nd_test`/`3rd_test` = 4 channels. The API computes all 11 time/frequency-domain features itself (ported directly from the feature-engineering notebook — no re-implementation drift).

```json
{
  "run": "2nd_test",
  "channels": [
    { "channel": "channel_1", "signal": [/* 20,480 numbers */] },
    { "channel": "channel_2", "signal": [/* 20,480 numbers */] },
    { "channel": "channel_3", "signal": [/* 20,480 numbers */] },
    { "channel": "channel_4", "signal": [/* 20,480 numbers */] }
  ]
}
```

**Response**: per-channel anomaly score (higher = more anomalous) and flag.

```json
{
  "run": "2nd_test",
  "results": [
    { "channel": "channel_1", "anomaly_score": 0.1655, "is_anomaly": true, "model_predict": -1 }
  ]
}
```

Validated manually with real data (200 OK, well-formed results). One open item: real early-run and late-run snapshots both scored 100% anomalous for `2nd_test` — plausibly genuine model behavior given known data-quality caveats in that run (documented in the feature-engineering notebook), but not yet cross-checked against the notebook's own scoring for the identical file. Flagged as a follow-up, not a known bug.

### `POST /predict/cmapss` — remaining useful life (RUL)

**Request**: the last 30 engine cycles, each with the 225 named engineered features the model was trained on (raw sensors + rolling statistics + trend slopes — see `api/schemas.py`'s `CMAPSS_FEATURE_ORDER` for the exact list and order).

**Response**: predicted RUL in cycles.

```json
{ "predicted_rul": 114.71 }
```

Validated manually with a real 30-cycle sequence: **114.71 cycles predicted, "Healthy"** range — consistent with a non-degraded engine.

## Setup

```powershell
cd "C:\chadha Summer Internship\2nd\Predictive Maintenance"
pip install -r requirements.txt
```

## Running the API

```powershell
uvicorn api.app:app --reload
```

Interactive docs: **http://127.0.0.1:8000/docs**

## Testing

Automated suite: `pytest -v` from the project root.

- **Health + CWRU tests** run immediately — CWRU uses a hardcoded real sample with a known correct prediction (`"Ball"`), acting as a regression check against future model/scaler changes.
- **IMS + C-MAPSS tests** use real data pulled from the actual project files (raw IMS snapshots, engineered C-MAPSS feature rows) via `tools/generate_real_test_payloads.py`. Run that script once first:
  ```powershell
  python tools/generate_real_test_payloads.py
  ```
  If it hasn't been run, the dependent tests skip cleanly with a message rather than failing or using fabricated data.

Each endpoint is tested for: a valid real request returning `200` with the correct output shape, a missing required field returning `422`, a wrong-typed field returning `422`, and malformed dimensions (wrong sequence length / signal length) returning `422`.

**Current status: 13/13 passing** against the real production models (verified on the development machine — 2 harmless warnings noted below, no failures).

## Design notes

- **Models load once, at startup** (`api/model_loader.py`), not per-request. `GET /health` reports load status; if loading fails, the server still starts so the failure is visible via `/health` rather than the process crash-looping silently.
- **No `.fit()` or `.fit_transform()` anywhere in the API** — only `.transform()` on the already-fitted production scalers. No model is retrained or modified by this code.
- **Every feature order is derived from the saved artifacts, not guessed** — confirmed via `tools/inspect_models.py` (feature names, shapes, classes) and cross-checked against the training notebooks.
- **Known warnings** (both harmless, seen during real test runs): an sklearn `UserWarning` about feature names, because the API deliberately passes a plain reordered numpy array into `.transform()` rather than a DataFrame (the order is verified correct by name beforehand); and a `DeprecationWarning` originating inside Keras's own internals, unrelated to this codebase.

## Explicitly out of scope for this phase

- ESP32 / IoT data ingestion
- Dashboard / UI
- Retraining or modifying any model
- A unified `/predict` endpoint (the decision layer routing between models)
- The agentic/multi-agent orchestration layer (prototyped in `agents/`, deliberately not wired in — see Architecture above)
