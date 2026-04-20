"""Testes de feature engineering."""

import numpy as np
import pandas as pd

from hr_analytics.data.feature_engineering import DERIVED_FEATURES, add_domain_features


def test_add_domain_features_creates_all_features(sample_df):
    """Todas as features derivadas são criadas."""
    df = add_domain_features(sample_df)
    for feat in DERIVED_FEATURES:
        assert feat in df.columns, f"Feature {feat} não encontrada"


def test_tenure_ratio_handles_zero_division(sample_df):
    """tenure_ratio não gera NaN/Inf quando total_working_years=0."""
    sample_df.loc[0, "total_working_years"] = 0
    df = add_domain_features(sample_df)
    assert np.isfinite(df["tenure_ratio"].iloc[0])
    assert df["tenure_ratio"].iloc[0] == 0.0


def test_career_stagnation_handles_zero_division(sample_df):
    """career_stagnation não gera NaN/Inf quando years_at_company=0."""
    sample_df.loc[0, "years_at_company"] = 0
    df = add_domain_features(sample_df)
    assert np.isfinite(df["career_stagnation"].iloc[0])


def test_satisfaction_index_range(sample_df):
    """satisfaction_index está no range esperado (1-4)."""
    df = add_domain_features(sample_df)
    assert df["satisfaction_index"].min() >= 1.0
    assert df["satisfaction_index"].max() <= 4.0


def test_income_annual_calculation(sample_df):
    """income_annual = monthly_income * 12."""
    df = add_domain_features(sample_df)
    expected = sample_df["monthly_income"] * 12
    pd.testing.assert_series_equal(df["income_annual"], expected, check_names=False)


def test_original_columns_preserved(sample_df):
    """Features originais não são removidas."""
    original_cols = set(sample_df.columns)
    df = add_domain_features(sample_df)
    assert original_cols.issubset(set(df.columns))
