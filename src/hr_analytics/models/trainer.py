"""Pipeline de treino com cross-validation, Optuna e MLflow.

Treina 4 modelos (LogReg, RF, XGBoost, LightGBM), otimiza hiperparâmetros
via Optuna, registra tudo no MLflow e seleciona o melhor modelo.
"""

import logging
from typing import Any

import mlflow
import numpy as np
import optuna
from imblearn.over_sampling import SMOTE
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

from hr_analytics.config import settings

logger = logging.getLogger(__name__)

# Suprimir logs verbosos do Optuna e LightGBM
optuna.logging.set_verbosity(optuna.logging.WARNING)


def _get_search_space(model_name: str, trial: optuna.Trial) -> dict[str, Any]:
    """Define o espaço de busca de hiperparâmetros por modelo.

    Args:
        model_name: Nome do modelo.
        trial: Trial do Optuna.

    Returns:
        Dicionário de hiperparâmetros sugeridos.
    """
    if model_name == "logistic_regression":
        return {
            "C": trial.suggest_float("C", 0.01, 10.0, log=True),
            "solver": "lbfgs",
            "max_iter": 1000,
            "class_weight": "balanced",
            "random_state": settings.random_seed,
        }

    elif model_name == "random_forest":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 15),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
            "class_weight": "balanced_subsample",
            "random_state": settings.random_seed,
            "n_jobs": -1,
        }

    elif model_name == "xgboost":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 2.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 2.0),
            "eval_metric": "aucpr",
            "random_state": settings.random_seed,
            "n_jobs": -1,
        }

    elif model_name == "lightgbm":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "is_unbalance": True,
            "random_state": settings.random_seed,
            "verbose": -1,
            "n_jobs": -1,
        }

    raise ValueError(f"Modelo desconhecido: {model_name}")


def _create_model(model_name: str, params: dict[str, Any]) -> Any:
    """Instancia o modelo com os hiperparâmetros dados.

    Args:
        model_name: Nome do modelo.
        params: Hiperparâmetros.

    Returns:
        Instância do modelo.
    """
    models = {
        "logistic_regression": LogisticRegression,
        "random_forest": RandomForestClassifier,
        "xgboost": XGBClassifier,
        "lightgbm": LGBMClassifier,
    }
    return models[model_name](**params)


def find_optimal_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Encontra o threshold ótimo via Youden's J statistic.

    J = Sensibilidade + Especificidade - 1
    Maximiza a separação entre TPR e FPR.

    Args:
        y_true: Labels reais.
        y_prob: Probabilidades preditas.

    Returns:
        Threshold ótimo.
    """
    from sklearn.metrics import roc_curve

    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    return float(thresholds[best_idx])


def cross_validate_model(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    n_folds: int = 5,
    use_smote: bool = True,
) -> dict[str, float]:
    """Cross-validation estratificada com SMOTE por fold.

    SMOTE é aplicado DENTRO de cada fold para evitar data leakage.

    Args:
        model: Modelo sklearn-compatible.
        X: Features transformadas.
        y: Labels binárias.
        n_folds: Número de folds.
        use_smote: Se True, aplica SMOTE por fold.

    Returns:
        Dicionário com métricas médias.
    """
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=settings.random_seed)

    metrics = {
        "roc_auc": [],
        "pr_auc": [],
        "precision": [],
        "recall": [],
        "f1": [],
    }

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        if use_smote:
            smote = SMOTE(random_state=settings.random_seed)
            X_train, y_train = smote.fit_resample(X_train, y_train)

        model_clone = _clone_model(model)
        model_clone.fit(X_train, y_train)

        y_prob = model_clone.predict_proba(X_val)[:, 1]
        threshold = find_optimal_threshold(y_val, y_prob)
        y_pred = (y_prob >= threshold).astype(int)

        metrics["roc_auc"].append(roc_auc_score(y_val, y_prob))
        metrics["pr_auc"].append(average_precision_score(y_val, y_prob))
        metrics["precision"].append(precision_score(y_val, y_pred, zero_division=0))
        metrics["recall"].append(recall_score(y_val, y_pred, zero_division=0))
        metrics["f1"].append(f1_score(y_val, y_pred, zero_division=0))

    return {k: float(np.mean(v)) for k, v in metrics.items()}


def _clone_model(model: Any) -> Any:
    """Cria uma cópia do modelo com os mesmos hiperparâmetros."""
    from sklearn.base import clone

    return clone(model)


def calibrate_model(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    method: str = "sigmoid",
) -> CalibratedClassifierCV:
    """Aplica Platt Scaling (sigmoid) ou isotonic regression ao modelo.

    Platt Scaling ajusta as probabilidades do modelo para que sejam
    bem calibradas — P(Y=1|predict_proba=0.7) ≈ 70% de fato.

    Modelos tree-based (XGBoost, LightGBM, RF) se beneficiam bastante
    pois tendem a ter probabilidades mal calibradas.

    Args:
        model: Modelo treinado (já fitado).
        X: Features para calibração.
        y: Labels binárias.
        method: "sigmoid" (Platt Scaling) ou "isotonic".

    Returns:
        Modelo calibrado.
    """
    calibrated = CalibratedClassifierCV(
        estimator=model,
        method=method,
        cv=5,
    )
    calibrated.fit(X, y)
    return calibrated


def optimize_model(
    model_name: str,
    X: np.ndarray,
    y: np.ndarray,
    n_trials: int | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    """Otimiza hiperparâmetros de um modelo via Optuna.

    Cada trial faz cross-validation completa e é registrada no MLflow
    como nested run.

    Args:
        model_name: Nome do modelo.
        X: Features transformadas.
        y: Labels binárias.
        n_trials: Número de trials (padrão: settings.optuna_n_trials).

    Returns:
        Tupla (melhores_params, melhores_métricas).
    """
    if n_trials is None:
        n_trials = settings.optuna_n_trials

    def objective(trial: optuna.Trial) -> float:
        params = _get_search_space(model_name, trial)
        model = _create_model(model_name, params)

        with mlflow.start_run(nested=True, run_name=f"{model_name}_trial_{trial.number}"):
            metrics = cross_validate_model(model, X, y, n_folds=settings.cv_folds)
            mlflow.log_params(params)
            mlflow.log_metrics(metrics)

        return metrics["roc_auc"]

    study = optuna.create_study(
        direction="maximize",
        study_name=f"{model_name}-tuning",
        sampler=optuna.samplers.TPESampler(seed=settings.random_seed),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    # Melhores hiperparâmetros e métricas
    best_params = _get_search_space(model_name, study.best_trial)
    best_model = _create_model(model_name, best_params)
    best_metrics = cross_validate_model(best_model, X, y, n_folds=settings.cv_folds)

    logger.info(
        "[%s] Melhor ROC-AUC: %.4f (trial %d de %d)",
        model_name,
        study.best_value,
        study.best_trial.number,
        n_trials,
    )

    return best_params, best_metrics


def train_all_models(
    X: np.ndarray,
    y: np.ndarray,
    model_names: list[str] | None = None,
) -> dict[str, dict]:
    """Treina e otimiza todos os modelos, registrando no MLflow.

    Args:
        X: Features transformadas.
        y: Labels binárias.
        model_names: Lista de modelos a treinar. Se None, treina todos.

    Returns:
        Dicionário {model_name: {"params": ..., "metrics": ..., "model": ...}}.
    """
    if model_names is None:
        model_names = ["logistic_regression", "random_forest", "xgboost", "lightgbm"]

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    results = {}

    for model_name in model_names:
        logger.info("=== Otimizando %s ===", model_name)

        with mlflow.start_run(run_name=model_name):
            best_params, best_metrics = optimize_model(model_name, X, y)

            # Treinar modelo final com todos os dados de treino + SMOTE
            smote = SMOTE(random_state=settings.random_seed)
            X_resampled, y_resampled = smote.fit_resample(X, y)

            final_model = _create_model(model_name, best_params)
            final_model.fit(X_resampled, y_resampled)

            # Platt Scaling (calibração de probabilidades)
            # Usa sigmoid (Platt) para modelos de árvore, que tendem a ter
            # probabilidades mal calibradas
            calibrated_model = calibrate_model(final_model, X, y)

            # Brier Score: mede qualidade da calibração (menor = melhor)
            y_prob_raw = final_model.predict_proba(X)[:, 1]
            y_prob_cal = calibrated_model.predict_proba(X)[:, 1]
            brier_raw = brier_score_loss(y, y_prob_raw)
            brier_cal = brier_score_loss(y, y_prob_cal)
            logger.info(
                "[%s] Brier Score: raw=%.4f → calibrado=%.4f",
                model_name,
                brier_raw,
                brier_cal,
            )

            # Registrar no MLflow
            mlflow.log_params(best_params)
            mlflow.log_metrics({f"final_{k}": v for k, v in best_metrics.items()})
            mlflow.log_metric("brier_score_raw", brier_raw)
            mlflow.log_metric("brier_score_calibrated", brier_cal)
            mlflow.sklearn.log_model(calibrated_model, artifact_path="model")

            results[model_name] = {
                "params": best_params,
                "metrics": best_metrics,
                "model": calibrated_model,  # Usar modelo calibrado
                "model_raw": final_model,  # Manter raw para SHAP
            }

    # Selecionar melhor modelo individual
    best_name = max(results, key=lambda k: results[k]["metrics"]["roc_auc"])
    logger.info(
        "=== Melhor modelo individual: %s (ROC-AUC: %.4f) ===",
        best_name,
        results[best_name]["metrics"]["roc_auc"],
    )

    return results
