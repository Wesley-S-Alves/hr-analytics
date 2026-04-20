"""Rota de explicabilidade SHAP."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from hr_analytics.api.dependencies import get_db, get_model_service
from hr_analytics.inference.predictor import ModelService
from hr_analytics.inference.schemas import ExplanationResponse, RiskFactor
from hr_analytics.inference.utils import employee_to_df
from hr_analytics.models.db_models import Employee

router = APIRouter(prefix="/explain", tags=["Explicabilidade"])


@router.get("/{employee_id}", response_model=ExplanationResponse)
def explain_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service),
):
    """Retorna a explicação SHAP dos fatores de risco de um colaborador."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")

    df = employee_to_df(employee)
    result = service.predict_single(df)

    return ExplanationResponse(
        employee_id=employee_id,
        attrition_probability=result["attrition_probability"],
        risk_level=result["risk_level"],
        factors=[RiskFactor(**f) for f in result["top_factors"]],
    )
