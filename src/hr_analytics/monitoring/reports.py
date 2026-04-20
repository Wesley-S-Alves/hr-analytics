"""Geração de relatórios de monitoramento."""

import logging
from datetime import datetime

from hr_analytics.monitoring.drift import generate_drift_report
from hr_analytics.monitoring.observability import tracker

logger = logging.getLogger(__name__)


def generate_full_report(hours: int = 24) -> dict:
    """Gera relatório completo de monitoramento (drift + observabilidade).

    Args:
        hours: Janela de tempo para métricas de observabilidade.

    Returns:
        Dicionário com relatório completo.
    """
    # Relatório de drift
    drift_report = generate_drift_report()

    # Métricas de observabilidade
    tracker.flush()
    obs_summary = tracker.get_summary(hours=hours)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "drift": {
            "overall_status": drift_report.overall_status,
            "recommendation": drift_report.recommendation,
            "features_drifted": drift_report.features_drifted,
            "features_warning": drift_report.features_warning,
            "prediction_psi": drift_report.prediction_psi,
            "feature_psi": drift_report.feature_psi,
        },
        "observability": {
            "period_hours": hours,
            "metrics_by_type": obs_summary,
        },
    }
