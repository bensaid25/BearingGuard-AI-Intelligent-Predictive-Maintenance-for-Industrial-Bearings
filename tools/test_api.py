"""
tools/test_api.py
==================

A simple script to test the running API with REAL data pulled from your
own project, instead of hand-typing huge JSON bodies into Swagger.

This file has TODO markers where YOU fill in how to load one real example
from your own CWRU/IMS/C-MAPSS data -- I don't have access to your data
files, so I can't write that part for you without guessing.

Run this AFTER starting the server in another terminal:
    uvicorn api.app:app --reload

Then, in a second terminal:
    pip install requests --break-system-packages   # if not already installed
    python tools/test_api.py
"""

import os
import sys

import requests

# Make sure the project root (the parent of this tools/ folder) is on
# sys.path, so "from api.schemas import ..." below can find the api
# package no matter which directory this script is run from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    print("\n--- GET /health ---")
    response = requests.get(f"{BASE_URL}/health")
    print(response.status_code, response.json())


def test_cwru():
    print("\n--- POST /predict/cwru ---")

    # TODO: replace these placeholder numbers with 12 real feature values
    # for one CWRU sample. If you already computed these features
    # somewhere in a notebook (e.g. a row of your feature dataframe),
    # copy those exact numbers in here.
    payload = {
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

    response = requests.post(f"{BASE_URL}/predict/cwru", json=payload)
    print(response.status_code, response.json())


def test_ims():
    print("\n--- POST /predict/ims ---")

    # TODO: replace this with code that loads a REAL IMS snapshot file
    # (one of your raw .txt/.csv IMS data files) and pulls out the raw
    # signal for each channel. Example if you're using pandas:
    #
    #   import pandas as pd
    #   df = pd.read_csv("data/ims/2nd_test/<some_file>", sep="\t", header=None)
    #   # df should have one column per channel, 20480 rows
    #   channels = [
    #       {"channel": f"channel_{i+1}", "signal": df[i].tolist()}
    #       for i in range(df.shape[1])
    #   ]
    #
    # For now, this sends random noise just to prove the endpoint runs --
    # the anomaly score won't be meaningful.
    import random
    channels = [
        {"channel": f"channel_{i+1}", "signal": [random.gauss(0, 1) for _ in range(20480)]}
        for i in range(4)  # 2nd_test and 3rd_test need 4 channels; 1st_test needs 8
    ]
    payload = {"run": "2nd_test", "channels": channels}

    response = requests.post(f"{BASE_URL}/predict/ims", json=payload)
    print(response.status_code, response.json())


def test_cmapss():
    print("\n--- POST /predict/cmapss ---")

    # TODO: replace this with code that loads 30 REAL consecutive rows of
    # your already-engineered C-MAPSS feature dataframe (the one with the
    # 225 columns) and converts them to a list of dicts. Example:
    #
    #   import pandas as pd
    #   df = pd.read_csv("data/cmapss/engineered_features.csv")
    #   unit_df = df[df["unit_number"] == 1].sort_values("time_in_cycles")
    #   last_30 = unit_df.tail(30)
    #   feature_cols = [c for c in FEATURE_ORDER_LIST]  # the 225 names
    #   sequence = last_30[feature_cols].to_dict(orient="records")
    #
    # For now, this sends the same dummy row 30 times just to prove the
    # endpoint runs -- the predicted RUL won't be meaningful.
    from api.schemas import CMAPSS_FEATURE_ORDER  # only for this placeholder
    dummy_row = {name: 0.5 for name in CMAPSS_FEATURE_ORDER}
    payload = {"sequence": [dummy_row] * 30}

    response = requests.post(f"{BASE_URL}/predict/cmapss", json=payload)
    print(response.status_code, response.json())


if __name__ == "__main__":
    test_health()
    test_cwru()
    test_ims()
    test_cmapss()
