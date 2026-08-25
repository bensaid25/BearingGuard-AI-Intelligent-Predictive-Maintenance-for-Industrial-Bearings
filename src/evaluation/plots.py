"""
Fonctions de visualisation communes pour tous les notebooks de modèles.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np


def plot_confusion_matrix(cm_df, model_name="Model", normalize=False, ax=None):
    """Affiche une matrice de confusion sous forme de heatmap.

    Parameters
    ----------
    cm_df : DataFrame (sortie de get_confusion_matrix)
    normalize : si True, affiche les proportions par ligne plutôt que les comptes bruts
    """
    data = cm_df.copy()
    fmt = "d"
    if normalize:
        data = data.div(data.sum(axis=1), axis=0).round(2)
        fmt = ".2f"

    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 5))
        created_fig = True

    sns.heatmap(data, annot=True, fmt=fmt, cmap="Blues", cbar=True, ax=ax)
    ax.set_title(f"Matrice de confusion — {model_name}")
    ax.set_ylabel("Classe réelle")
    ax.set_xlabel("Classe prédite")

    if created_fig:
        plt.tight_layout()
        plt.show()


def plot_model_comparison(summary_df, metric="f1_macro"):
    """Barplot comparant plusieurs modèles sur une métrique donnée.

    Parameters
    ----------
    summary_df : DataFrame indexé par model_name (sortie de summarize_results)
    metric : nom de la colonne à afficher
    """
    fig, ax = plt.subplots(figsize=(7, 4))
    sorted_df = summary_df.sort_values(metric, ascending=False)
    sns.barplot(x=sorted_df.index, y=sorted_df[metric], ax=ax, palette="viridis")
    ax.set_title(f"Comparaison des modèles — {metric}")
    ax.set_ylabel(metric)
    ax.set_xlabel("Modèle")
    ax.set_ylim(0, 1)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.show()


def plot_class_distribution(y_series, title="Distribution des classes"):
    """Barplot de la distribution des classes pour un split donné."""
    fig, ax = plt.subplots(figsize=(6, 4))
    counts = y_series.value_counts()
    sns.barplot(x=counts.index, y=counts.values, ax=ax, palette="mako")
    ax.set_title(title)
    ax.set_ylabel("Nombre d'échantillons")
    ax.set_xlabel("Classe")
    plt.tight_layout()
    plt.show()


def plot_feature_importance(importances, feature_names, top_n=20, model_name="Model"):
    """Barplot horizontal des top_n features les plus importantes.

    Utile pour Random Forest / XGBoost (feature_importances_).
    """
    imp_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    }).sort_values("importance", ascending=False).head(top_n)

    fig, ax = plt.subplots(figsize=(7, max(4, top_n * 0.3)))
    sns.barplot(x="importance", y="feature", data=imp_df, ax=ax, palette="crest")
    ax.set_title(f"Top {top_n} features importantes — {model_name}")
    plt.tight_layout()
    plt.show()
