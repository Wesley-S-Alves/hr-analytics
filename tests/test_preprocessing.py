"""Testes de pré-processamento de dados."""

import numpy as np

from hr_analytics.data.preprocessing import (
    ALL_FEATURES,
    build_preprocessor,
    encode_target,
    prepare_features,
)


def test_encode_target_converts_yes_no_to_binary(sample_df):
    """Attrition Yes→1, No→0."""
    y = encode_target(sample_df)
    assert set(y.unique()).issubset({0, 1})
    assert y.dtype == int


def test_build_preprocessor_transforms_all_features(sample_df):
    """Preprocessor transforma todas as features sem erro."""
    preprocessor = build_preprocessor()
    X_raw = prepare_features(sample_df)
    X = preprocessor.fit_transform(X_raw)

    assert X.shape[0] == len(sample_df)
    assert X.shape[1] > 0
    assert not np.any(np.isnan(X))


def test_prepare_features_selects_correct_columns(sample_df):
    """prepare_features seleciona apenas features válidas."""
    X = prepare_features(sample_df)
    for col in X.columns:
        assert col in ALL_FEATURES


def test_preprocessor_output_has_feature_names(sample_df):
    """Preprocessor retorna nomes de features."""
    preprocessor = build_preprocessor()
    X_raw = prepare_features(sample_df)
    preprocessor.fit_transform(X_raw)
    names = list(preprocessor.get_feature_names_out())
    assert len(names) > 0
    assert all(isinstance(n, str) for n in names)
