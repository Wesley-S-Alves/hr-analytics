"""Página 9 — Observabilidade: latência, inferências, tokens e custos."""

import streamlit as st
import httpx

from components.sidebar import get_api_url
from components.theme import apply_theme

st.set_page_config(page_title="Observabilidade", page_icon="🔍", layout="wide")
st.title("🔍 Observabilidade — Métricas do Sistema")
st.caption(
    "Métricas operacionais do sistema: latência, volume de requisições, tokens "
    "consumidos e custos por chamada."
)

# CSS do tema — mesmas caixas (externa #1E2538 + interna #0F1420)
apply_theme()


# Seletor de período + botão (sem caixa, estilo Dashboard)
col_period, col_btn = st.columns([1, 2])
with col_period:
    hours = st.selectbox("Período", [1, 6, 12, 24, 48, 168], index=3, format_func=lambda h: f"Últimas {h}h")
with col_btn:
    st.markdown("<div style='height: 1.7rem;'></div>", unsafe_allow_html=True)
    refresh = st.button("🔄 Atualizar Métricas", type="primary")

if refresh:
    with st.spinner("Carregando métricas..."):
        try:
            resp = httpx.get(
                get_api_url("/monitoring/observability"),
                params={"hours": hours},
                timeout=10,
            )
            resp.raise_for_status()
            st.session_state["obs_data"] = resp.json()
        except Exception as e:
            st.error(f"Erro ao carregar métricas: {e}")

# Mapeamento de tipos técnicos → rótulos amigáveis, ícones e categoria (ML local vs LLM)
METRIC_LABELS = {
    "inference":   {"label": "Modelo ML (Preditivo)",      "icon": "🤖", "category": "ml"},
    "llm_call":    {"label": "LLM — Chamada Individual",   "icon": "💬", "category": "llm"},
    "llm_batch":   {"label": "LLM — Processamento em Lote", "icon": "📦", "category": "llm"},
    "agent_call":  {"label": "Agente Conversacional",      "icon": "🧠", "category": "llm"},
    "api_request": {"label": "API REST",                    "icon": "🌐", "category": "infra"},
}


def _big_number_tile(label: str, value: str, accent: str = "#00BCD4") -> str:
    """Tile escuro com número grande e label — fundo azul escuro (#0F1420)."""
    return (
        f"<div style='"
        f"background:#0F1420; border:1px solid #2D3748; border-radius:8px;"
        f"padding:0.9rem 1rem; height:100%;'>"
        f"<div style='color:#94A3B8; font-size:0.75rem; text-transform:uppercase;"
        f" letter-spacing:0.6px; margin-bottom:0.3rem;'>{label}</div>"
        f"<div style='color:{accent}; font-size:1.6rem; font-weight:700; line-height:1.1;'>{value}</div>"
        f"</div>"
    )


def _metric_card(metric_type: str, m: dict) -> str:
    """Card bonito para cada tipo de métrica — com badge de categoria e stats em grid."""
    info = METRIC_LABELS.get(metric_type, {"label": metric_type, "icon": "📊", "category": "infra"})
    cat = info["category"]
    cat_colors = {
        "ml":    ("#10B981", "ML Local"),     # verde — roda localmente, sem custo por token
        "llm":   ("#F59E0B", "LLM (API)"),    # âmbar — consome tokens, tem custo
        "infra": ("#3B82F6", "Infra"),
    }
    badge_color, badge_label = cat_colors.get(cat, ("#6B7280", "Outro"))

    count = m.get("count", 0)
    avg_lat = m.get("avg_latency_ms", 0)
    min_lat = m.get("min_latency_ms", 0)
    max_lat = m.get("max_latency_ms", 0)
    tokens = m.get("total_tokens", 0)
    cost = m.get("total_cost_usd", 0.0)
    items = m.get("total_items", 0)

    tokens_display = f"{tokens:,}" if cat == "llm" else "—"
    cost_display = f"US$ {cost:.4f}" if cat == "llm" else "—"

    # Grid interno com stats em caixas menores (fundo azul escuro)
    def stat(label: str, value: str) -> str:
        return (
            f"<div style='background:#0F1420; border:1px solid #2D3748; border-radius:6px;"
            f" padding:0.55rem 0.7rem;'>"
            f"<div style='color:#94A3B8; font-size:0.68rem; text-transform:uppercase;"
            f" letter-spacing:0.5px; margin-bottom:0.15rem;'>{label}</div>"
            f"<div style='color:#FAFAFA; font-size:1.05rem; font-weight:700;'>{value}</div>"
            f"</div>"
        )

    return (
        f"<div style='background:#1A1F2E; border:1px solid #2D3748; border-radius:10px;"
        f" padding:1rem 1.1rem; margin-bottom:0.75rem;'>"
        # Header: ícone + nome + badge
        f"<div style='display:flex; justify-content:space-between; align-items:center;"
        f" margin-bottom:0.8rem;'>"
        f"<div style='display:flex; align-items:center; gap:0.55rem;'>"
        f"<span style='font-size:1.3rem;'>{info['icon']}</span>"
        f"<span style='color:#FAFAFA; font-size:1.05rem; font-weight:700;'>{info['label']}</span>"
        f"</div>"
        f"<span style='background:{badge_color}; color:#0F1420; font-size:0.7rem;"
        f" font-weight:700; padding:0.2rem 0.6rem; border-radius:12px;'>{badge_label}</span>"
        f"</div>"
        # Grid de stats
        f"<div style='display:grid; grid-template-columns:repeat(6, 1fr); gap:0.5rem;'>"
        f"{stat('Requisições', f'{count:,}')}"
        f"{stat('Latência Média', f'{avg_lat:.0f} ms')}"
        f"{stat('Mín / Máx', f'{min_lat:.0f} / {max_lat:.0f} ms')}"
        f"{stat('Itens', f'{items:,}')}"
        f"{stat('Tokens', tokens_display)}"
        f"{stat('Custo', cost_display)}"
        f"</div>"
        f"</div>"
    )


if "obs_data" in st.session_state:
    data = st.session_state["obs_data"]
    metrics = data.get("metrics_by_type", {})

    if not metrics:
        st.info("Nenhuma métrica registrada no período selecionado.")
    else:
        # Agregados separados: ML local vs LLM (tem custo)
        total_requests = sum(m["count"] for m in metrics.values())
        avg_latency = (
            sum(m["avg_latency_ms"] * m["count"] for m in metrics.values()) / total_requests
            if total_requests > 0
            else 0
        )
        ml_requests = sum(
            m["count"] for mt, m in metrics.items()
            if METRIC_LABELS.get(mt, {}).get("category") == "ml"
        )
        llm_tokens = sum(
            m["total_tokens"] for mt, m in metrics.items()
            if METRIC_LABELS.get(mt, {}).get("category") == "llm"
        )
        llm_cost = sum(
            m["total_cost_usd"] for mt, m in metrics.items()
            if METRIC_LABELS.get(mt, {}).get("category") == "llm"
        )

        with st.container(border=True):
            st.subheader("📊 Visão Geral")
            tiles = (
                "<div style='display:grid; grid-template-columns:repeat(5, 1fr);"
                " gap:0.7rem; padding:0.6rem 0.2rem 0.4rem 0.2rem;'>"
                + _big_number_tile("Total de Requisições", f"{total_requests:,}")
                + _big_number_tile("Latência Média", f"{avg_latency:.0f} ms")
                + _big_number_tile("Predições ML Local", f"{ml_requests:,}", accent="#10B981")
                + _big_number_tile("Tokens LLM Consumidos", f"{llm_tokens:,}", accent="#F59E0B")
                + _big_number_tile("Custo LLM", f"US$ {llm_cost:.4f}", accent="#F59E0B")
                + "</div>"
            )
            st.markdown(tiles, unsafe_allow_html=True)

        # Cards bonitos por tipo de métrica (substitui a tabela)
        with st.container(border=True):
            st.subheader("📈 Detalhamento por Tipo")
            cards_html = "".join(_metric_card(mt, m) for mt, m in metrics.items())
            st.markdown(cards_html, unsafe_allow_html=True)

        # Nota sobre ML local vs LLM
        st.caption(
            "💡 **ML Local** (modelo preditivo XGBoost) roda na CPU do servidor — sem consumo de tokens ou custo por requisição. "
            "**LLM (API)** chama o Gemini e é cobrado por token (input: \\$0,50/M · output: \\$3,00/M)."
        )
else:
    st.info("Clique em 'Atualizar Métricas' para carregar os dados.")
