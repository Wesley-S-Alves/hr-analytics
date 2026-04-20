"""Carregamento de dados: CSV → SQLite + Parquet para DuckDB.

Baixa automaticamente o dataset IBM HR Analytics se não estiver presente.
"""

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from hr_analytics.config import settings
from hr_analytics.data.database import Base, SessionLocal, engine, init_db
from hr_analytics.models.db_models import Employee

logger = logging.getLogger(__name__)


def download_dataset(dest: Path) -> Path:
    """Baixa o dataset IBM HR Analytics do Kaggle via kagglehub.

    Args:
        dest: Caminho de destino para salvar o CSV.

    Returns:
        Caminho do arquivo salvo.
    """
    import shutil

    import kagglehub

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Baixando dataset do Kaggle via kagglehub...")
    cache_path = kagglehub.dataset_download("pavansubhasht/ibm-hr-analytics-attrition-dataset")
    src_file = Path(cache_path) / "WA_Fn-UseC_-HR-Employee-Attrition.csv"
    shutil.copy2(src_file, dest)
    logger.info("Dataset salvo em %s", dest)
    return dest


# Mapeamento de colunas do CSV (CamelCase) para o ORM (snake_case)
COLUMN_MAP = {
    "Age": "age",
    "Gender": "gender",
    "MaritalStatus": "marital_status",
    "Education": "education",
    "EducationField": "education_field",
    "DistanceFromHome": "distance_from_home",
    "Department": "department",
    "JobRole": "job_role",
    "JobLevel": "job_level",
    "BusinessTravel": "business_travel",
    "OverTime": "over_time",
    "DailyRate": "daily_rate",
    "HourlyRate": "hourly_rate",
    "MonthlyRate": "monthly_rate",
    "MonthlyIncome": "monthly_income",
    "PercentSalaryHike": "percent_salary_hike",
    "StockOptionLevel": "stock_option_level",
    "TotalWorkingYears": "total_working_years",
    "YearsAtCompany": "years_at_company",
    "YearsInCurrentRole": "years_in_current_role",
    "YearsSinceLastPromotion": "years_since_last_promotion",
    "YearsWithCurrManager": "years_with_curr_manager",
    "NumCompaniesWorked": "num_companies_worked",
    "TrainingTimesLastYear": "training_times_last_year",
    "EnvironmentSatisfaction": "environment_satisfaction",
    "JobInvolvement": "job_involvement",
    "JobSatisfaction": "job_satisfaction",
    "RelationshipSatisfaction": "relationship_satisfaction",
    "WorkLifeBalance": "work_life_balance",
    "PerformanceRating": "performance_rating",
    "Attrition": "attrition",
}

# Colunas descartadas (constantes ou irrelevantes)
DROP_COLUMNS = ["EmployeeCount", "EmployeeNumber", "Over18", "StandardHours"]


def load_csv(filepath: Path | None = None) -> pd.DataFrame:
    """Carrega o CSV original do IBM HR Analytics.

    Args:
        filepath: Caminho para o CSV. Se None, busca em data/raw/.

    Returns:
        DataFrame com colunas renomeadas para snake_case.
    """
    if filepath is None:
        filepath = settings.data_raw_dir / "WA_Fn-UseC_-HR-Employee-Attrition.csv"

    if not filepath.exists():
        logger.info("CSV não encontrado localmente. Baixando do repositório público...")
        filepath = download_dataset(filepath)

    df = pd.read_csv(filepath)
    logger.info("CSV carregado: %d linhas, %d colunas", len(df), len(df.columns))

    # Remover colunas constantes/irrelevantes
    df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns])

    # Renomear para snake_case
    df = df.rename(columns=COLUMN_MAP)

    return df


def seed_database(df: pd.DataFrame) -> int:
    """Popula o SQLite com os dados do DataFrame via ORM.

    Usa init_db() para criar tabelas com schema correto (incluindo id,
    risk_score, risk_level, created_at, etc.) e insere via bulk.

    Args:
        df: DataFrame com colunas em snake_case.

    Returns:
        Número de registros inseridos.
    """
    # Dropar e recriar tabelas com schema ORM correto
    Base.metadata.drop_all(bind=engine)
    init_db()

    # Filtrar apenas colunas que existem no ORM
    orm_columns = {c.name for c in Employee.__table__.columns}
    valid_columns = [c for c in df.columns if c in orm_columns]
    records = df[valid_columns].to_dict(orient="records")

    # Inserir via session (respeita schema ORM com defaults)
    session = SessionLocal()
    try:
        for record in records:
            employee = Employee(**record)
            session.add(employee)
        session.commit()
        count = len(records)
        logger.info("Banco populado com %d colaboradores", count)
        return count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def export_parquet(df: pd.DataFrame, filename: str = "employees.parquet") -> Path:
    """Exporta DataFrame para Parquet (usado pelo DuckDB).

    Args:
        df: DataFrame a ser exportado.
        filename: Nome do arquivo Parquet.

    Returns:
        Caminho do arquivo Parquet criado.
    """
    output_path = settings.data_processed_dir / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Parquet exportado: %s (%d linhas)", output_path, len(df))
    return output_path


def load_from_db(session: Session) -> pd.DataFrame:
    """Carrega todos os colaboradores ativos do banco.

    Args:
        session: Sessão do SQLAlchemy.

    Returns:
        DataFrame com dados dos colaboradores.
    """
    query = session.query(Employee).filter(Employee.is_active.is_(True))
    df = pd.read_sql(query.statement, session.bind)
    return df
