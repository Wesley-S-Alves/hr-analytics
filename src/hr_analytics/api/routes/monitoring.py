"""Rotas de monitoramento: drift, saúde do modelo e observabilidade."""

from fastapi import APIRouter, Query

from hr_analytics.inference.schemas import DriftReportResponse
from hr_analytics.monitoring.observability import tracker

router = APIRouter(prefix="/monitoring", tags=["Monitoramento"])


@router.get("/drift", response_model=DriftReportResponse)
def get_drift_report():
    """Retorna relatório de drift (PSI por feature)."""
    from hr_analytics.monitoring.drift import generate_drift_report

    report = generate_drift_report()
    return DriftReportResponse(
        overall_status=report.overall_status,
        prediction_psi=report.prediction_psi,
        features_drifted=report.features_drifted,
        features_warning=report.features_warning,
        feature_psi=report.feature_psi,
        recommendation=report.recommendation,
    )


@router.get("/health")
def get_model_health():
    """Retorna saúde do modelo (métricas atuais vs treino)."""
    from hr_analytics.models.registry import load_model

    try:
        artifacts = load_model()
        metadata = artifacts["metadata"]
        return {
            "status": "healthy",
            "model_name": metadata["model_name"],
            "metrics": metadata["metrics"],
            "threshold": metadata["threshold"],
            "trained_at": metadata["timestamp"],
        }
    except FileNotFoundError:
        return {"status": "no_model", "message": "Nenhum modelo treinado"}


@router.get("/observability")
def get_observability_summary(hours: int = Query(24, ge=1, le=168)):
    """Retorna resumo de observabilidade das últimas N horas.

    Métricas: latência, inferências, tokens gastos, custos estimados.
    """
    # Flush buffer antes de consultar
    tracker.flush()
    summary = tracker.get_summary(hours=hours)
    return {
        "period_hours": hours,
        "metrics_by_type": summary,
    }
