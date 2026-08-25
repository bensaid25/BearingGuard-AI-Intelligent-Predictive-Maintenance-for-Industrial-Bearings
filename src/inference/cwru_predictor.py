"""
Wrapper pret a l'emploi pour charger et utiliser le modele CWRU final
(voir models/final/, produit par 05_model_comparison.ipynb).

Usage :
    from src.inference.cwru_predictor import CWRUFaultPredictor

    predictor = CWRUFaultPredictor(PROJECT_ROOT / "models" / "final")
    y_pred = predictor.predict(new_features_df)          # array de labels
    proba  = predictor.predict_proba(new_features_df)    # si le modele le supporte
"""

import json
from pathlib import Path

import joblib
import pandas as pd


class CWRUFaultPredictor:
    """Charge le modele + scaler + metadonnees en un seul objet reutilisable."""

    def __init__(self, model_dir):
        model_dir = Path(model_dir)

        metadata_path = model_dir / "model_metadata.json"
        assert metadata_path.exists(), f"Metadonnees introuvables : {metadata_path}"

        with open(metadata_path, encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.model = joblib.load(model_dir / self.metadata["model_file"])
        self.scaler = joblib.load(model_dir / self.metadata["scaler_file"])
        self.feature_cols = self.metadata["feature_cols"]
        self.classes_ = self.metadata["classes"]
        self.model_name = self.metadata["model_name"]

    def _prepare(self, X: pd.DataFrame):
        missing = [c for c in self.feature_cols if c not in X.columns]
        assert not missing, f"Colonnes manquantes dans X : {missing}"
        X_ordered = X[self.feature_cols]  # force le meme ordre qu'a l'entrainement
        return self.scaler.transform(X_ordered)

    def predict(self, X: pd.DataFrame):
        return self.model.predict(self._prepare(X))

    def predict_proba(self, X: pd.DataFrame):
        if not hasattr(self.model, "predict_proba"):
            raise AttributeError(f"{self.model_name} ne supporte pas predict_proba.")
        return self.model.predict_proba(self._prepare(X))

    def info(self):
        """Affiche un resume du modele charge (utile pour verifier rapidement)."""
        print(f"Modele        : {self.model_name}")
        print(f"Classes       : {self.classes_}")
        print(f"Nb features   : {len(self.feature_cols)}")
        print(f"Metriques test: {self.metadata['test_metrics']}")
        print(f"Entraine le   : {self.metadata['training_date']}")
