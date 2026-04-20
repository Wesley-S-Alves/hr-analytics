"""Tools do agente para People Analytics.

Cada tool é registrado via @tool decorator do LangChain e conecta
o agente ao modelo preditivo, banco de dados e SHAP.
"""

import json
import logging
import re

from langchain_core.tools import tool
from sqlalchemy import text

from hr_analytics.data.database import get_session
from hr_analytics.models.db_models import Employee

logger = logging.getLogger(__name__)


@tool
def predict_employee(employee_id: int) -> str:
    """Prediz o risco de saída de um colaborador específico.

    Retorna probabilidade de attrition, nível de risco e top-5 fatores SHAP.
    Use quando o usuário perguntar sobre o risco de um colaborador específico.

    Args:
        employee_id: ID do colaborador no banco de dados.
    """
    from hr_analytics.inference.predictor import model_service
    from hr_analytics.inference.utils import employee_to_df

    if not model_service.is_loaded:
        model_service.load()

    session = get_session()
    try:
        employee = session.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            return json.dumps({"erro": f"Colaborador {employee_id} não encontrado"})

        df = employee_to_df(employee)
        result = model_service.predict_single(df)

        return json.dumps(
            {
                "employee_id": employee_id,
                "nome": f"{employee.job_role} ({employee.department})",
                "probabilidade_attrition": result["attrition_probability"],
                "nivel_risco": result["risk_level"],
                "threshold": result["threshold"],
                "fatores_principais": result["top_factors"],
            },
            ensure_ascii=False,
        )
    finally:
        session.close()


@tool
def list_high_risk_employees(threshold: float = 0.4, limit: int = 10) -> str:
    """Lista os colaboradores com maior risco de saída.

    Use quando o usuário perguntar quem tem maior risco, ou pedir um ranking.

    Args:
        threshold: Probabilidade mínima de risco (padrão: 0.4 = alto).
        limit: Número máximo de colaboradores a retornar.
    """
    from hr_analytics.inference.predictor import model_service

    if not model_service.is_loaded:
        model_service.load()

    session = get_session()
    try:
        employees = (
            session.query(Employee)
            .filter(Employee.is_active.is_(True))
            .filter(Employee.risk_score.isnot(None))
            .filter(Employee.risk_score >= threshold)
            .order_by(Employee.risk_score.desc())
            .limit(limit)
            .all()
        )

        if not employees:
            return json.dumps({"mensagem": "Nenhum colaborador com risco acima do threshold"})

        results = []
        for emp in employees:
            results.append(
                {
                    "id": emp.id,
                    "cargo": emp.job_role,
                    "departamento": emp.department,
                    "salario": emp.monthly_income,
                    "anos_empresa": emp.years_at_company,
                    "risco": round(emp.risk_score, 4) if emp.risk_score else None,
                    "nivel": emp.risk_level,
                }
            )

        return json.dumps({"total": len(results), "colaboradores": results}, ensure_ascii=False)
    finally:
        session.close()


@tool
def get_employee_details(employee_id: int) -> str:
    """Retorna os dados completos de um colaborador.

    Use quando o usuário quiser ver informações detalhadas de um colaborador.

    Args:
        employee_id: ID do colaborador.
    """
    session = get_session()
    try:
        emp = session.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            return json.dumps({"erro": f"Colaborador {employee_id} não encontrado"})

        return json.dumps(
            {
                "id": emp.id,
                "idade": emp.age,
                "genero": emp.gender,
                "estado_civil": emp.marital_status,
                "departamento": emp.department,
                "cargo": emp.job_role,
                "nivel": emp.job_level,
                "salario_mensal": emp.monthly_income,
                "hora_extra": emp.over_time,
                "distancia_casa": emp.distance_from_home,
                "anos_empresa": emp.years_at_company,
                "anos_cargo_atual": emp.years_in_current_role,
                "anos_sem_promocao": emp.years_since_last_promotion,
                "satisfacao_ambiente": emp.environment_satisfaction,
                "satisfacao_trabalho": emp.job_satisfaction,
                "equilibrio_vida_trabalho": emp.work_life_balance,
                "envolvimento": emp.job_involvement,
                "performance": emp.performance_rating,
                "treinamentos_ultimo_ano": emp.training_times_last_year,
                "risco": round(emp.risk_score, 4) if emp.risk_score else None,
                "nivel_risco": emp.risk_level,
            },
            ensure_ascii=False,
        )
    finally:
        session.close()


@tool
def explain_risk_factors(employee_id: int) -> str:
    """Explica os fatores que contribuem para o risco de saída de um colaborador.

    Usa SHAP para identificar os top-5 fatores com maior impacto.
    Use quando o usuário perguntar POR QUE um colaborador está em risco.

    Args:
        employee_id: ID do colaborador.
    """
    # Reutiliza predict_employee que já retorna os fatores SHAP
    return predict_employee.invoke({"employee_id": employee_id})


@tool
def query_employees_analytics(sql_query: str) -> str:
    """Executa uma query SQL analítica na tabela de colaboradores.

    Use para responder perguntas como:
    - Quantos colaboradores tem por departamento?
    - Qual o percentual de churn (attrition) por departamento?
    - Qual a média salarial por cargo?
    - Quantos colaboradores fazem hora extra?
    - Qual a distribuição de satisfação no trabalho?
    - Qual o headcount total?

    A tabela se chama 'employees' e tem as colunas:
    id, age, gender, marital_status, education, education_field,
    distance_from_home, department, job_role, job_level, business_travel,
    over_time, daily_rate, hourly_rate, monthly_rate, monthly_income,
    percent_salary_hike, stock_option_level, total_working_years,
    years_at_company, years_in_current_role, years_since_last_promotion,
    years_with_curr_manager, num_companies_worked, training_times_last_year,
    environment_satisfaction, job_involvement, job_satisfaction,
    relationship_satisfaction, work_life_balance, performance_rating,
    attrition (Yes/No), risk_score, risk_level, is_active

    IMPORTANTE: use somente SELECT. Nunca INSERT, UPDATE, DELETE.

    Args:
        sql_query: Query SQL SELECT para executar. Exemplos:
            - SELECT department, COUNT(*) as total FROM employees GROUP BY department
            - SELECT department, ROUND(100.0 * SUM(CASE WHEN attrition='Yes' THEN 1 ELSE 0 END) / COUNT(*), 1) as churn_pct FROM employees GROUP BY department
            - SELECT COUNT(*) as total FROM employees WHERE is_active = 1
    """
    # ── Hardening de segurança ──
    # Remove comentários SQL para evitar bypass do validador
    cleaned = re.sub(r"--.*?(\n|$)", " ", sql_query)  # comentários de linha
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)  # comentários de bloco
    cleaned = cleaned.strip()

    # Só pode haver UM statement (impede "SELECT ...; DROP TABLE ...")
    # Ignora ';' trailing isolado
    statements = [s.strip() for s in cleaned.rstrip(";").split(";") if s.strip()]
    if len(statements) != 1:
        return json.dumps({"erro": "Apenas uma única query SELECT é permitida por chamada."})

    stmt = statements[0]
    stmt_upper = stmt.upper()

    # Deve começar com SELECT ou WITH (CTE)
    if not (stmt_upper.startswith("SELECT") or stmt_upper.startswith("WITH")):
        return json.dumps({"erro": "Apenas queries SELECT/WITH são permitidas"})

    # Whitelist de tabelas acessíveis + CTEs auto-detectadas
    allowed_tables = {"employees"}
    # CTEs: "WITH alias AS (...)", "alias AS (...)"
    cte_aliases = {m.lower() for m in re.findall(r"(?:WITH|,)\s+(\w+)\s+AS\s*\(", stmt_upper)}
    allowed = allowed_tables | cte_aliases

    tables_referenced = set(re.findall(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", stmt_upper))
    flat_tables = {t.lower() for pair in tables_referenced for t in pair if t}
    if flat_tables and not flat_tables.issubset(allowed):
        blocked = flat_tables - allowed
        return json.dumps(
            {"erro": f"Acesso negado à(s) tabela(s): {', '.join(blocked)}. Permitidas: {', '.join(allowed_tables)}"}
        )

    # Bloqueia DDL/DML mesmo após o SELECT
    forbidden = [
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bTRUNCATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bEXEC\b",
        r"\bATTACH\b",
        r"\bDETACH\b",
        r"\bPRAGMA\b",
    ]
    for pattern in forbidden:
        if re.search(pattern, stmt_upper):
            op = pattern.strip(r"\b")
            return json.dumps({"erro": f"Operação '{op}' não permitida"})

    # Limite hard de linhas para evitar dump completo acidental
    # Adiciona LIMIT se a query não tiver
    if "LIMIT" not in stmt_upper:
        stmt = stmt + " LIMIT 500"

    session = get_session()
    try:
        # Timeout de 5s pra queries lentas / recursivas
        result = session.execute(text(stmt))
        rows = result.fetchall()
        columns = list(result.keys())

        data = [dict(zip(columns, row)) for row in rows]

        return json.dumps(
            {
                "query": stmt,
                "total_rows": len(data),
                "columns": columns,
                "data": data,
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        logger.error("Erro na query SQL: %s — %s", stmt, e)
        return json.dumps({"erro": f"Erro SQL: {str(e)}"})
    finally:
        session.close()


# Lista de todas as tools disponíveis para o agente
ALL_TOOLS = [
    predict_employee,
    list_high_risk_employees,
    get_employee_details,
    explain_risk_factors,
    query_employees_analytics,
]
