"""Testes do monitoramento de drift (PSI)."""

import numpy as np

from hr_analytics.monitoring.drift import DriftReport, calculate_psi


def test_psi_identical_distributions():
    """PSI de distribuições idênticas deve ser ~0."""
    data = np.random.normal(0, 1, 1000)
    psi = calculate_psi(data, data)
    assert psi < 0.01


def test_psi_slightly_different_distributions():
    """PSI de distribuições levemente diferentes deve ser baixo."""
    expected = np.random.normal(0, 1, 1000)
    actual = np.random.normal(0.1, 1, 1000)
    psi = calculate_psi(expected, actual)
    assert psi < 0.2  # Não deve indicar drift significativo


def test_psi_very_different_distributions():
    """PSI de distribuições muito diferentes deve ser alto."""
    expected = np.random.normal(0, 1, 1000)
    actual = np.random.normal(5, 1, 1000)
    psi = calculate_psi(expected, actual)
    assert psi > 0.2  # Deve indicar drift significativo


def test_psi_non_negative():
    """PSI deve ser sempre >= 0."""
    for _ in range(10):
        expected = np.random.uniform(0, 10, 500)
        actual = np.random.uniform(0, 10, 500)
        psi = calculate_psi(expected, actual)
        assert psi >= 0


def test_drift_report_classification():
    """DriftReport classifica features corretamente."""
    report = DriftReport(
        feature_psi={
            "feature_ok": 0.05,
            "feature_warning": 0.15,
            "feature_alert": 0.30,
        }
    )
    report.classify_features()

    assert "feature_alert" in report.features_drifted
    assert "feature_warning" in report.features_warning
    assert "feature_ok" not in report.features_drifted
    assert "feature_ok" not in report.features_warning
    assert report.overall_status == "alert"


def test_drift_report_ok_status():
    """DriftReport retorna 'ok' quando não há drift."""
    report = DriftReport(feature_psi={"f1": 0.01, "f2": 0.05, "f3": 0.08})
    report.classify_features()

    assert report.overall_status == "ok"
    assert len(report.features_drifted) == 0
    assert len(report.features_warning) == 0
