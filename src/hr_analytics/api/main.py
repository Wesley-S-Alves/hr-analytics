"""FastAPI application factory com lifespan management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hr_analytics.api.routes import agent, employees, explain, insights, monitoring, predict, users
from hr_analytics.config import settings
from hr_analytics.data.database import init_db
from hr_analytics.inference.predictor import model_service
from hr_analytics.logging_config import configure_logging
from hr_analytics.monitoring.observability import tracker
from hr_analytics.tracing import setup_genai_tracing

# Configura logging uma vez no startup do processo (lê LOG_LEVEL / LOG_FORMAT do .env)
configure_logging()

# Ativa tracing de GenAI no MLflow (LangChain + Gemini autolog)
setup_genai_tracing()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação.

    Startup: inicializa banco, carrega modelo.
    Shutdown: flush de métricas de observabilidade.
    """
    # Startup
    logger.info("Inicializando aplicação...")
    init_db()
    model_service.load()
    logger.info("Aplicação pronta")

    yield

    # Shutdown
    logger.info("Encerrando aplicação...")
    tracker.flush()
    logger.info("Aplicação encerrada")


def create_app() -> FastAPI:
    """Cria e configura a aplicação FastAPI."""
    app = FastAPI(
        title="HR Analytics API",
        description="API de People Analytics — predição de attrition, insights com LLM e agente conversacional",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS — restrito por env var CORS_ALLOWED_ORIGINS (padrão: localhost:8501).
    # Para produção, setar CORS_ALLOWED_ORIGINS=https://app.meudominio.com
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Registrar rotas
    prefix = "/api/v1"
    app.include_router(predict.router, prefix=prefix)
    app.include_router(employees.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(explain.router, prefix=prefix)
    app.include_router(insights.router, prefix=prefix)
    app.include_router(monitoring.router, prefix=prefix)
    app.include_router(agent.router, prefix=prefix)

    @app.get("/api/v1/health", tags=["Health"])
    def health_check():
        """Health check profundo: DB, modelo e dependências."""
        from pathlib import Path

        from sqlalchemy import text

        from hr_analytics.data.database import get_session
        from hr_analytics.inference.schemas import HealthResponse

        # 1. Conectividade DB — SELECT 1
        database_ok = False
        try:
            session = get_session()
            session.execute(text("SELECT 1"))
            session.close()
            database_ok = True
        except Exception as e:
            logger.warning("Health: DB falhou: %s", e)

        # 2. Modelo carregado + arquivo .joblib existe
        model_loaded = model_service.is_loaded
        model_file_ok = False
        try:
            artifacts = Path(settings.artifacts_dir) / "models"
            model_file_ok = artifacts.exists() and any(artifacts.glob("*.joblib"))
        except Exception:
            pass

        # 3. Status agregado
        critical_ok = database_ok and model_loaded and model_file_ok
        status = "ok" if critical_ok else "degraded"

        return HealthResponse(
            status=status,
            model_loaded=model_loaded,
            model_name=model_service.model_name,
            database_ok=database_ok,
        )

    return app


# Instância usada pelo uvicorn
app = create_app()
