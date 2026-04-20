"""Instrumentação de GenAI no MLflow — traces de chamadas LangChain + Gemini.

Ativa autologging do MLflow para:
- `mlflow.langchain.autolog()`: captura cada agent.invoke() com tool calls,
  tokens e latência — aparece na aba "Traces" do MLflow.
- `mlflow.gemini.autolog()`: captura chamadas diretas ao Gemini (client.py
  e batch.py) — mesma aba.

A configuração é idempotente (safe para múltiplas chamadas) e silencia
erros caso um dos backends não esteja disponível na versão do MLflow.

Uso:
    from hr_analytics.tracing import setup_genai_tracing
    setup_genai_tracing()  # no startup da API ou no orchestrator
"""

import logging
import os

logger = logging.getLogger(__name__)

_TRACING_INITIALIZED = False
GENAI_EXPERIMENT_NAME = "hr-genai-traces"


def setup_genai_tracing(experiment_name: str | None = None) -> bool:
    """Habilita autologging de GenAI no MLflow.

    Args:
        experiment_name: nome do experimento MLflow onde os traces serão
            registrados. Padrão: "hr-genai-traces".

    Returns:
        True se pelo menos um autolog foi ativado com sucesso.
    """
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return True

    try:
        import mlflow
    except ImportError:
        logger.warning("MLflow não instalado — tracing de GenAI desativado")
        return False

    # Tracking URI — usa a mesma config do treino (settings.mlflow_tracking_uri)
    try:
        from hr_analytics.config import settings

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    except Exception as e:
        logger.warning("Falha ao configurar tracking URI: %s", e)

    # Experiment dedicado pra traces de GenAI (separa de "hr-attrition")
    exp_name = experiment_name or os.getenv("MLFLOW_GENAI_EXPERIMENT", GENAI_EXPERIMENT_NAME)
    try:
        mlflow.set_experiment(exp_name)
    except Exception as e:
        logger.warning("Falha ao setar experimento '%s': %s", exp_name, e)

    enabled: list[str] = []

    # LangChain autolog — agente ReAct (process_message) e todas as tool calls
    try:
        mlflow.langchain.autolog(disable=False)
        enabled.append("langchain")
    except Exception as e:
        logger.warning("Falha ao ativar mlflow.langchain.autolog: %s", e)

    # Gemini autolog — chamadas diretas via google-generativeai (client.py, batch.py)
    try:
        mlflow.gemini.autolog(disable=False)
        enabled.append("gemini")
    except Exception as e:
        logger.warning("Falha ao ativar mlflow.gemini.autolog: %s", e)

    if enabled:
        _TRACING_INITIALIZED = True
        logger.info(
            "MLflow tracing ativo: %s | experiment=%s | URI=%s",
            ", ".join(enabled),
            exp_name,
            mlflow.get_tracking_uri(),
        )
        return True

    logger.warning("Nenhum autolog de GenAI foi ativado")
    return False
