"""Dependências compartilhadas da API FastAPI."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from hr_analytics.data.database import SessionLocal
from hr_analytics.inference.predictor import model_service


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão de banco de dados por requisição."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_model_service():
    """Fornece o serviço de modelo carregado."""
    if not model_service.is_loaded:
        model_service.load()
    return model_service
