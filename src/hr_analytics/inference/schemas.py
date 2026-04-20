"""Schemas Pydantic v2 para request/response da API."""

from datetime import datetime

from pydantic import BaseModel, Field

# === Predição ===


class PredictionRequest(BaseModel):
    """Requisição de predição individual."""

    employee_id: int = Field(..., description="ID do colaborador")


class BatchPredictionRequest(BaseModel):
    """Requisição de predição em lote."""

    employee_ids: list[int] = Field(..., description="Lista de IDs dos colaboradores")


class RiskFactor(BaseModel):
    """Fator que contribui para o risco de attrition."""

    feature: str = Field(..., description="Nome da feature")
    shap_value: float = Field(..., description="Valor SHAP (impacto no risco)")
    impact: str = Field(..., description="Direção do impacto: aumenta_risco ou diminui_risco")
    magnitude: float = Field(..., description="Magnitude absoluta do impacto")


class PredictionResponse(BaseModel):
    """Resposta de predição individual."""

    employee_id: int
    attrition_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str = Field(..., description="baixo, médio, alto ou crítico")
    threshold: float
    top_factors: list[RiskFactor] = Field(default_factory=list)


class BatchPredictionResponse(BaseModel):
    """Resposta de predição em lote."""

    predictions: list[PredictionResponse]
    total: int
    high_risk_count: int = Field(description="Colaboradores com risco alto ou crítico")


# === Colaboradores ===


class EmployeeCreate(BaseModel):
    """Dados para cadastro de colaborador."""

    age: int = Field(..., ge=18, le=70)
    gender: str
    marital_status: str
    education: int = Field(..., ge=1, le=5)
    education_field: str
    distance_from_home: int = Field(..., ge=0)
    department: str
    job_role: str
    job_level: int = Field(..., ge=1, le=5)
    business_travel: str
    over_time: str
    daily_rate: int = Field(..., ge=0)
    hourly_rate: int = Field(..., ge=0)
    monthly_rate: int = Field(..., ge=0)
    monthly_income: int = Field(..., ge=0)
    percent_salary_hike: int = Field(..., ge=0)
    stock_option_level: int = Field(..., ge=0, le=3)
    total_working_years: int = Field(..., ge=0)
    years_at_company: int = Field(..., ge=0)
    years_in_current_role: int = Field(..., ge=0)
    years_since_last_promotion: int = Field(..., ge=0)
    years_with_curr_manager: int = Field(..., ge=0)
    num_companies_worked: int = Field(..., ge=0)
    training_times_last_year: int = Field(..., ge=0)
    environment_satisfaction: int = Field(..., ge=1, le=4)
    job_involvement: int = Field(..., ge=1, le=4)
    job_satisfaction: int = Field(..., ge=1, le=4)
    relationship_satisfaction: int = Field(..., ge=1, le=4)
    work_life_balance: int = Field(..., ge=1, le=4)
    performance_rating: int = Field(..., ge=1, le=4)


class EmployeeUpdate(BaseModel):
    """Dados para atualização parcial de colaborador."""

    age: int | None = None
    department: str | None = None
    job_role: str | None = None
    job_level: int | None = None
    monthly_income: int | None = None
    over_time: str | None = None
    environment_satisfaction: int | None = None
    job_satisfaction: int | None = None
    work_life_balance: int | None = None


class EmployeeResponse(BaseModel):
    """Resposta com dados do colaborador."""

    id: int
    age: int
    gender: str
    marital_status: str | None = None
    education: int | None = None
    education_field: str | None = None
    distance_from_home: int | None = None
    department: str
    job_role: str
    job_level: int
    business_travel: str | None = None
    over_time: str
    daily_rate: int | None = None
    hourly_rate: int | None = None
    monthly_rate: int | None = None
    monthly_income: int
    percent_salary_hike: int | None = None
    stock_option_level: int | None = None
    total_working_years: int | None = None
    years_at_company: int
    years_in_current_role: int | None = None
    years_since_last_promotion: int | None = None
    years_with_curr_manager: int | None = None
    num_companies_worked: int | None = None
    training_times_last_year: int | None = None
    environment_satisfaction: int | None = None
    job_involvement: int | None = None
    job_satisfaction: int | None = None
    relationship_satisfaction: int | None = None
    work_life_balance: int | None = None
    performance_rating: int | None = None
    attrition: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    """Resposta paginada de lista de colaboradores."""

    employees: list[EmployeeResponse]
    total: int
    page: int
    page_size: int


# === Usuários ===


class UserCreate(BaseModel):
    """Dados para cadastro de usuário."""

    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    role: str = Field(..., description="Cargo do usuário no sistema")
    department: str | None = None


class UserResponse(BaseModel):
    """Resposta com dados do usuário."""

    id: int
    name: str
    email: str
    role: str
    department: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# === Explicabilidade ===


class ExplanationResponse(BaseModel):
    """Resposta com explicação SHAP de um colaborador."""

    employee_id: int
    attrition_probability: float
    risk_level: str
    factors: list[RiskFactor]


# === Agente ===


class AgentChatRequest(BaseModel):
    """Requisição para o agente conversacional."""

    message: str = Field(..., min_length=1, max_length=20000)
    conversation_id: str | None = Field(None, description="ID da conversação para manter contexto")


class ChartData(BaseModel):
    """Dados para renderização de gráfico no frontend."""

    chart_type: str = Field(..., description="bar, pie, line, horizontal_bar")
    title: str = Field(..., description="Título do gráfico")
    x_label: str = Field(default="", description="Label do eixo X")
    y_label: str = Field(default="", description="Label do eixo Y")
    data: list[dict] = Field(..., description="Dados em formato [{label: ..., value: ...}]")


class AgentChatResponse(BaseModel):
    """Resposta do agente conversacional."""

    response: str
    structured_data: dict | None = Field(None, description="Dados estruturados (JSON de insights)")
    chart: ChartData | None = Field(None, description="Dados para gráfico (se aplicável)")
    conversation_id: str
    tools_used: list[str] = Field(default_factory=list)


# === Monitoramento ===


class DriftReportResponse(BaseModel):
    """Resposta do relatório de drift."""

    overall_status: str = Field(..., description="ok, warning ou alert")
    prediction_psi: float
    features_drifted: list[str]
    features_warning: list[str]
    feature_psi: dict[str, float]
    recommendation: str


# === Health ===


class HealthResponse(BaseModel):
    """Resposta do health check."""

    status: str
    model_loaded: bool
    model_name: str | None = None
    database_ok: bool
    version: str = "1.0.0"
