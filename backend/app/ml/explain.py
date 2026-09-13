"""Additive feature attributions (SHAP values) for serialized CareFlow pipelines.

- XGBoost: exact TreeSHAP computed natively by the booster (`pred_contribs=True`).
- Linear models: exact SHAP for a linear model with an independent-feature masker,
  phi_i = w_i * (x_i - E[x_i]) (this is what shap.LinearExplainer computes).
- Other tree ensembles (e.g. RandomForest): shap.TreeExplainer, or on memory-constrained hosts
  (CAREFLOW_ML_EXPLAINER=tree_path) tree-path attributions, which are additive but approximate SHAP.

Attributions are computed on the one-hot/scaled matrix and summed back to the original feature,
so "admission_source" gets one number rather than one per category.
Attributions describe the MODEL, not causal effects in patients.
"""
from collections import defaultdict

import numpy as np
import pandas as pd

_TREE_EXPLAINERS: dict[int, object] = {}


def output_feature_map(preprocessor) -> list[str]:
    """For each column produced by the ColumnTransformer, the original feature it came from."""
    mapping: list[str] = []
    for name, transformer, columns in preprocessor.transformers_:
        if name == "remainder" or transformer == "drop":
            continue
        if name == "cat":
            encoder = transformer
            for col, cats in zip(columns, encoder.categories_, strict=True):
                mapping.extend([col] * len(cats))
        else:
            mapping.extend(columns)
    return mapping


def explanation_method(pipeline, method: str = "shap") -> str:
    """The attribution actually used: tree_path applies only to non-XGBoost tree ensembles."""
    est = pipeline.named_steps["model"]
    if method == "tree_path" and hasattr(est, "estimators_") and not type(est).__name__.startswith("XGB"):
        return "tree_path"
    return "shap"


def _tree_path_contributions(est, Xt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Tree-path (Saabas) attributions for a random-forest classifier.

    Along each row's decision path, the change in positive-class probability at every split is credited to the
    split's feature, then averaged over trees. Additive like SHAP (base + sum equals the forest's probability) but
    it follows one feature ordering per path instead of averaging over all orderings, so values approximate SHAP.
    """
    contribs = np.zeros(Xt.shape, dtype=float)
    base = 0.0
    positive = list(est.classes_).index(1)
    for tree in est.estimators_:
        t = tree.tree_
        values = t.value[:, 0, :]
        prob = values[:, positive] / values.sum(axis=1)
        base += prob[0]
        paths = tree.decision_path(Xt.astype(np.float32))
        for i in range(Xt.shape[0]):
            nodes = paths.indices[paths.indptr[i]:paths.indptr[i + 1]]  # node ids increase from root to leaf
            np.add.at(contribs[i], t.feature[nodes[:-1]], prob[nodes[1:]] - prob[nodes[:-1]])
    n = len(est.estimators_)
    return contribs / n, np.full(Xt.shape[0], base / n)


def raw_contributions(pipeline, X: pd.DataFrame, background: np.ndarray | None = None, method: str = "shap"):
    """Return (contributions[n, n_transformed], base_values[n], space)."""
    pre = pipeline.named_steps["preprocess"]
    est = pipeline.named_steps["model"]
    Xt = np.asarray(pre.transform(X), dtype=float)
    kind = type(est).__name__
    if kind.startswith("XGB"):
        import xgboost as xgb

        contribs = est.get_booster().predict(xgb.DMatrix(Xt), pred_contribs=True)
        space = "log_odds" if kind == "XGBClassifier" else "prediction"
        return contribs[:, :-1], contribs[:, -1], space
    if hasattr(est, "coef_"):
        if background is None:
            raise ValueError("Linear explanations need a background sample")
        coef = np.asarray(est.coef_).ravel()
        mean = background.mean(axis=0)
        contribs = (Xt - mean) * coef
        intercept = float(np.ravel(est.intercept_)[0])
        base = np.full(len(Xt), intercept + float(mean @ coef))
        space = "log_odds" if hasattr(est, "predict_proba") else "prediction"
        return contribs, base, space
    if explanation_method(pipeline, method) == "tree_path":
        contribs, base = _tree_path_contributions(est, Xt)
        return contribs, base, "probability"
    explainer = _TREE_EXPLAINERS.get(id(est))
    if explainer is None:  # building a TreeExplainer parses every tree: do it once per loaded model
        import shap

        explainer = _TREE_EXPLAINERS.setdefault(id(est), shap.TreeExplainer(est))
    values = explainer.shap_values(Xt)
    expected = explainer.expected_value
    if isinstance(values, list):  # older shap: one array per class
        values, expected = values[1], expected[1]
    elif values.ndim == 3:  # (n, features, classes)
        values, expected = values[:, :, 1], np.ravel(expected)[1]
    space = "probability" if hasattr(est, "predict_proba") else "prediction"
    return values, np.full(len(Xt), float(np.ravel(expected)[0])), space


def grouped_contributions(pipeline, X: pd.DataFrame, background: np.ndarray | None = None, method: str = "shap"):
    """Per-row attributions summed back to original features: (DataFrame[n, features], base, space)."""
    contribs, base, space = raw_contributions(pipeline, X, background, method)
    mapping = output_feature_map(pipeline.named_steps["preprocess"])
    grouped: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(len(X)))
    for j, feature in enumerate(mapping):
        grouped[feature] = grouped[feature] + contribs[:, j]
    return pd.DataFrame(dict(grouped), index=X.index), base, space


def global_importance(pipeline, X: pd.DataFrame, background: np.ndarray | None = None) -> dict[str, float]:
    """Mean absolute attribution per original feature (descending)."""
    frame, _, _ = grouped_contributions(pipeline, X, background)
    imp = frame.abs().mean().sort_values(ascending=False)
    return {k: round(float(v), 5) for k, v in imp.items()}
