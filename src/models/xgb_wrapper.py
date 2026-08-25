"""
Wrapper permettant à XGBClassifier de fonctionner avec des labels string
(comme tous les autres modèles du projet : LogisticRegression, SVM, RandomForest),
au lieu des labels entiers 0..n_classes-1 qu'il attend nativement.

Pourquoi un module séparé (plutôt qu'une classe définie dans le notebook) ?
----------------------------------------------------------------------------
joblib/pickle sérialise une référence au chemin du module + nom de classe,
pas le code de la classe lui-même. Une classe définie dans une cellule de
notebook vit dans le module `__main__` : elle se recharge très mal (voire pas
du tout) une fois le modèle rechargé dans un AUTRE notebook (ex: depuis
04_xgboost.ipynb vers 05_model_comparison.ipynb). En la plaçant dans
src/models/xgb_wrapper.py (un vrai module importable via sys.path, déjà
utilisé pour src.evaluation.*), le modèle se recharge correctement partout,
tant que PROJECT_ROOT est sur sys.path — ce qui est déjà fait par convention
dans tous les notebooks (`sys.path.insert(0, str(SRC_ROOT))`).
"""

from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder


class XGBStringClassifier(BaseEstimator, ClassifierMixin):
    """Enveloppe un estimateur XGBoost (ou tout classifieur sklearn-compatible
    attendant des labels entiers) pour qu'il se comporte, de l'extérieur,
    exactement comme les autres modèles du projet : fit/predict avec des
    labels string natifs ("Ball", "InnerRace", "Normal", "OuterRace"...).

    Compatible avec GridSearchCV : les hyperparamètres de l'estimateur interne
    se règlent via le préfixe standard sklearn "estimator__", par ex.
    `param_grid = {"estimator__n_estimators": [200, 400], ...}`.

    Compatible avec permutation_importance, evaluate_model, summarize_results,
    plot_feature_importance, etc. car il expose fit/predict/predict_proba/
    classes_/feature_importances_ comme un classifieur sklearn standard.
    """

    def __init__(self, estimator=None):
        self.estimator = estimator

    def fit(self, X, y):
        self.label_encoder_ = LabelEncoder()
        y_enc = self.label_encoder_.fit_transform(y)
        self.estimator.fit(X, y_enc)

        self.classes_ = self.label_encoder_.classes_
        # Ré-exposée à plat pour rester compatible avec plot_feature_importance,
        # qui attend un simple array-like sur `model.feature_importances_`.
        self.feature_importances_ = getattr(self.estimator, "feature_importances_", None)
        return self

    def predict(self, X):
        preds_enc = self.estimator.predict(X)
        return self.label_encoder_.inverse_transform(preds_enc)

    def predict_proba(self, X):
        return self.estimator.predict_proba(X)
