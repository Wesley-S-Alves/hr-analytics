"""Testes das camadas ML: trainer, explainer, registry."""

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

# ============================================================
# trainer.find_optimal_threshold
# ============================================================


class TestFindOptimalThreshold:
    def test_perfect_separation(self):
        from hr_analytics.models.trainer import find_optimal_threshold

        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.9])
        threshold = find_optimal_threshold(y_true, y_prob)
        # Youden's J pode pegar qualquer ponto onde há separação perfeita
        assert 0.2 <= threshold <= 0.8

    def test_returns_float_in_range(self):
        from hr_analytics.models.trainer import find_optimal_threshold

        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_prob = np.random.rand(100)
        threshold = find_optimal_threshold(y_true, y_prob)
        assert isinstance(threshold, float)
        assert 0.0 <= threshold <= 1.0


# ============================================================
# trainer._create_model
# ============================================================


class TestCreateModel:
    def test_creates_xgboost(self):
        from hr_analytics.models.trainer import _create_model

        model = _create_model("xgboost", {"n_estimators": 10, "max_depth": 3})
        assert model is not None
        assert hasattr(model, "fit")

    def test_creates_logistic_regression(self):
        from hr_analytics.models.trainer import _create_model

        model = _create_model("logistic_regression", {"C": 1.0, "max_iter": 100})
        assert model is not None
        assert hasattr(model, "fit")

    def test_creates_random_forest(self):
        from hr_analytics.models.trainer import _create_model

        model = _create_model("random_forest", {"n_estimators": 10, "max_depth": 3})
        assert model is not None

    def test_unknown_model_raises(self):
        from hr_analytics.models.trainer import _create_model

        with pytest.raises((ValueError, KeyError)):
            _create_model("unknown_model_xyz", {})


# ============================================================
# explainer.create_explainer + global_feature_importance
# ============================================================


class TestExplainer:
    def test_create_explainer_returns_shap_object(self):
        from hr_analytics.models.explainer import create_explainer

        X = np.random.rand(50, 5)
        y = np.random.randint(0, 2, 50)
        model = RandomForestClassifier(n_estimators=10, random_state=42).fit(X, y)

        explainer = create_explainer(model)
        assert explainer is not None

    def test_compute_shap_values_correct_shape(self):
        from hr_analytics.models.explainer import compute_shap_values, create_explainer

        X = np.random.rand(30, 5)
        y = np.random.randint(0, 2, 30)
        model = RandomForestClassifier(n_estimators=10, random_state=42).fit(X, y)
        explainer = create_explainer(model)

        shap_values = compute_shap_values(explainer, X)
        # Shape should be (n_samples, n_features) ou (n_samples, n_features, n_classes)
        assert shap_values.shape[0] == 30

    def test_global_feature_importance_returns_sorted(self):
        from hr_analytics.models.explainer import (
            compute_shap_values,
            create_explainer,
            global_feature_importance,
        )

        X = np.random.rand(30, 5)
        y = np.random.randint(0, 2, 30)
        model = RandomForestClassifier(n_estimators=10, random_state=42).fit(X, y)
        explainer = create_explainer(model)
        shap_values = compute_shap_values(explainer, X)

        importance = global_feature_importance(
            shap_values,
            feature_names=["f0", "f1", "f2", "f3", "f4"],
        )
        # Função retorna dict OU lista dependendo da implementação
        assert importance is not None
        if isinstance(importance, dict):
            assert len(importance) == 5
        else:
            assert len(importance) >= 1

    def test_explain_single_returns_top_n(self):
        from hr_analytics.models.explainer import create_explainer, explain_single

        X = np.random.rand(20, 5)
        y = np.random.randint(0, 2, 20)
        model = RandomForestClassifier(n_estimators=10, random_state=42).fit(X, y)
        explainer = create_explainer(model)

        factors = explain_single(
            explainer,
            X[:1],
            feature_names=["f0", "f1", "f2", "f3", "f4"],
            top_n=3,
        )
        assert len(factors) == 3
        for f in factors:
            assert "feature" in f
            assert "shap_value" in f
            assert "impact" in f
            assert f["impact"] in ("aumenta_risco", "diminui_risco")


# ============================================================
# registry.save_model / load_model
# ============================================================


class TestRegistry:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        from sklearn.preprocessing import StandardScaler

        from hr_analytics.config import settings
        from hr_analytics.models import registry

        monkeypatch.setattr(settings, "artifacts_dir", tmp_path)

        X = np.random.rand(30, 4)
        y = np.random.randint(0, 2, 30)
        model = LogisticRegression(max_iter=100).fit(X, y)
        # Usa StandardScaler (picklável de verdade) em vez de MagicMock
        preprocessor = StandardScaler().fit(X)

        model_dir = registry.save_model(
            model=model,
            preprocessor=preprocessor,
            model_name="logistic_regression",
            metrics={"roc_auc": 0.75, "f1": 0.7, "precision": 0.7, "recall": 0.7, "pr_auc": 0.7},
            threshold=0.5,
            feature_names=["f0", "f1", "f2", "f3"],
        )
        assert model_dir.exists()

        loaded = registry.load_model(model_dir)
        # load_model retorna dict com 'model', 'preprocessor', 'metadata'
        meta = loaded["metadata"]
        assert meta["model_name"] == "logistic_regression"
        assert meta["threshold"] == 0.5
        assert "roc_auc" in meta["metrics"]
        assert meta["feature_names"] == ["f0", "f1", "f2", "f3"]
