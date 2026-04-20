"""Script principal de treino: EDA → Features → Treino → SHAP → Salvar.

Uso: python -m scripts.train
"""

import logging
import sys
import warnings

import numpy as np

# Suprimir warnings repetitivos do LightGBM/sklearn
warnings.filterwarnings("ignore", message="X does not have valid feature names")

from hr_analytics.config import settings
from hr_analytics.data.feature_engineering import add_domain_features
from hr_analytics.data.loader import load_csv, export_parquet
from hr_analytics.data.preprocessing import (
    ALL_FEATURES,
    build_preprocessor,
    encode_target,
    get_feature_names,
    prepare_features,
)
from hr_analytics.models.explainer import (
    compute_shap_values,
    create_explainer,
    global_feature_importance,
    save_shap_bar_plot,
    save_shap_summary_plot,
    save_shap_waterfall_plot,
)
from hr_analytics.models.registry import save_model, save_reference_distributions
from hr_analytics.models.trainer import find_optimal_threshold, train_all_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Pipeline completo de treino."""
    logger.info("=" * 60)
    logger.info("PIPELINE DE TREINO — People Analytics")
    logger.info("=" * 60)

    # 1. Carregar dados
    logger.info("--- Fase 1: Carregamento de dados ---")
    try:
        df = load_csv()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # 2. Feature engineering
    logger.info("--- Fase 2: Feature engineering ---")
    df = add_domain_features(df)

    # 3. Preparar features e target
    logger.info("--- Fase 3: Preparação de features ---")
    X_raw = prepare_features(df)
    y = encode_target(df)

    logger.info("Shape X: %s, distribuição y: %s",
                X_raw.shape, dict(zip(*np.unique(y, return_counts=True))))

    # 4. Preprocessamento
    logger.info("--- Fase 4: Preprocessamento ---")
    preprocessor = build_preprocessor()
    X = preprocessor.fit_transform(X_raw)
    feature_names = get_feature_names(preprocessor)

    logger.info("Features após transformação: %d", X.shape[1])

    # 5. Salvar distribuições de referência para monitoramento de drift
    logger.info("--- Fase 5: Salvando distribuições de referência ---")
    ref_distributions = {name: X[:, i] for i, name in enumerate(feature_names)}
    save_reference_distributions(ref_distributions)

    # 6. Treinar modelos
    logger.info("--- Fase 6: Treino de modelos (Optuna + MLflow) ---")
    results = train_all_models(X, y.values)

    # 7. Comparação de modelos
    logger.info("\n--- Comparação de modelos ---")
    for name, res in sorted(results.items(), key=lambda x: x[1]["metrics"]["roc_auc"], reverse=True):
        m = res["metrics"]
        logger.info(
            "  %-25s ROC-AUC=%.4f  PR-AUC=%.4f  F1=%.4f  Precision=%.4f  Recall=%.4f",
            name, m["roc_auc"], m["pr_auc"], m["f1"], m["precision"], m["recall"],
        )

    # Salvar comparação em JSON para o EDA notebook
    import json
    metrics_dir = settings.artifacts_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    comparison = {name: res["metrics"] for name, res in results.items()}
    with open(metrics_dir / "model_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    # 8. Selecionar melhor modelo pelo ROC-AUC
    best_name = max(results, key=lambda k: results[k]["metrics"]["roc_auc"])
    best_model = results[best_name]["model"]
    best_metrics = results[best_name]["metrics"]
    best_params = results[best_name]["params"]

    logger.info(
        "=== Modelo final escolhido: %s (ROC-AUC=%.4f) ===",
        best_name, best_metrics["roc_auc"],
    )

    # 9. Threshold ótimo via Youden's J
    y_prob = best_model.predict_proba(X)[:, 1]
    threshold = find_optimal_threshold(y.values, y_prob)
    logger.info("Threshold ótimo (Youden's J): %.4f", threshold)

    # 10. SHAP — usa model_raw (sem calibração) porque CalibratedClassifierCV
    # não é compatível com TreeExplainer do SHAP
    logger.info("--- Fase 10: Explicabilidade SHAP ---")
    shap_model = results[best_name].get("model_raw", best_model)
    explainer = create_explainer(shap_model, X)
    shap_values = compute_shap_values(explainer, X)
    importance_df = global_feature_importance(shap_values, feature_names)
    logger.info("Top-10 features:\n%s", importance_df.head(10).to_string(index=False))
    importance_df.to_csv(metrics_dir / "feature_importance.csv", index=False)

    # Gerar e salvar plots SHAP
    logger.info("--- Fase 10b: Salvando plots SHAP ---")
    save_shap_summary_plot(shap_values, X, feature_names)
    save_shap_bar_plot(shap_values, feature_names)
    # Waterfall para o colaborador com maior risco previsto
    y_prob_all = best_model.predict_proba(X)[:, 1]
    highest_risk_idx = int(np.argmax(y_prob_all))
    save_shap_waterfall_plot(
        explainer, X[highest_risk_idx], feature_names, employee_id=highest_risk_idx,
    )

    # 11. Salvar modelo final
    logger.info("--- Fase 11: Salvando artefatos ---")
    model_dir = save_model(
        model=best_model,
        preprocessor=preprocessor,
        model_name=best_name,
        metrics=best_metrics,
        feature_names=feature_names,
        threshold=threshold,
        params=best_params,
    )

    # Exportar Parquet atualizado
    export_parquet(df)

    logger.info("=" * 60)
    logger.info("TREINO CONCLUÍDO")
    logger.info("Modelo final: %s", best_name)
    logger.info("ROC-AUC: %.4f  |  Threshold: %.4f", best_metrics["roc_auc"], threshold)
    logger.info("Artefatos: %s", model_dir)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
