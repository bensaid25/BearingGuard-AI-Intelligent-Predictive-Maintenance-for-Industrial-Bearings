"""
Fonctions d'évaluation communes pour tous les notebooks de modèles
(01_logistic_regression, 02_svm, 03_random_forest, 04_xgboost, 05_model_comparison).

Garantit que tous les modèles sont évalués avec exactement les mêmes métriques,
calculées de la même façon, pour une comparaison équitable.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)


def evaluate_model(model, X, y_true, model_name="model", average="macro"):
    """Calcule un dictionnaire de métriques standard pour un modèle donné.

    Parameters
    ----------
    model : estimateur scikit-learn déjà entraîné (avec .predict)
    X : features (déjà preprocessées / scalées si nécessaire)
    y_true : labels réels
    model_name : nom du modèle, utilisé dans le résultat
    average : stratégie d'agrégation pour precision/recall/f1 multi-classes

    Returns
    -------
    dict avec les métriques + les prédictions (utile pour l'analyse d'erreurs)
    """
    y_pred = model.predict(X)

    results = {
        "model_name": model_name,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average=average, zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average=average, zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average=average, zero_division=0),
        "y_pred": y_pred,
        "y_true": np.array(y_true),
    }
    return results


def get_confusion_matrix(y_true, y_pred, labels=None):
    """Retourne la matrice de confusion sous forme de DataFrame labellisé."""
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    if labels is None:
        labels = sorted(pd.unique(np.concatenate([y_true, y_pred])))
    return pd.DataFrame(cm, index=labels, columns=labels)


def get_classification_report(y_true, y_pred, output_dict=True):
    """Retourne le classification_report scikit-learn (dict ou texte)."""
    return classification_report(y_true, y_pred, output_dict=output_dict, zero_division=0)


def summarize_results(results_list):
    """Assemble une liste de dicts (sortie de evaluate_model) en DataFrame comparatif.

    Exclut automatiquement les colonnes y_pred / y_true (trop volumineuses / non tabulaires).
    """
    rows = []
    for r in results_list:
        row = {k: v for k, v in r.items() if k not in ("y_pred", "y_true")}
        rows.append(row)
    df = pd.DataFrame(rows).set_index("model_name")
    return df.round(4)


def save_results_json(results, path):
    """Sauvegarde un dict de résultats (sans y_pred/y_true) en JSON."""
    import json
    clean = {k: v for k, v in results.items() if k not in ("y_pred", "y_true")}
    with open(path, "w") as f:
        json.dump(clean, f, indent=2)
