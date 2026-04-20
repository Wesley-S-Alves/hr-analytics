"""Rotas de predição de risco de attrition."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from hr_analytics.api.dependencies import get_db, get_model_service
from hr_analytics.inference.predictor import ModelService
from hr_analytics.inference.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionRequest,
    PredictionResponse,
    RiskFactor,
)
from hr_analytics.inference.utils import employee_to_df
from hr_analytics.models.db_models import Employee

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Predição"])


@router.post("", response_model=PredictionResponse)
def predict_single(
    request: PredictionRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service),
):
    """Predição de risco para um colaborador com explicação SHAP."""
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")

    try:
        df = employee_to_df(employee)
        result = service.predict_single(df)

        # Atualizar risco no banco
        employee.risk_score = result["attrition_probability"]
        employee.risk_level = result["risk_level"]
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Erro em /predict para employee_id=%s", request.employee_id)
        raise HTTPException(status_code=500, detail=f"Erro na predição: {e}")

    return PredictionResponse(
        employee_id=request.employee_id,
        attrition_probability=result["attrition_probability"],
        risk_level=result["risk_level"],
        threshold=result["threshold"],
        top_factors=[RiskFactor(**f) for f in result["top_factors"]],
    )


@router.post("/batch", response_model=BatchPredictionResponse)
def predict_batch(
    request: BatchPredictionRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service),
):
    """Predição de risco em lote para múltiplos colaboradores.

    Usa transação com rollback: se qualquer predição falhar, nenhuma
    atualização de risk_score é persistida (consistência atômica).
    """
    employees = db.query(Employee).filter(Employee.id.in_(request.employee_ids)).all()

    if not employees:
        raise HTTPException(status_code=404, detail="Nenhum colaborador encontrado")

    predictions = []
    failed_ids: list[int] = []

    try:
        for emp in employees:
            try:
                df = employee_to_df(emp)
                result = service.predict_single(df)
            except Exception as e:
                logger.warning("Predição falhou para employee_id=%s: %s", emp.id, e)
                failed_ids.append(emp.id)
                continue

            # Atualizar risco no banco (ainda não commitado)
            emp.risk_score = result["attrition_probability"]
            emp.risk_level = result["risk_level"]

            predictions.append(
                PredictionResponse(
                    employee_id=emp.id,
                    attrition_probability=result["attrition_probability"],
                    risk_level=result["risk_level"],
                    threshold=result["threshold"],
                    top_factors=[RiskFactor(**f) for f in result["top_factors"]],
                )
            )

        # Commit único no final — rollback automático se sair do try
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Erro crítico em /predict/batch — rollback completo")
        raise HTTPException(status_code=500, detail=f"Erro na predição em lote: {e}")

    if failed_ids:
        logger.info("predict/batch concluiu com %d falhas parciais: %s", len(failed_ids), failed_ids)

    high_risk = sum(1 for p in predictions if p.risk_level in ("alto", "crítico"))

    return BatchPredictionResponse(
        predictions=predictions,
        total=len(predictions),
        high_risk_count=high_risk,
    )


class SimulationRequest(BaseModel):
    """Request pra simulação dry-run: base no colaborador real + overrides."""

    employee_id: int
    overrides: dict = {}


@router.post("/simulate", response_model=PredictionResponse)
def predict_simulate(
    request: SimulationRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service),
):
    """Predição dry-run — NÃO persiste alterações no banco.

    Carrega o colaborador real, aplica `overrides` nos campos do DataFrame
    antes de enviar ao modelo. Ideal pro simulador 'E se?'.
    """
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")

    try:
        df = employee_to_df(employee)
        # Aplica overrides — só nos campos que existem no DF
        for field, value in (request.overrides or {}).items():
            if field in df.columns:
                df[field] = value
        result = service.predict_single(df)
    except Exception as e:
        logger.exception("Erro em /predict/simulate")
        raise HTTPException(status_code=500, detail=f"Erro na simulação: {e}")

    return PredictionResponse(
        employee_id=request.employee_id,
        attrition_probability=result["attrition_probability"],
        risk_level=result["risk_level"],
        threshold=result["threshold"],
        top_factors=[RiskFactor(**f) for f in result["top_factors"]],
    )
