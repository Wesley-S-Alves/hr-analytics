"""Padrão de erros para API e tools.

Objetivo: ter uma estrutura única de erro que:
- Rotas FastAPI convertem automaticamente em HTTPException correta
- Tools do agente serializam como JSON sem crashar o fluxo

Uso:
    from hr_analytics.api.errors import NotFoundError, error_json

    # Em rota FastAPI:
    if not emp:
        raise NotFoundError("Colaborador não encontrado", resource="employee", id=employee_id)

    # Em tool do agente:
    return error_json("Colaborador não encontrado", code="NOT_FOUND", id=employee_id)
"""

import json
from typing import Any

from fastapi import HTTPException


class HRAnalyticsError(Exception):
    """Base de exceções da aplicação com código + contexto."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, **context: Any):
        super().__init__(message)
        self.message = message
        self.context = context

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                **({"context": self.context} if self.context else {}),
            }
        }

    def to_http(self) -> HTTPException:
        return HTTPException(status_code=self.status_code, detail=self.to_dict())


class NotFoundError(HRAnalyticsError):
    code = "NOT_FOUND"
    status_code = 404


class ValidationError(HRAnalyticsError):
    code = "VALIDATION_ERROR"
    status_code = 400


class ForbiddenError(HRAnalyticsError):
    code = "FORBIDDEN"
    status_code = 403


class ExternalServiceError(HRAnalyticsError):
    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


def error_json(message: str, code: str = "INTERNAL_ERROR", **context: Any) -> str:
    """Formata erro como JSON string pra uso em tools do agente."""
    payload = {"erro": message, "codigo": code}
    if context:
        payload["contexto"] = context
    return json.dumps(payload, ensure_ascii=False, default=str)
