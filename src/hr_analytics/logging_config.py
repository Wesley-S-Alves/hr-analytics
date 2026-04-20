"""Configuração de logging estruturado (JSON) pra toda a aplicação.

Usa apenas stdlib (json + logging.Formatter) — sem deps externas tipo structlog.
Saída compatível com qualquer coletor (CloudWatch, Datadog, Loki, ELK).

Uso:
    from hr_analytics.logging_config import configure_logging
    configure_logging(level="INFO", format="json")
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formatter que emite logs em JSON (uma linha por registro)."""

    # Campos padrão do LogRecord que NÃO vão para "extra"
    _STANDARD_ATTRS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Exception info
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Campos extras passados via logger.info("msg", extra={"key": "val"})
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_ATTRS and not key.startswith("_"):
                try:
                    json.dumps(value)  # checa serializabilidade
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str | None = None, format: str | None = None) -> None:
    """Configura o root logger.

    Args:
        level: DEBUG/INFO/WARNING/ERROR (padrão: env LOG_LEVEL ou INFO).
        format: "json" ou "text" (padrão: env LOG_FORMAT ou "text").
            Em produção, usar "json" para ingestão em coletores.
    """
    level = level or os.getenv("LOG_LEVEL", "INFO")
    format = format or os.getenv("LOG_FORMAT", "text")

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Remove handlers existentes pra não duplicar logs
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root.addHandler(handler)

    # Silenciar loggers muito verbosos de libs
    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
