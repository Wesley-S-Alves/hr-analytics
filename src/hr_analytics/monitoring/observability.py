"""Camada de observabilidade: métricas de latência, inferências, tokens e custos.

Registra métricas em tempo real para monitoramento do sistema.
Dados são persistidos em SQLite para consulta via dashboard.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from hr_analytics.data.database import Base

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Tipos de métricas de observabilidade."""

    INFERENCE = "inference"
    LLM_CALL = "llm_call"
    LLM_BATCH = "llm_batch"
    AGENT_CALL = "agent_call"
    API_REQUEST = "api_request"


class ObservabilityLog(Base):
    """Registro de métricas de observabilidade no banco de dados."""

    __tablename__ = "observability_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    endpoint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    items_processed: Mapped[int] = mapped_column(Integer, default=1)
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)


@dataclass
class RequestMetrics:
    """Métricas coletadas durante uma requisição."""

    metric_type: MetricType
    endpoint: str = ""
    start_time: float = field(default_factory=time.time)
    input_tokens: int = 0
    output_tokens: int = 0
    items_processed: int = 1
    success: bool = True
    error_message: str | None = None

    @property
    def latency_ms(self) -> float:
        """Latência em milissegundos desde o início."""
        return (time.time() - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        """Total de tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Custo estimado em USD baseado nos tokens do Gemini Flash.

        Preços do Gemini Flash (nível pago):
        - Input:  $0.50 / 1M tokens (texto/imagem/vídeo)
        - Output: $3.00 / 1M tokens (incluindo tokens de pensamento)
        Ref: https://ai.google.dev/pricing
        """
        input_cost = self.input_tokens * 0.50 / 1_000_000
        output_cost = self.output_tokens * 3.00 / 1_000_000
        return input_cost + output_cost

    def to_db_record(self) -> dict:
        """Converte para dicionário compatível com o modelo ORM."""
        return {
            "metric_type": self.metric_type.value,
            "endpoint": self.endpoint,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "items_processed": self.items_processed,
            "success": self.success,
            "error_message": self.error_message,
        }


class ObservabilityTracker:
    """Rastreia e persiste métricas de observabilidade."""

    def __init__(self):
        self._buffer: list[dict] = []
        self._buffer_size = 50  # flush a cada 50 registros

    def record(self, metrics: RequestMetrics) -> None:
        """Registra uma métrica no buffer.

        Args:
            metrics: Métricas coletadas da requisição.
        """
        record = metrics.to_db_record()
        self._buffer.append(record)
        logger.debug(
            "[%s] %s — %.0fms, %d tokens",
            metrics.metric_type.value,
            metrics.endpoint,
            metrics.latency_ms,
            metrics.total_tokens,
        )

        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> int:
        """Persiste o buffer no banco de dados.

        Returns:
            Número de registros persistidos.
        """
        if not self._buffer:
            return 0

        from hr_analytics.data.database import get_session

        records = self._buffer.copy()
        self._buffer.clear()

        try:
            session = get_session()
            for record in records:
                log = ObservabilityLog(**record)
                session.add(log)
            session.commit()
            session.close()
            logger.info("Observabilidade: %d registros persistidos", len(records))
            return len(records)
        except Exception as e:
            logger.error("Erro ao persistir métricas: %s", e)
            return 0

    def get_summary(self, hours: int = 24) -> dict:
        """Retorna resumo das métricas das últimas N horas.

        Args:
            hours: Janela de tempo em horas.

        Returns:
            Dicionário com métricas agregadas.
        """
        from datetime import timedelta

        from sqlalchemy import func as sqla_func

        from hr_analytics.data.database import get_session

        session = get_session()
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        try:
            logs = (
                session.query(
                    ObservabilityLog.metric_type,
                    sqla_func.count().label("count"),
                    sqla_func.avg(ObservabilityLog.latency_ms).label("avg_latency_ms"),
                    sqla_func.min(ObservabilityLog.latency_ms).label("min_latency_ms"),
                    sqla_func.max(ObservabilityLog.latency_ms).label("max_latency_ms"),
                    sqla_func.sum(ObservabilityLog.total_tokens).label("total_tokens"),
                    sqla_func.sum(ObservabilityLog.estimated_cost_usd).label("total_cost_usd"),
                    sqla_func.sum(ObservabilityLog.items_processed).label("total_items"),
                )
                .filter(ObservabilityLog.created_at >= cutoff)
                .group_by(ObservabilityLog.metric_type)
                .all()
            )

            summary = {}
            for row in logs:
                summary[row.metric_type] = {
                    "count": row.count,
                    "avg_latency_ms": round(row.avg_latency_ms, 1),
                    "min_latency_ms": round(row.min_latency_ms, 1),
                    "max_latency_ms": round(row.max_latency_ms, 1),
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": round(row.total_cost_usd or 0, 4),
                    "total_items": row.total_items or 0,
                }

            return summary
        finally:
            session.close()


# Instância global
tracker = ObservabilityTracker()
