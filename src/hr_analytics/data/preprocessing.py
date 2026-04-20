"""Pipeline de pré-processamento com scikit-learn ColumnTransformer.

O pipeline inteiro é serializado junto com o modelo para evitar
divergência entre treino e inferência (train/serve skew).
"""

import logging

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

logger = logging.getLogger(__name__)

# Variável alvo
TARGET = "attrition"

# Features numéricas contínuas → StandardScaler
NUMERIC_FEATURES = [
    "age",
    "daily_rate",
    "distance_from_home",
    "hourly_rate",
    "monthly_income",
    "monthly_rate",
    "num_companies_worked",
    "percent_salary_hike",
    "total_working_years",
    "training_times_last_year",
    "years_at_company",
    "years_in_current_role",
    "years_since_last_promotion",
    "years_with_curr_manager",
]

# Features ordinais (escala de satisfação 1-4, performance 1-4, etc.) → OrdinalEncoder
ORDINAL_FEATURES = [
    "education",
    "environment_satisfaction",
    "job_involvement",
    "job_level",
    "job_satisfaction",
    "relationship_satisfaction",
    "stock_option_level",
    "work_life_balance",
    "performance_rating",
]

# Features categóricas nominais → OneHotEncoder
CATEGORICAL_FEATURES = [
    "business_travel",
    "department",
    "education_field",
    "gender",
    "job_role",
    "marital_status",
    "over_time",
]

# Todas as features de entrada (sem a target)
ALL_FEATURES = NUMERIC_FEATURES + ORDINAL_FEATURES + CATEGORICAL_FEATURES


def encode_target(df: pd.DataFrame) -> pd.Series:
    """Converte a variável alvo Attrition para binário (Yes=1, No=0).

    Args:
        df: DataFrame com coluna 'attrition'.

    Returns:
        Series binária.
    """
    return df[TARGET].map({"Yes": 1, "No": 0}).astype(int)


def build_preprocessor() -> ColumnTransformer:
    """Constrói o ColumnTransformer com todas as transformações.

    Returns:
        ColumnTransformer configurado (não fitado).
    """
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "ord",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                ORDINAL_FEATURES,
            ),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, drop="if_binary"),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )

    return preprocessor


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona apenas as features de entrada (sem target, sem IDs).

    Args:
        df: DataFrame completo.

    Returns:
        DataFrame apenas com as features de entrada.
    """
    available = [f for f in ALL_FEATURES if f in df.columns]
    missing = set(ALL_FEATURES) - set(available)
    if missing:
        logger.warning("Features ausentes no DataFrame: %s", missing)
    return df[available]


def get_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Retorna os nomes das features após transformação.

    Args:
        preprocessor: ColumnTransformer já fitado.

    Returns:
        Lista de nomes das features transformadas.
    """
    return list(preprocessor.get_feature_names_out())
