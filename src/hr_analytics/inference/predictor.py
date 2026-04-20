"""Serviço de predição singleton.

Carrega o modelo e preprocessor uma vez na inicialização da API
e reutiliza para todas as predições.
"""

import logging
from typing import Any

import pandas as pd

from hr_analytics.config import settings
from hr_analytics.data.feature_engineering import add_domain_features
from hr_analytics.data.preprocessing import prepare_features
from hr_analytics.models.explainer import create_explainer, explain_single
from hr_analytics.models.registry import load_model
from hr_analytics.monitoring.observability import MetricType, RequestMetrics, tracker

logger = logging.getLogger(__name__)


class ModelService:
    """Serviço singleton para predição e explicabilidade.

    Carrega modelo, preprocessor e SHAP explainer na inicialização.
    Fornece métodos para predição individual e em batch.
    """

    def __init__(self):
        self._model = None
        self._preprocessor = None
        self._metadata = None
        self._explainer = None
        self._feature_names = None
        self._loaded = False

    def load(self) -> None:
        """Carrega modelo e artefatos do disco."""
        try:
            artifacts = load_model()
            self._model = artifacts["model"]
            self._preprocessor = artifacts["preprocessor"]
            self._metadata = artifacts["metadata"]
            self._feature_names = artifacts["metadata"]["feature_names"]

            # Para SHAP: extrair modelo base compatível com TreeExplainer
            shap_model = self._extract_shap_model(self._model)
            self._explainer = create_explainer(shap_model)

            self._loaded = True
            logger.info("ModelService carregado: %s", self._metadata["model_name"])
        except FileNotFoundError as e:
            logger.warning("Modelo não encontrado: %s", e)
            self._loaded = False

    @staticmethod
    def _extract_shap_model(model: Any) -> Any:
        """Extrai um modelo compatível com SHAP TreeExplainer.

        CalibratedClassifierCV e EnsembleModel não são compatíveis diretamente.
        Esta função extrai o estimator base tree-based.
        """
        from sklearn.calibration import CalibratedClassifierCV

        # CalibratedClassifierCV → extrair o estimator base
        if isinstance(model, CalibratedClassifierCV):
            base = model.estimator
            if hasattr(base, "feature_importances_"):
                return base
            # Se calibrated tem calibrated_classifiers_, pegar o primeiro
            if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
                inner = model.calibrated_classifiers_[0].estimator
                if hasattr(inner, "feature_importances_"):
                    return inner

        # EnsembleModel → pegar o melhor base model tree-based
        from hr_analytics.models.trainer import EnsembleModel

        if isinstance(model, EnsembleModel):
            for name, base in model.base_models.items():
                extracted = ModelService._extract_shap_model(base)
                if hasattr(extracted, "feature_importances_"):
                    return extracted

        # Modelo direto (XGBoost, LightGBM, RF, etc.)
        if hasattr(model, "feature_importances_"):
            return model

        # Fallback: retornar o modelo original (pode falhar no SHAP)
        return model

    @property
    def is_loaded(self) -> bool:
        """Retorna True se o modelo está carregado."""
        return self._loaded

    @property
    def model_name(self) -> str | None:
        """Nome do modelo carregado."""
        return self._metadata["model_name"] if self._metadata else None

    @property
    def threshold(self) -> float:
        """Threshold ótimo de classificação."""
        if self._metadata:
            return self._metadata.get("threshold", 0.5)
        return 0.5

    def predict(self, df: pd.DataFrame) -> list[dict]:
        """Predição para um DataFrame de colaboradores.

        Args:
            df: DataFrame com dados dos colaboradores (colunas originais).

        Returns:
            Lista de dicionários com predições.
        """
        if not self._loaded:
            raise RuntimeError("Modelo não carregado. Execute load() primeiro.")

        metrics = RequestMetrics(metric_type=MetricType.INFERENCE, endpoint="/predict")

        # Adicionar features de domínio
        df_feat = add_domain_features(df)

        # Preparar e transformar
        X_raw = prepare_features(df_feat)
        X = self._preprocessor.transform(X_raw)

        # Predição
        probabilities = self._model.predict_proba(X)[:, 1]

        results = []
        for i, prob in enumerate(probabilities):
            risk_level = settings.get_risk_level(float(prob))
            results.append(
                {
                    "attrition_probability": round(float(prob), 4),
                    "risk_level": risk_level,
                    "threshold": self.threshold,
                }
            )

        metrics.items_processed = len(results)
        tracker.record(metrics)

        return results

    def predict_single(self, df_row: pd.DataFrame) -> dict:
        """Predição para um único colaborador com explicação SHAP.

        Args:
            df_row: DataFrame com uma única linha.

        Returns:
            Dicionário com predição e fatores explicativos.
        """
        if not self._loaded:
            raise RuntimeError("Modelo não carregado. Execute load() primeiro.")

        metrics = RequestMetrics(metric_type=MetricType.INFERENCE, endpoint="/predict/single")

        # Feature engineering e transformação
        df_feat = add_domain_features(df_row)
        X_raw = prepare_features(df_feat)
        X = self._preprocessor.transform(X_raw)

        # Predição
        prob = float(self._model.predict_proba(X)[:, 1][0])
        risk_level = settings.get_risk_level(prob)

        # Explicação SHAP
        factors = explain_single(
            self._explainer,
            X,
            self._feature_names,
            top_n=5,
        )

        tracker.record(metrics)

        return {
            "attrition_probability": round(prob, 4),
            "risk_level": risk_level,
            "threshold": self.threshold,
            "top_factors": factors,
        }


# Instância global
model_service = ModelService()
