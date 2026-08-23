"""
tools/generate_real_test_payloads.py
======================================

Generates REAL (not random/dummy) request payloads for /predict/ims and
/predict/cmapss, pulled directly from your own project data:

  - IMS: two real raw snapshot files for one run -- the EARLIEST one
    (presumably healthy) and the LATEST one (presumably closer to
    failure) -- so you can compare how the anomaly score differs.

  - C-MAPSS: the last 30 cycles of one real engine unit from
    test_engineered.csv, plus that engine's true RUL at that point (if
    present in the file), so you can compare the prediction against
    ground truth.

Paths below match exactly what your own notebooks use
(02_feature_engineering.ipynb and 02_IMS_Feature_Engineering.ipynb) --
nothing here is guessed.

Run from the project root:
    python tools/generate_real_test_payloads.py
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.schemas import CMAPSS_FEATURE_ORDER, CMAPSS_SEQUENCE_LENGTH

OUTPUT_DIR = PROJECT_ROOT / "tools" / "sample_payloads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# C-MAPSS
# ---------------------------------------------------------------------------
CMAPSS_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "cmapss"
CMAPSS_TEST_PATH = CMAPSS_DATA_DIR / "test_engineered.csv"


def generate_cmapss_payload(unit_number: int = None) -> dict:
    if not CMAPSS_TEST_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {CMAPSS_TEST_PATH}. Run 02_feature_engineering.ipynb first, "
            f"or edit CMAPSS_TEST_PATH in this script if your file lives elsewhere."
        )

    df = pd.read_csv(CMAPSS_TEST_PATH)

    if unit_number is None:
        unit_number = df["unit_number"].iloc[0]  # just take the first engine present

    unit_df = df[df["unit_number"] == unit_number].sort_values("time_in_cycles")
    if len(unit_df) < CMAPSS_SEQUENCE_LENGTH:
        raise ValueError(
            f"Engine unit {unit_number} only has {len(unit_df)} cycles, "
            f"need at least {CMAPSS_SEQUENCE_LENGTH}. Try a different unit_number."
        )

    last_30 = unit_df.tail(CMAPSS_SEQUENCE_LENGTH)

    missing_cols = set(CMAPSS_FEATURE_ORDER) - set(last_30.columns)
    if missing_cols:
        raise ValueError(f"test_engineered.csv is missing expected columns: {sorted(missing_cols)}")

    sequence = last_30[CMAPSS_FEATURE_ORDER].to_dict(orient="records")

    true_rul = None
    if "RUL" in last_30.columns:
        true_rul = float(last_30["RUL"].iloc[-1])  # RUL at the final (most recent) cycle in the window

    print(f"C-MAPSS: using engine unit {unit_number}, cycles "
          f"{int(last_30['time_in_cycles'].iloc[0])}-{int(last_30['time_in_cycles'].iloc[-1])}"
          f"{f', true RUL at final cycle = {true_rul}' if true_rul is not None else ''}")

    return {"sequence": sequence}, true_rul


# ---------------------------------------------------------------------------
# IMS
# ---------------------------------------------------------------------------
IMS_ROOT = PROJECT_ROOT / "data" / "raw" / "ims"
IMS_MANIFEST_PATH = PROJECT_ROOT / "data" / "processed" / "ims" / "ims_documented_file_manifest.csv"


def load_snapshot_file(file_path: Path) -> pd.DataFrame:
    """Matches load_snapshot_file() in 02_IMS_Feature_Engineering.ipynb exactly."""
    df = pd.read_csv(file_path, sep="\t", header=None)
    df.columns = [f"channel_{i + 1}" for i in range(df.shape[1])]
    return df


def generate_ims_payload(run: str, which: str) -> dict:
    """which: "earliest" or "latest" -- picks the first or last documented
    snapshot file for the given run, by timestamp."""
    if not IMS_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {IMS_MANIFEST_PATH}. Run 01_IMS_Data_Understanding.ipynb first, "
            f"or edit IMS_MANIFEST_PATH in this script if your manifest lives elsewhere."
        )

    manifest = pd.read_csv(IMS_MANIFEST_PATH, parse_dates=["timestamp"])
    run_rows = manifest.loc[manifest["test_set"] == run].sort_values("timestamp")
    if run_rows.empty:
        raise ValueError(f"No manifest rows found for run={run!r}")

    row = run_rows.iloc[0] if which == "earliest" else run_rows.iloc[-1]
    file_path = IMS_ROOT / row["relative_path"]
    if not file_path.exists():
        raise FileNotFoundError(f"Manifest points to a missing file: {file_path}")

    signal_df = load_snapshot_file(file_path)
    channels = [
        {"channel": col, "signal": signal_df[col].tolist()}
        for col in signal_df.columns
    ]

    print(f"IMS ({run}, {which}): using file {file_path.name} (timestamp {row['timestamp']})")

    return {"run": run, "channels": channels}


if __name__ == "__main__":
    # ---- C-MAPSS ----
    try:
        cmapss_payload, true_rul = generate_cmapss_payload()
        cmapss_path = OUTPUT_DIR / "cmapss_payload_real.json"
        with open(cmapss_path, "w") as f:
            json.dump(cmapss_payload, f)
        print(f"Wrote {cmapss_path}")
        if true_rul is not None:
            print(f"  -> Compare the API's predicted_rul against the true RUL above ({true_rul}).")
    except Exception as exc:
        print(f"C-MAPSS payload generation FAILED: {exc}")

    print()

    # ---- IMS ----
    for run in ("2nd_test",):
        for which in ("earliest", "latest"):
            try:
                ims_payload = generate_ims_payload(run, which)
                ims_path = OUTPUT_DIR / f"ims_payload_real_{run}_{which}.json"
                with open(ims_path, "w") as f:
                    json.dump(ims_payload, f)
                print(f"Wrote {ims_path}")
            except Exception as exc:
                print(f"IMS ({run}, {which}) payload generation FAILED: {exc}")

    print("\nOpen each file, copy the contents, paste into Postman's raw JSON body.")
    print("Tip: compare the 'earliest' vs 'latest' IMS anomaly scores for the same run --")
    print("if the pipeline is working, 'latest' should generally score more anomalous.")
