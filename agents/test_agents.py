"""
tools/test_agents.py
======================

Tests the full agent pipeline (classifier agent -> predictor agent)
directly against your real production models and real local Ollama --
WITHOUT going through FastAPI. This lets you debug the agent layer in
isolation before we wire a /agent/analyze endpoint into api/app.py.

Prerequisites:
    1. Ollama installed and running (it runs as a background service
       once installed -- check with: ollama list)
    2. A tool-calling model pulled:  ollama pull llama3.1:8b
    3. pip install ollama

Run from the project root:
    python tools/test_agents.py
"""

import os
import sys

# Make the project root importable, regardless of where this is run from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.router import run_agent_pipeline
from api.model_loader import load_all_models


def main():
    print("Loading production models (this may take a few seconds)...")
    models = load_all_models()
    print("Models loaded.\n")

    # TODO: replace with a real CWRU feature row once you've confirmed
    # the pipeline runs end-to-end with this placeholder.
    cwru_payload = {
        "rms": 0.42,
        "kurtosis": 3.1,
        "skewness": 0.05,
        "peak_to_peak": 1.8,
        "std": 0.39,
        "dominant_freq": 118.5,
        "spectral_energy": 22.7,
        "spectral_centroid": 340.2,
        "energy_0_1000": 5.1,
        "energy_1000_2500": 3.4,
        "energy_2500_5000": 1.2,
        "load": 1,
    }

    print("--- Running agent pipeline on a CWRU-shaped payload ---")
    result = run_agent_pipeline(cwru_payload, models)
    print("Classified pipeline:", result.classification.pipeline)
    print("Classifier confidence:", result.classification.confidence)
    print("Classifier reasoning:", result.classification.reasoning)
    print("Predictor summary:", result.summary)
    print()
    print("Full result dict:", result.to_dict())


if __name__ == "__main__":
    main()
