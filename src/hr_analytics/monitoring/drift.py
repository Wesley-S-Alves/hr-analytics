"""Monitoramento de drift via PSI (Population Stability Index).

Compara distribuições de features entre treino (referência) e dados atuais
para detectar mudanças que possam degradar a performance do modelo.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import numpy as np

from hr_analytics.config import settings
from hr_analytics.models.registry import load_reference_distributions

logger = logging.getLogger(__name__)

# Constante pequena para evitar divisão por zero no log
EPSILON = 1e-6


def calculate_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Calcula o Population Stability Index (PSI) entre duas distribuições.

    PSI < 0.1  → sem drift significativo (verde)
    PSI 0.1-0.2 → drift moderado (amarelo) — investigar
    PSI > 0.2  → drift significativo (vermelho) — considerar retreino

    Fórmula: PSI = Σ (actual_% - expected_%) × ln(actual_% / expected_%)

    Args:
        expected: Array com valores da distribuição de referência (treino).
        actual: Array com valores da distribuição atual (produção).
        bins: Número de bins para discretização.

    Returns:
        Valor PSI (float >= 0).
    """
    # Definir breakpoints baseados na distribuição de referência
    breakpoints = np.linspace(
        min(expected.min(), actual.min()),
        max(expected.max(), actual.max()),
        bins + 1,
    )

    # Calcular proporções em cada bin
    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]

    # Converter para proporções (adicionar epsilon para evitar log(0))
    expected_pct = (expected_counts + EPSILON) / (expected_counts.sum() + EPSILON * bins)
    actual_pct = (actual_counts + EPSILON) / (actual_counts.sum() + EPSILON * bins)

    # Fórmula PSI
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))

    return float(psi)


def calculate_csi(expected_counts: dict, actual_counts: dict) -> float:
    """Calcula o Characteristic Stability Index (CSI) para features categóricas.

    Equivalente ao PSI, mas para variáveis categóricas.

    Args:
        expected_counts: Contagem de cada categoria na referência.
        actual_counts: Contagem de cada categoria nos dados atuais.

    Returns:
        Valor CSI (float >= 0).
    """
    all_categories = set(expected_counts.keys()) | set(actual_counts.keys())

    total_expected = sum(expected_counts.values()) + EPSILON * len(all_categories)
    total_actual = sum(actual_counts.values()) + EPSILON * len(all_categories)

    csi = 0.0
    for cat in all_categories:
        exp_pct = (expected_counts.get(cat, 0) + EPSILON) / total_expected
        act_pct = (actual_counts.get(cat, 0) + EPSILON) / total_actual
        csi += (act_pct - exp_pct) * np.log(act_pct / exp_pct)

    return float(csi)


@dataclass
class DriftReport:
    """Relatório de drift do modelo."""

    generated_at: datetime = field(default_factory=datetime.utcnow)
    reference_period: str = "treino"
    current_period: str = "atual"
    feature_psi: dict[str, float] = field(default_factory=dict)
    prediction_psi: float = 0.0
    features_drifted: list[str] = field(default_factory=list)
    features_warning: list[str] = field(default_factory=list)
    overall_status: Literal["ok", "warning", "alert"] = "ok"
    recommendation: str = "Modelo estável — nenhuma ação necessária"

    def classify_features(self) -> None:
        """Classifica features por nível de drift."""
        self.features_drifted = [f for f, psi in self.feature_psi.items() if psi > 0.2]
        self.features_warning = [f for f, psi in self.feature_psi.items() if 0.1 <= psi <= 0.2]

        if self.features_drifted:
            self.overall_status = "alert"
            self.recommendation = (
                f"Drift significativo detectado em {len(self.features_drifted)} feature(s): "
                f"{', '.join(self.features_drifted[:5])}. "
                "Recomendação: retreinar o modelo com dados atualizados."
            )
        elif self.features_warning:
            self.overall_status = "warning"
            self.recommendation = (
                f"Drift moderado em {len(self.features_warning)} feature(s): "
                f"{', '.join(self.features_warning[:5])}. "
                "Recomendação: monitorar nas próximas semanas."
            )
        else:
            self.overall_status = "ok"
            self.recommendation = "Modelo estável — nenhuma ação necessária."


def generate_drift_report() -> DriftReport:
    """Gera relatório completo de drift comparando treino vs dados atuais.

    Returns:
        DriftReport com PSI por feature, status geral e recomendação.
    """
    report = DriftReport()

    try:
        reference = load_reference_distributions()
    except FileNotFoundError:
        report.recommendation = "Distribuições de referência não encontradas. Execute o treino."
        return report

    # Carregar dados atuais do Parquet
    try:
        import pandas as pd

        parquet_path = settings.data_processed_dir / "employees.parquet"
        if not parquet_path.exists():
            report.recommendation = "Dados atuais não encontrados em Parquet."
            return report

        df_current = pd.read_parquet(parquet_path)
    except Exception as e:
        report.recommendation = f"Erro ao carregar dados atuais: {e}"
        return report

    # Calcular PSI para cada feature numérica
    from hr_analytics.data.feature_engineering import add_domain_features
    from hr_analytics.data.preprocessing import build_preprocessor, prepare_features

    df_current = add_domain_features(df_current)
    X_raw = prepare_features(df_current)

    preprocessor = build_preprocessor()
    try:
        X_current = preprocessor.fit_transform(X_raw)
    except Exception as e:
        report.recommendation = f"Erro no preprocessamento: {e}"
        return report

    feature_names = list(preprocessor.get_feature_names_out())

    for i, name in enumerate(feature_names):
        if name in reference:
            ref_values = reference[name]
            curr_values = X_current[:, i]

            # Filtrar NaN e Inf
            ref_clean = ref_values[np.isfinite(ref_values)]
            curr_clean = curr_values[np.isfinite(curr_values)]

            if len(ref_clean) > 0 and len(curr_clean) > 0:
                psi = calculate_psi(ref_clean, curr_clean)
                report.feature_psi[name] = round(psi, 6)

    # Classificar features
    report.classify_features()

    logger.info(
        "Drift report: status=%s, drifted=%d, warning=%d",
        report.overall_status,
        len(report.features_drifted),
        len(report.features_warning),
    )

    return report
