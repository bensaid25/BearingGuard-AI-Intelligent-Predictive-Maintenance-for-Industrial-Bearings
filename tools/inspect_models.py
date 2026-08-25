import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\chadha Summer Internship\2nd\Predictive Maintenance")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import joblib
import numpy as np



MODELS_DIR = PROJECT_ROOT / "models" / "production"


def inspect_joblib(path: Path, label: str) -> None:
    print(f"\n--- {label} ---")
    print(f"Path: {path}")

    try:
        obj = joblib.load(path)
    except Exception as exc:
        print(f"ERROR: Could not load artifact: {exc}")
        return

    print(f"Type: {type(obj)}")

    if hasattr(obj, "n_features_in_"):
        print(f"n_features_in_: {obj.n_features_in_}")

    if hasattr(obj, "feature_names_in_"):
        print(f"feature_names_in_: {list(obj.feature_names_in_)}")

    if hasattr(obj, "classes_"):
        print(f"classes_: {list(obj.classes_)}")

    if hasattr(obj, "mean_"):
        print(f"mean_ shape: {np.shape(obj.mean_)}")

    if hasattr(obj, "scale_"):
        print(f"scale_ shape: {np.shape(obj.scale_)}")

    if hasattr(obj, "data_min_"):
        print(f"data_min_ shape: {np.shape(obj.data_min_)}")

    if hasattr(obj, "offset_"):
        print(f"offset_: {obj.offset_}")

    if hasattr(obj, "contamination"):
        print(f"contamination: {obj.contamination}")


def inspect_keras(path: Path, label: str) -> None:
    print(f"\n--- {label} ---")
    print(f"Path: {path}")

    try:
        from tensorflow import keras

        model = keras.models.load_model(path)

    except Exception as exc:
        print(f"ERROR: Could not load model: {exc}")
        return

    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")


def main() -> None:

    # ---------------------------
    # CWRU
    # ---------------------------
    inspect_joblib(
        MODELS_DIR / "cwru" / "cwru_fault_classifier.joblib",
        "CWRU classifier",
    )

    inspect_joblib(
        MODELS_DIR / "cwru" / "scaler.joblib",
        "CWRU scaler",
    )

    # ---------------------------
    # C-MAPSS
    # ---------------------------
    inspect_joblib(
        MODELS_DIR / "cmapss" / "scaler_fd001.joblib",
        "C-MAPSS scaler",
    )

    inspect_keras(
        MODELS_DIR / "cmapss" / "best.keras",
        "C-MAPSS model",
    )

    # ---------------------------
    # IMS
    # ---------------------------
    for run in ["1st_test", "2nd_test", "3rd_test"]:

        inspect_joblib(
            MODELS_DIR / "ims" / f"{run}_isolation_forest.joblib",
            f"IMS {run} Isolation Forest",
        )

        inspect_joblib(
            MODELS_DIR / "ims" / f"{run}_scaler.joblib",
            f"IMS {run} scaler",
        )


if __name__ == "__main__":
    main()