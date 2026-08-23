"""
tools/generate_test_payloads.py
=================================

Generates two JSON files with correctly-SHAPED request bodies for
/predict/ims and /predict/cmapss -- too large to hand-type into Postman,
so generate them here and copy-paste the file contents into Postman's
raw JSON body instead.

IMPORTANT: the values in these files are RANDOM placeholders, not real
sensor data. They prove the endpoint runs and returns a well-formed
response -- they do NOT prove the prediction is meaningful. Swap in real
values (see the TODOs) once you're ready for a genuine test.

Run from the project root:
    python tools/generate_test_payloads.py

Output:
    tools/sample_payloads/ims_payload.json
    tools/sample_payloads/cmapss_payload.json
"""

import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.schemas import CMAPSS_FEATURE_ORDER, CMAPSS_SEQUENCE_LENGTH

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tools", "sample_payloads")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_ims_payload(run: str = "2nd_test", num_channels: int = 4) -> dict:
    # TODO: replace this random signal with a real one read from one of
    # your IMS raw data files if you want a meaningful (not just
    # well-formed) test.
    channels = [
        {
            "channel": f"channel_{i + 1}",
            "signal": [random.gauss(0, 1) for _ in range(20480)],
        }
        for i in range(num_channels)
    ]
    return {"run": run, "channels": channels}


def generate_cmapss_payload() -> dict:
    # TODO: replace this dummy 0.5-for-everything row with 30 real rows
    # from your engineered C-MAPSS feature dataframe if you want a
    # meaningful (not just well-formed) test.
    dummy_row = {name: 0.5 for name in CMAPSS_FEATURE_ORDER}
    return {"sequence": [dummy_row] * CMAPSS_SEQUENCE_LENGTH}


if __name__ == "__main__":
    ims_path = os.path.join(OUTPUT_DIR, "ims_payload.json")
    with open(ims_path, "w") as f:
        json.dump(generate_ims_payload(), f)
    print(f"Wrote {ims_path}")

    cmapss_path = os.path.join(OUTPUT_DIR, "cmapss_payload.json")
    with open(cmapss_path, "w") as f:
        json.dump(generate_cmapss_payload(), f)
    print(f"Wrote {cmapss_path}")

    print("\nOpen each file, copy the whole contents, and paste into Postman's raw JSON body.")
