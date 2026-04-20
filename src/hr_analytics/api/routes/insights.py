"""Rota de geração de insights via LLM em batch."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from hr_analytics.api.dependencies import get_db, get_model_service
from hr_analytics.inference.predictor import ModelService
from hr_analytics.inference.utils import employee_to_df
from hr_analytics.models.db_models import Employee

router = APIRouter(prefix="/insights", tags=["Insights LLM"])


@router.post("/batch")
async def generate_insights_batch(
    employee_ids: list[int],
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service),
):
    """Gera insights via LLM em batch para múltiplos colaboradores.

    async + semaphore + multi-item prompts.
    """
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all()

    if not employees:
        raise HTTPException(status_code=404, detail="Nenhum colaborador encontrado")

    # Coletar predições + fatores para cada colaborador
    items = []
    for emp in employees:
        df = employee_to_df(emp)
        result = service.predict_single(df)
        items.append(
            {
                "employee_id": emp.id,
                "department": emp.department,
                "job_role": emp.job_role,
                "monthly_income": emp.monthly_income,
                "years_at_company": emp.years_at_company,
                "attrition_probability": result["attrition_probability"],
                "risk_level": result["risk_level"],
                "top_factors": result["top_factors"],
            }
        )

    # Gerar insights via LLM batch
    from hr_analytics.llm.batch import generate_insights_batch

    insights = await generate_insights_batch(items)

    return {
        "total": len(insights),
        "insights": insights,
    }
