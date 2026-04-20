"""Schemas Pydantic para output estruturado do LLM."""

from pydantic import BaseModel, Field


class RetentionAction(BaseModel):
    """Ação recomendada de retenção."""

    action: str = Field(..., description="Descrição da ação")
    priority: str = Field(..., description="alta, média ou baixa")
    rationale: str = Field(..., description="Justificativa baseada nos fatores")


class InsightResponse(BaseModel):
    """Insight gerado pelo LLM para um colaborador."""

    id: int = Field(..., description="ID do colaborador")
    risk_level: str = Field(..., description="baixo, médio, alto ou crítico")
    main_factors: list[str] = Field(..., description="Fatores principais em linguagem de RH")
    recommended_actions: list[str] = Field(..., description="Ações de retenção recomendadas")
    summary: str = Field(..., description="Resumo em linguagem natural")
