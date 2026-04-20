"""Configurações centralizadas da aplicação via variáveis de ambiente."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações carregadas do arquivo .env com tipagem forte."""

    # Caminhos base
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_raw_dir: Path = project_root / "data" / "raw"
    data_processed_dir: Path = project_root / "data" / "processed"
    artifacts_dir: Path = project_root / "artifacts"

    # Banco de dados
    database_url: str = f"sqlite:///{project_root / 'data' / 'hr_analytics.db'}"

    # Chaves de API
    gemini_api_key: str = ""

    # MLflow
    mlflow_tracking_uri: str = f"sqlite:///{project_root / 'mlflow.db'}"
    mlflow_experiment_name: str = "hr-attrition"

    # Configurações de treino
    random_seed: int = 42
    optuna_n_trials: int = 50
    cv_folds: int = 5
    test_size: float = 0.2

    # Configurações de risco
    risk_threshold_low: float = 0.2
    risk_threshold_medium: float = 0.4
    risk_threshold_high: float = 0.7

    # LLM batch
    llm_items_per_request: int = 10
    llm_concurrency: int = 10
    llm_timeout: float = 120.0
    llm_max_retries: int = 5

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Origens permitidas via CORS — lista separada por vírgula via env var.
    # Padrão: Streamlit local + localhost. Em produção, setar via CORS_ALLOWED_ORIGINS.
    cors_allowed_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    @property
    def cors_origins_list(self) -> list[str]:
        """Retorna lista de origens permitidas parseada da env."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def get_risk_level(self, probability: float) -> str:
        """Retorna o nível de risco baseado na probabilidade de attrition."""
        if probability >= self.risk_threshold_high:
            return "crítico"
        elif probability >= self.risk_threshold_medium:
            return "alto"
        elif probability >= self.risk_threshold_low:
            return "médio"
        return "baixo"


# Instância global
settings = Settings()
