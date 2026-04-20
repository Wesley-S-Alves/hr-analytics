"""Script para popular o banco de dados com o CSV do IBM HR Analytics.

Uso: python -m scripts.seed_db
"""

import logging
import sys

from hr_analytics.data.feature_engineering import add_domain_features
from hr_analytics.data.loader import export_parquet, load_csv, seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Pipeline de seed: CSV → features → SQLite + Parquet."""
    logger.info("=== Iniciando seed do banco de dados ===")

    # 1. Carregar CSV
    try:
        df = load_csv()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # 2. Adicionar features de domínio
    df = add_domain_features(df)
    logger.info("Features de domínio adicionadas. Shape: %s", df.shape)

    # 3. Popular SQLite
    count = seed_database(df)
    logger.info("SQLite populado com %d registros", count)

    # 4. Exportar Parquet para DuckDB
    parquet_path = export_parquet(df)
    logger.info("Parquet exportado: %s", parquet_path)

    logger.info("=== Seed concluído com sucesso ===")


if __name__ == "__main__":
    main()
