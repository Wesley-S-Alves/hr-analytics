"""Notificações via webhook (Slack-compatible ou genérico)."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def send_drift_alert(
    status: str,
    features_drifted: list[str],
    features_warning: list[str],
    recommendation: str,
    webhook_url: str | None = None,
) -> bool:
    """Envia alerta de drift via webhook (Slack incoming webhook ou genérico).

    Formato Slack-compatível (`text` + `attachments`) — também aceito
    por muitos outros collectors (Discord, Teams via bridge, etc.).

    Args:
        status: "ok" / "warning" / "alert"
        features_drifted: features com PSI > 0.2
        features_warning: features com PSI 0.1-0.2
        recommendation: texto da recomendação
        webhook_url: override. Se None, lê DRIFT_WEBHOOK_URL do env.

    Returns:
        True se enviado com sucesso (HTTP 2xx).
    """
    url = webhook_url or os.getenv("DRIFT_WEBHOOK_URL", "")
    if not url:
        logger.info("DRIFT_WEBHOOK_URL não configurado — alerta não enviado")
        return False

    color_map = {"ok": "#10B981", "warning": "#F59E0B", "alert": "#DC2626"}
    emoji_map = {"ok": "🟢", "warning": "🟡", "alert": "🔴"}

    payload = {
        "text": f"{emoji_map.get(status, '⚪')} *Drift Alert — {status.upper()}*",
        "attachments": [
            {
                "color": color_map.get(status, "#6B7280"),
                "fields": [
                    {"title": "Status", "value": status.upper(), "short": True},
                    {"title": "Features com Drift", "value": ", ".join(features_drifted) or "—", "short": False},
                    {"title": "Features em Atenção", "value": ", ".join(features_warning) or "—", "short": False},
                    {"title": "Recomendação", "value": recommendation or "—", "short": False},
                ],
            }
        ],
    }

    try:
        r = httpx.post(url, json=payload, timeout=10)
        ok = r.is_success
        logger.info("Webhook enviado: status=%s http=%d", status, r.status_code)
        return ok
    except Exception as e:
        logger.error("Falha ao enviar webhook: %s", e)
        return False
