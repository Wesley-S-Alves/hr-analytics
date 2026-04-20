"""Helpers compartilhados entre rotas API e tools do agente.

Evita duplicação de `_employee_to_df` que existia em 3 arquivos
(routes/predict.py, routes/explain.py, agent/tools.py).
"""

import pandas as pd

from hr_analytics.models.db_models import Employee

# Campos usados pelo preprocessador do modelo — mantém sincronizado com feature_engineering.
_EMPLOYEE_DF_COLUMNS = (
    "age",
    "gender",
    "marital_status",
    "education",
    "education_field",
    "distance_from_home",
    "department",
    "job_role",
    "job_level",
    "business_travel",
    "over_time",
    "daily_rate",
    "hourly_rate",
    "monthly_rate",
    "monthly_income",
    "percent_salary_hike",
    "stock_option_level",
    "total_working_years",
    "years_at_company",
    "years_in_current_role",
    "years_since_last_promotion",
    "years_with_curr_manager",
    "num_companies_worked",
    "training_times_last_year",
    "environment_satisfaction",
    "job_involvement",
    "job_satisfaction",
    "relationship_satisfaction",
    "work_life_balance",
    "performance_rating",
)


def employee_to_df(employee: Employee) -> pd.DataFrame:
    """Converte um registro ORM Employee para DataFrame de 1 linha.

    Usado por predição individual, explicabilidade SHAP e tools do agente.
    """
    data = {col: [getattr(employee, col)] for col in _EMPLOYEE_DF_COLUMNS}
    return pd.DataFrame(data)
