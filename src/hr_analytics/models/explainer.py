"""Explicabilidade do modelo via SHAP.

Gera explicações globais (feature importance, summary plot) e
individuais (top-N fatores de risco por colaborador).
"""

import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Backend não-interativo para salvar plots
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from hr_analytics.config import settings

logger = logging.getLogger(__name__)


def create_explainer(model: Any, X_background: np.ndarray | None = None) -> shap.Explainer:
    """Cria um SHAP explainer adequado ao tipo de modelo.

    Para modelos baseados em árvore (RF, XGBoost, LightGBM), usa TreeExplainer.
    Para outros (LogReg), usa o Explainer genérico com amostra de background.

    Args:
        model: Modelo treinado.
        X_background: Amostra de dados de treino para background (necessário para LogReg).

    Returns:
        SHAP Explainer configurado.
    """
    model_type = type(model).__name__

    if model_type in ("RandomForestClassifier", "XGBClassifier", "LGBMClassifier"):
        return shap.TreeExplainer(model)

    # Fallback: Explainer genérico com amostra de background
    if X_background is None:
        raise ValueError("X_background é necessário para modelos não baseados em árvore")

    # Usar uma amostra de 100 pontos para performance
    n_samples = min(100, len(X_background))
    background = shap.sample(X_background, n_samples, random_state=settings.random_seed)
    return shap.Explainer(model.predict_proba, background)


def compute_shap_values(
    explainer: shap.Explainer,
    X: np.ndarray,
) -> np.ndarray:
    """Calcula SHAP values para um conjunto de dados.

    Args:
        explainer: SHAP Explainer.
        X: Features transformadas.

    Returns:
        Array de SHAP values (classe positiva = attrition).
    """
    shap_values = explainer(X)

    # Para classificação binária, pegar valores da classe positiva (index 1)
    if isinstance(shap_values.values, list):
        return shap_values.values[1]
    elif len(shap_values.values.shape) == 3:
        return shap_values.values[:, :, 1]
    return shap_values.values


def global_feature_importance(
    shap_values: np.ndarray,
    feature_names: list[str],
    top_n: int = 20,
) -> pd.DataFrame:
    """Calcula feature importance global baseada em SHAP.

    Args:
        shap_values: Array de SHAP values.
        feature_names: Nomes das features.
        top_n: Número de features a retornar.

    Returns:
        DataFrame com features ordenadas por importância.
    """
    importance = np.abs(shap_values).mean(axis=0)

    df = pd.DataFrame(
        {
            "feature": feature_names[: len(importance)],
            "importance": importance,
        }
    )
    df = df.sort_values("importance", ascending=False).head(top_n).reset_index(drop=True)

    return df


def explain_single(
    explainer: shap.Explainer,
    X_single: np.ndarray,
    feature_names: list[str],
    top_n: int = 5,
) -> list[dict]:
    """Explica a predição para um único colaborador.

    Retorna os top-N fatores que mais influenciam o risco,
    com direção (aumenta/diminui) e magnitude.

    Args:
        explainer: SHAP Explainer.
        X_single: Features de um colaborador (1 linha).
        feature_names: Nomes das features.
        top_n: Número de fatores a retornar.

    Returns:
        Lista de dicionários com fatores explicativos.
    """
    if X_single.ndim == 1:
        X_single = X_single.reshape(1, -1)

    shap_values = compute_shap_values(explainer, X_single)[0]

    # Criar lista de fatores com SHAP value e direção
    factors = []
    for i, (name, sv) in enumerate(zip(feature_names, shap_values)):
        factors.append(
            {
                "feature": name,
                "shap_value": float(sv),
                "impact": "aumenta_risco" if sv > 0 else "diminui_risco",
                "magnitude": float(abs(sv)),
                "feature_value": float(X_single[0, i]) if i < X_single.shape[1] else None,
            }
        )

    # Ordenar por magnitude (maior impacto primeiro)
    factors.sort(key=lambda x: x["magnitude"], reverse=True)

    return factors[:top_n]


# =============================================================================
# PLOTS SHAP — salvos como imagem em artifacts/figures/
# =============================================================================


def save_shap_summary_plot(
    shap_values: np.ndarray,
    X: np.ndarray,
    feature_names: list[str],
    output_dir: Path | None = None,
) -> Path:
    """Gera e salva o SHAP summary plot (beeswarm).

    Args:
        shap_values: Array de SHAP values.
        X: Features transformadas.
        feature_names: Nomes das features.
        output_dir: Diretório de saída. Se None, usa artifacts/figures/.

    Returns:
        Caminho do arquivo salvo.
    """
    if output_dir is None:
        output_dir = settings.artifacts_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 8))
    shap.summary_plot(
        shap_values,
        X,
        feature_names=feature_names,
        show=False,
        max_display=20,
    )
    plt.title("SHAP Summary Plot — Top 20 Features", fontsize=14)
    plt.tight_layout()

    path = output_dir / "shap_summary.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("SHAP summary plot salvo: %s", path)
    return path


def save_shap_bar_plot(
    shap_values: np.ndarray,
    feature_names: list[str],
    output_dir: Path | None = None,
) -> Path:
    """Gera e salva o SHAP bar plot (feature importance global).

    Args:
        shap_values: Array de SHAP values.
        feature_names: Nomes das features.
        output_dir: Diretório de saída.

    Returns:
        Caminho do arquivo salvo.
    """
    if output_dir is None:
        output_dir = settings.artifacts_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    importance = np.abs(shap_values).mean(axis=0)
    indices = np.argsort(importance)[-20:]  # Top 20

    plt.figure(figsize=(10, 8))
    plt.barh(
        [feature_names[i] for i in indices],
        importance[indices],
        color="#3498db",
    )
    plt.xlabel("Importância SHAP Média (|SHAP value|)")
    plt.title("SHAP Feature Importance — Top 20", fontsize=14)
    plt.tight_layout()

    path = output_dir / "shap_feature_importance.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("SHAP bar plot salvo: %s", path)
    return path


def save_shap_waterfall_plot(
    explainer: shap.Explainer,
    X_single: np.ndarray,
    feature_names: list[str],
    employee_id: int = 0,
    output_dir: Path | None = None,
) -> Path:
    """Gera e salva o SHAP waterfall plot para um colaborador.

    Args:
        explainer: SHAP Explainer.
        X_single: Features de um colaborador (1 linha).
        feature_names: Nomes das features.
        employee_id: ID para o nome do arquivo.
        output_dir: Diretório de saída.

    Returns:
        Caminho do arquivo salvo.
    """
    if output_dir is None:
        output_dir = settings.artifacts_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    if X_single.ndim == 1:
        X_single = X_single.reshape(1, -1)

    shap_explanation = explainer(X_single)

    # Para classificação binária, pegar classe positiva
    if len(shap_explanation.values.shape) == 3:
        explanation = shap.Explanation(
            values=shap_explanation.values[0, :, 1],
            base_values=shap_explanation.base_values[0, 1],
            data=X_single[0],
            feature_names=feature_names,
        )
    else:
        explanation = shap.Explanation(
            values=shap_explanation.values[0],
            base_values=shap_explanation.base_values[0]
            if hasattr(shap_explanation.base_values, "__len__")
            else shap_explanation.base_values,
            data=X_single[0],
            feature_names=feature_names,
        )

    plt.figure(figsize=(10, 8))
    shap.plots.waterfall(explanation, show=False, max_display=15)
    plt.title(f"SHAP Waterfall — Colaborador {employee_id}", fontsize=14)
    plt.tight_layout()

    path = output_dir / f"shap_waterfall_{employee_id}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("SHAP waterfall plot salvo: %s (colaborador %d)", path, employee_id)
    return path
