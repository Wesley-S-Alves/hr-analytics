"""Feature engineering de domínio para People Analytics.

Cria features derivadas que capturam padrões de risco de attrition
baseados em conhecimento de domínio de RH.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def add_domain_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona features derivadas de domínio ao DataFrame.

    Todas as features são calculadas a partir das colunas originais
    e representam fatores conhecidos de risco de attrition.

    Args:
        df: DataFrame com colunas originais do dataset.

    Returns:
        DataFrame com features adicionais.
    """
    df = df.copy()

    # Razão de permanência: proporção do tempo de carreira gasto na empresa
    # Valores baixos podem indicar histórico de trocas frequentes
    df["tenure_ratio"] = np.where(
        df["total_working_years"] > 0,
        df["years_at_company"] / df["total_working_years"],
        0.0,
    )

    # Índice de satisfação composto: média das 4 dimensões de satisfação
    # Escala 1-4, valores baixos indicam insatisfação generalizada
    satisfaction_cols = [
        "environment_satisfaction",
        "job_satisfaction",
        "relationship_satisfaction",
        "work_life_balance",
    ]
    df["satisfaction_index"] = df[satisfaction_cols].mean(axis=1)

    # Estagnação de carreira: tempo sem promoção relativo ao tempo na empresa
    # Valores altos indicam falta de crescimento
    df["career_stagnation"] = np.where(
        df["years_at_company"] > 0,
        df["years_since_last_promotion"] / df["years_at_company"],
        0.0,
    )

    # Renda anual: facilita comparações e é mais intuitiva
    df["income_annual"] = df["monthly_income"] * 12

    # Renda por nível: salário relativo ao nível hierárquico
    # Valores baixos podem indicar sub-remuneração para o cargo
    df["income_per_level"] = np.where(
        df["job_level"] > 0,
        df["monthly_income"] / df["job_level"],
        df["monthly_income"],
    )

    # Anos desde última promoção relativo a anos no cargo atual
    # Indica se a pessoa está "presa" no mesmo cargo
    df["promotion_gap"] = df["years_since_last_promotion"] - df["years_in_current_role"]

    # Flag de viagem frequente: business_travel como indicador binário
    df["frequent_traveler"] = (df["business_travel"] == "Travel_Frequently").astype(int)

    # Experiência prévia: número de empresas antes da atual
    # Pode indicar propensão a trocas
    df["companies_per_year"] = np.where(
        df["total_working_years"] > 0,
        df["num_companies_worked"] / df["total_working_years"],
        0.0,
    )

    logger.info(
        "Features de domínio adicionadas: %d novas colunas",
        8,  # quantidade de features adicionadas
    )

    return df


# Lista das features derivadas para referência
DERIVED_FEATURES = [
    "tenure_ratio",
    "satisfaction_index",
    "career_stagnation",
    "income_annual",
    "income_per_level",
    "promotion_gap",
    "frequent_traveler",
    "companies_per_year",
]
