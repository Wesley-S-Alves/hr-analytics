"""Registro e versionamento de modelos e artefatos.

Salva e carrega modelos treinados, preprocessors, explainers e metadata
de forma organizada em artifacts/.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from hr_analytics.config import settings

logger = logging.getLogger(__name__)


def _artifacts_path() -> Path:
    """Retorna o diretório de artefatos, criando se necessário."""
    path = settings.artifacts_dir / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_model(
    model: Any,
    preprocessor: Any,
    model_name: str,
    metrics: dict[str, float],
    feature_names: list[str],
    threshold: float,
    params: dict[str, Any] | None = None,
) -> Path:
    """Salva modelo, preprocessor e metadata.

    Args:
        model: Modelo treinado.
        preprocessor: ColumnTransformer fitado.
        model_name: Nome identificador do modelo.
        metrics: Métricas de avaliação.
        feature_names: Nomes das features após transformação.
        threshold: Threshold ótimo de classificação.
        params: Hiperparâmetros do modelo.

    Returns:
        Caminho do diretório onde os artefatos foram salvos.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = _artifacts_path() / f"{model_name}_{timestamp}"
    model_dir.mkdir(parents=True, exist_ok=True)

    # Salvar modelo
    model_path = model_dir / "model.joblib"
    joblib.dump(model, model_path)

    # Salvar preprocessor
    preprocessor_path = model_dir / "preprocessor.joblib"
    joblib.dump(preprocessor, preprocessor_path)

    # Salvar metadata
    metadata = {
        "model_name": model_name,
        "timestamp": timestamp,
        "metrics": metrics,
        "threshold": threshold,
        "feature_names": feature_names,
        "params": params or {},
    }
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Criar symlink para "latest" (facilita carregamento)
    latest_link = _artifacts_path() / "latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(model_dir.name)

    logger.info("Modelo salvo em %s", model_dir)
    return model_dir


def load_model(model_dir: Path | None = None) -> dict[str, Any]:
    """Carrega modelo, preprocessor e metadata.

    Args:
        model_dir: Diretório do modelo. Se None, carrega o mais recente (latest).

    Returns:
        Dicionário com 'model', 'preprocessor', 'metadata'.
    """
    if model_dir is None:
        latest_link = _artifacts_path() / "latest"
        if not latest_link.exists():
            raise FileNotFoundError("Nenhum modelo encontrado. Execute 'make train' primeiro.")
        model_dir = latest_link.resolve()

    model = joblib.load(model_dir / "model.joblib")
    preprocessor = joblib.load(model_dir / "preprocessor.joblib")

    with open(model_dir / "metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)

    logger.info(
        "Modelo carregado: %s (ROC-AUC: %.4f)",
        metadata["model_name"],
        metadata["metrics"].get("roc_auc", 0),
    )

    return {
        "model": model,
        "preprocessor": preprocessor,
        "metadata": metadata,
    }


def save_reference_distributions(distributions: dict[str, np.ndarray]) -> Path:
    """Salva distribuições de referência do treino para monitoramento de drift.

    Args:
        distributions: Dicionário {feature_name: array_de_valores}.

    Returns:
        Caminho do arquivo salvo.
    """
    import pandas as pd

    output_path = settings.artifacts_dir / "reference_distributions.parquet"
    df = pd.DataFrame(distributions)
    df.to_parquet(output_path, index=False)
    logger.info("Distribuições de referência salvas: %s", output_path)
    return output_path


def load_reference_distributions() -> dict[str, np.ndarray]:
    """Carrega distribuições de referência do treino.

    Returns:
        Dicionário {feature_name: array_de_valores}.
    """
    import pandas as pd

    path = settings.artifacts_dir / "reference_distributions.parquet"
    if not path.exists():
        raise FileNotFoundError("Distribuições de referência não encontradas. Execute 'make train' primeiro.")

    df = pd.read_parquet(path)
    return {col: df[col].values for col in df.columns}
