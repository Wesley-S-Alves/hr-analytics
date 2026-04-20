"""Modelos ORM do SQLAlchemy para o banco de dados."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_analytics.data.database import Base


class Employee(Base):
    """Modelo de colaborador com dados do dataset + risco calculado."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dados demográficos
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    marital_status: Mapped[str] = mapped_column(String(20), nullable=False)
    education: Mapped[int] = mapped_column(Integer, nullable=False)
    education_field: Mapped[str] = mapped_column(String(50), nullable=False)
    distance_from_home: Mapped[int] = mapped_column(Integer, nullable=False)

    # Dados profissionais
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    job_role: Mapped[str] = mapped_column(String(50), nullable=False)
    job_level: Mapped[int] = mapped_column(Integer, nullable=False)
    business_travel: Mapped[str] = mapped_column(String(30), nullable=False)
    over_time: Mapped[str] = mapped_column(String(5), nullable=False)

    # Financeiro
    daily_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    hourly_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_income: Mapped[int] = mapped_column(Integer, nullable=False)
    percent_salary_hike: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_option_level: Mapped[int] = mapped_column(Integer, nullable=False)

    # Experiência
    total_working_years: Mapped[int] = mapped_column(Integer, nullable=False)
    years_at_company: Mapped[int] = mapped_column(Integer, nullable=False)
    years_in_current_role: Mapped[int] = mapped_column(Integer, nullable=False)
    years_since_last_promotion: Mapped[int] = mapped_column(Integer, nullable=False)
    years_with_curr_manager: Mapped[int] = mapped_column(Integer, nullable=False)
    num_companies_worked: Mapped[int] = mapped_column(Integer, nullable=False)
    training_times_last_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Satisfação e performance
    environment_satisfaction: Mapped[int] = mapped_column(Integer, nullable=False)
    job_involvement: Mapped[int] = mapped_column(Integer, nullable=False)
    job_satisfaction: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_satisfaction: Mapped[int] = mapped_column(Integer, nullable=False)
    work_life_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_rating: Mapped[int] = mapped_column(Integer, nullable=False)

    # Variável alvo (histórico)
    attrition: Mapped[str] = mapped_column(String(5), nullable=True)

    # Campos calculados pelo modelo
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Metadados
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class User(Base):
    """Modelo de usuário do sistema."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
