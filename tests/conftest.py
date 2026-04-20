"""Fixtures compartilhadas para testes."""

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hr_analytics.data.database import Base
from hr_analytics.models.db_models import Employee


@pytest.fixture
def sample_df():
    """DataFrame de exemplo com 50 linhas simulando o dataset IBM HR."""
    np.random.seed(42)
    n = 50
    return pd.DataFrame(
        {
            "age": np.random.randint(18, 60, n),
            "gender": np.random.choice(["Male", "Female"], n),
            "marital_status": np.random.choice(["Single", "Married", "Divorced"], n),
            "education": np.random.randint(1, 6, n),
            "education_field": np.random.choice(["Life Sciences", "Medical", "Technical Degree"], n),
            "distance_from_home": np.random.randint(1, 30, n),
            "department": np.random.choice(["Sales", "Research & Development", "Human Resources"], n),
            "job_role": np.random.choice(["Sales Executive", "Research Scientist", "Manager"], n),
            "job_level": np.random.randint(1, 6, n),
            "business_travel": np.random.choice(["Travel_Rarely", "Travel_Frequently", "Non-Travel"], n),
            "over_time": np.random.choice(["Yes", "No"], n),
            "daily_rate": np.random.randint(100, 1500, n),
            "hourly_rate": np.random.randint(30, 100, n),
            "monthly_rate": np.random.randint(2000, 25000, n),
            "monthly_income": np.random.randint(1000, 20000, n),
            "percent_salary_hike": np.random.randint(11, 25, n),
            "stock_option_level": np.random.randint(0, 4, n),
            "total_working_years": np.random.randint(0, 40, n),
            "years_at_company": np.random.randint(0, 30, n),
            "years_in_current_role": np.random.randint(0, 18, n),
            "years_since_last_promotion": np.random.randint(0, 15, n),
            "years_with_curr_manager": np.random.randint(0, 17, n),
            "num_companies_worked": np.random.randint(0, 10, n),
            "training_times_last_year": np.random.randint(0, 7, n),
            "environment_satisfaction": np.random.randint(1, 5, n),
            "job_involvement": np.random.randint(1, 5, n),
            "job_satisfaction": np.random.randint(1, 5, n),
            "relationship_satisfaction": np.random.randint(1, 5, n),
            "work_life_balance": np.random.randint(1, 5, n),
            "performance_rating": np.random.choice([3, 4], n),
            "attrition": np.random.choice(["Yes", "No"], n, p=[0.16, 0.84]),
        }
    )


@pytest.fixture
def test_db_session():
    """Banco SQLite em memória com tabelas criadas e sessão aberta."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()


# Alias para compat com testes antigos
@pytest.fixture
def test_db(test_db_session):
    """Alias deprecated — use `test_db_session`."""
    return test_db_session


@pytest.fixture
def sample_employee():
    """Retorna um Employee ORM de exemplo (não persistido)."""
    return Employee(
        id=1,
        age=35,
        gender="Male",
        marital_status="Married",
        education=3,
        education_field="Life Sciences",
        distance_from_home=5,
        department="Research & Development",
        job_role="Research Scientist",
        job_level=2,
        business_travel="Travel_Rarely",
        over_time="No",
        daily_rate=800,
        hourly_rate=65,
        monthly_rate=14000,
        monthly_income=5000,
        percent_salary_hike=15,
        stock_option_level=1,
        total_working_years=10,
        years_at_company=5,
        years_in_current_role=3,
        years_since_last_promotion=1,
        years_with_curr_manager=3,
        num_companies_worked=2,
        training_times_last_year=3,
        environment_satisfaction=3,
        job_involvement=3,
        job_satisfaction=3,
        relationship_satisfaction=3,
        work_life_balance=3,
        performance_rating=3,
        attrition="No",
        is_active=True,
    )


@pytest.fixture
def populated_db(test_db_session, sample_employee):
    """DB com 3 colaboradores de diferentes perfis."""
    employees = [
        sample_employee,
        Employee(
            id=2,
            age=28,
            gender="Female",
            marital_status="Single",
            education=4,
            education_field="Medical",
            distance_from_home=12,
            department="Sales",
            job_role="Sales Executive",
            job_level=3,
            business_travel="Travel_Frequently",
            over_time="Yes",
            daily_rate=1200,
            hourly_rate=80,
            monthly_rate=20000,
            monthly_income=8000,
            percent_salary_hike=20,
            stock_option_level=2,
            total_working_years=6,
            years_at_company=2,
            years_in_current_role=1,
            years_since_last_promotion=0,
            years_with_curr_manager=1,
            num_companies_worked=3,
            training_times_last_year=5,
            environment_satisfaction=2,
            job_involvement=4,
            job_satisfaction=2,
            relationship_satisfaction=3,
            work_life_balance=2,
            performance_rating=4,
            attrition="Yes",
            is_active=True,
            risk_score=0.82,
            risk_level="crítico",
        ),
        Employee(
            id=3,
            age=45,
            gender="Male",
            marital_status="Married",
            education=5,
            education_field="Technical Degree",
            distance_from_home=3,
            department="Human Resources",
            job_role="Manager",
            job_level=4,
            business_travel="Non-Travel",
            over_time="No",
            daily_rate=1500,
            hourly_rate=95,
            monthly_rate=25000,
            monthly_income=15000,
            percent_salary_hike=12,
            stock_option_level=3,
            total_working_years=20,
            years_at_company=15,
            years_in_current_role=8,
            years_since_last_promotion=5,
            years_with_curr_manager=10,
            num_companies_worked=1,
            training_times_last_year=2,
            environment_satisfaction=4,
            job_involvement=3,
            job_satisfaction=4,
            relationship_satisfaction=4,
            work_life_balance=4,
            performance_rating=3,
            attrition="No",
            is_active=True,
            risk_score=0.12,
            risk_level="baixo",
        ),
    ]
    for e in employees:
        test_db_session.add(e)
    test_db_session.commit()
    return test_db_session


@pytest.fixture
def mock_model_service():
    """Mock do ModelService retornando predição fixa."""
    service = MagicMock()
    service.is_loaded = True
    service.model_name = "xgboost_test"
    service.threshold = 0.45
    service.predict_single.return_value = {
        "attrition_probability": 0.62,
        "risk_level": "alto",
        "threshold": 0.45,
        "top_factors": [
            {"feature": "cat__over_time_Yes", "shap_value": 0.35, "impact": "aumenta_risco", "magnitude": 0.35},
            {"feature": "num__monthly_income", "shap_value": -0.22, "impact": "diminui_risco", "magnitude": 0.22},
        ],
    }
    return service


@pytest.fixture
def api_client(populated_db, mock_model_service):
    """TestClient da FastAPI com DB e modelo mockados via dependency_overrides."""
    from hr_analytics.api.dependencies import get_db, get_model_service
    from hr_analytics.api.main import create_app

    app = create_app()

    def _override_db():
        yield populated_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_model_service] = lambda: mock_model_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
