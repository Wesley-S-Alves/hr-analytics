"""Roda predição para TODOS os colaboradores no banco e atualiza risk_score/risk_level.

Uso: PYTHONPATH=src python -m scripts.predict_all
"""

import logging
import sys

import pandas as pd

from hr_analytics.config import settings
from hr_analytics.data.database import SessionLocal
from hr_analytics.data.feature_engineering import add_domain_features
from hr_analytics.data.preprocessing import prepare_features
from hr_analytics.inference.predictor import model_service
from hr_analytics.models.db_models import Employee

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Prediz risco para todos os colaboradores ativos."""
    logger.info("=== Rodando predição para todos os colaboradores ===")

    # Carregar modelo
    model_service.load()
    if not model_service.is_loaded:
        logger.error("Modelo não carregado. Execute 'make train' primeiro.")
        sys.exit(1)

    session = SessionLocal()
    try:
        employees = session.query(Employee).filter(Employee.is_active.is_(True)).all()
        logger.info("Total de colaboradores: %d", len(employees))

        updated = 0
        for emp in employees:
            # Converter para DataFrame
            data = {col.name: [getattr(emp, col.name)] for col in Employee.__table__.columns
                    if col.name not in ("id", "risk_score", "risk_level", "created_at", "updated_at", "is_active")}
            df = pd.DataFrame(data)

            try:
                # Adicionar features de domínio e predizer
                df_feat = add_domain_features(df)
                X_raw = prepare_features(df_feat)
                X = model_service._preprocessor.transform(X_raw)
                prob = float(model_service._model.predict_proba(X)[:, 1][0])
                risk_level = settings.get_risk_level(prob)

                emp.risk_score = round(prob, 4)
                emp.risk_level = risk_level
                updated += 1
            except Exception as e:
                logger.warning("Erro no colaborador %d: %s", emp.id, e)
                continue

            if updated % 200 == 0:
                logger.info("  Progresso: %d/%d", updated, len(employees))
                session.commit()

        session.commit()
        logger.info("=== Predição concluída: %d/%d colaboradores atualizados ===", updated, len(employees))

        # Resumo por nível de risco
        for level in ["crítico", "alto", "médio", "baixo"]:
            count = session.query(Employee).filter(Employee.risk_level == level).count()
            logger.info("  %s: %d colaboradores", level, count)

    finally:
        session.close()


if __name__ == "__main__":
    main()
