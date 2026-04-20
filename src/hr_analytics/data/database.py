"""Configuração do banco de dados SQLAlchemy 2.0."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from hr_analytics.config import settings


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""

    pass


engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite precisa disso
)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Session:
    """Retorna uma sessão do banco de dados."""
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise


def init_db() -> None:
    """Cria todas as tabelas no banco de dados."""
    Base.metadata.create_all(bind=engine)
