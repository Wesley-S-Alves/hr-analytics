"""Dicionário central de traduções EN→PT.

Usado por todas as páginas Streamlit para garantir consistência visual.
Não renomeia no banco — só na exibição.
"""

DEPT_PT = {
    "Sales": "Vendas",
    "Research & Development": "Pesquisa e Desenvolvimento",
    "Human Resources": "Recursos Humanos",
}

ROLE_PT = {
    "Sales Executive": "Executivo de Vendas",
    "Sales Representative": "Representante de Vendas",
    "Research Scientist": "Cientista de Pesquisa",
    "Laboratory Technician": "Técnico de Laboratório",
    "Manufacturing Director": "Diretor de Manufatura",
    "Healthcare Representative": "Representante de Saúde",
    "Manager": "Gerente",
    "Research Director": "Diretor de Pesquisa",
    "Human Resources": "Profissional de RH",
}

EDUCATION_FIELD_PT = {
    "Life Sciences": "Ciências da Vida",
    "Medical": "Medicina",
    "Technical Degree": "Técnico",
    "Marketing": "Marketing",
    "Human Resources": "Recursos Humanos",
    "Other": "Outra",
}

GENDER_PT = {"Male": "Masculino", "Female": "Feminino"}

MARITAL_PT = {
    "Single": "Solteiro(a)",
    "Married": "Casado(a)",
    "Divorced": "Divorciado(a)",
}

TRAVEL_PT = {
    "Travel_Rarely": "Viaja raramente",
    "Travel_Frequently": "Viaja frequentemente",
    "Non-Travel": "Não viaja",
}

OVERTIME_PT = {"Yes": "Sim", "No": "Não"}

EDUCATION_LEVEL_PT = {
    1: "Ensino Fundamental",
    2: "Ensino Médio",
    3: "Graduação",
    4: "Mestrado",
    5: "Doutorado",
}

SATISFACTION_PT = {
    1: "Baixa",
    2: "Média",
    3: "Alta",
    4: "Muito Alta",
}


def tr_dept(v: str) -> str:
    """Traduz departamento."""
    return DEPT_PT.get(v, v or "—")


def tr_role(v: str) -> str:
    """Traduz cargo."""
    return ROLE_PT.get(v, v or "—")


def tr_education_field(v: str) -> str:
    """Traduz área de formação."""
    return EDUCATION_FIELD_PT.get(v, v or "—")


def tr_gender(v: str) -> str:
    """Traduz gênero."""
    return GENDER_PT.get(v, v or "—")


def tr_marital(v: str) -> str:
    """Traduz estado civil."""
    return MARITAL_PT.get(v, v or "—")


def tr_travel(v: str) -> str:
    """Traduz frequência de viagens."""
    return TRAVEL_PT.get(v, v or "—")


def tr_overtime(v: str) -> str:
    """Traduz hora extra."""
    return OVERTIME_PT.get(v, v or "—")


def tr_education_level(v) -> str:
    """Traduz nível de escolaridade (1-5)."""
    try:
        return EDUCATION_LEVEL_PT.get(int(v), str(v))
    except (ValueError, TypeError):
        return "—"


def tr_satisfaction(v) -> str:
    """Traduz escala de satisfação (1-4)."""
    try:
        return SATISFACTION_PT.get(int(v), str(v))
    except (ValueError, TypeError):
        return "—"


# ──────────────────────────────────────────────────────────────
# Helpers para aplicar em DataFrames inteiros — reutilizáveis
# ──────────────────────────────────────────────────────────────

# Mapeamento coluna → função de tradução
_COLUMN_TRANSLATORS = {
    "department": tr_dept,
    "job_role": tr_role,
    "gender": tr_gender,
    "marital_status": tr_marital,
    "business_travel": tr_travel,
    "over_time": tr_overtime,
    "education_field": tr_education_field,
    "education": tr_education_level,
    "job_satisfaction": tr_satisfaction,
    "environment_satisfaction": tr_satisfaction,
    "relationship_satisfaction": tr_satisfaction,
    "work_life_balance": tr_satisfaction,
    "job_involvement": tr_satisfaction,
}

# Mapeamento nome de coluna EN → PT (p/ rename)
COLUMN_LABELS_PT = {
    "id": "ID",
    "age": "Idade",
    "gender": "Gênero",
    "marital_status": "Estado Civil",
    "education": "Escolaridade",
    "education_field": "Área de Formação",
    "distance_from_home": "Distância (km)",
    "department": "Departamento",
    "job_role": "Cargo",
    "job_level": "Nível do Cargo",
    "business_travel": "Viagens",
    "over_time": "Hora Extra",
    "monthly_income": "Salário",
    "years_at_company": "Anos na Empresa",
    "years_in_current_role": "Anos no Cargo",
    "years_since_last_promotion": "Anos sem Promoção",
    "years_with_curr_manager": "Anos c/ Gestor",
    "num_companies_worked": "Empresas Anteriores",
    "training_times_last_year": "Treinamentos",
    "total_working_years": "Experiência (anos)",
    "percent_salary_hike": "% Último Aumento",
    "stock_option_level": "Stock Options",
    "performance_rating": "Desempenho",
    "job_satisfaction": "Satisf. Trabalho",
    "environment_satisfaction": "Satisf. Ambiente",
    "relationship_satisfaction": "Satisf. Relacionamentos",
    "work_life_balance": "Equilíbrio Vida",
    "job_involvement": "Envolvimento",
    "attrition": "Saiu?",
    "risk_score": "Score de Risco",
    "risk_level": "Nível de Risco",
}


def translate_df(df, rename_columns: bool = True, translate_values: bool = True):
    """Retorna uma cópia do DataFrame com valores EN→PT + colunas renomeadas.

    Função única reutilizável por todas as páginas (Dashboard, Comparador,
    Relatório, Listar, etc.) para exibição consistente em PT-BR.

    Args:
        df: DataFrame com colunas EN (ex: department, job_role, gender).
        rename_columns: se True, renomeia colunas usando COLUMN_LABELS_PT.
        translate_values: se True, aplica funções tr_* em cada coluna conhecida.

    Returns:
        Novo DataFrame pronto pra exibição (não modifica o original).
    """
    import pandas as pd  # lazy import

    out = df.copy()
    if translate_values:
        for col, translator in _COLUMN_TRANSLATORS.items():
            if col in out.columns:
                out[col] = out[col].apply(translator)
    if rename_columns:
        out = out.rename(columns={c: COLUMN_LABELS_PT[c] for c in out.columns if c in COLUMN_LABELS_PT})
    return out


def format_employee_option(row, include_risk: bool = True) -> str:
    """Formata uma linha de Employee como string amigável pra selectbox.

    Padrão consistente com a página Colaborador:
        'ID 42 — Gerente (Vendas) — alto'
    """
    role_pt = tr_role(row.get("job_role", ""))
    dept_pt = tr_dept(row.get("department", ""))
    eid = row.get("id", "?")
    risk = ""
    if include_risk and row.get("risk_level"):
        risk = f" — {row['risk_level']}"
    return f"ID {eid} — {role_pt} ({dept_pt}){risk}"
