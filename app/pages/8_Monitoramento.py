"""Página 8 — Monitoramento: PSI, drift e saúde do modelo (UX melhorada)."""

import streamlit as st
import httpx
import plotly.graph_objects as go

from components.sidebar import get_api_url
from components.charts import psi_bar_chart
from components.theme import apply_theme

st.set_page_config(page_title="Monitoramento", page_icon="📈", layout="wide")
st.title("📈 Monitoramento — Saúde do Modelo")
st.caption(
    "Acompanhe o estado do modelo em produção: métricas atuais, drift por feature (PSI), "
    "acesso ao MLflow para comparar experimentos e alertas quando há sinal de degradação."
)


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

# CSS do tema — mesmas caixas (externa #1E2538 + interna #0F1420)
apply_theme()

# ── SAÚDE DO MODELO ──
with st.container(border=True):
    st.subheader("🏥 Estado Atual do Modelo")
    try:
        resp = httpx.get(get_api_url("/monitoring/health"), timeout=10)
        resp.raise_for_status()
        health = resp.json()

        # Traduzir status
        raw_status = health.get("status", "N/A")
        status_pt = {"healthy": "Saudável", "degraded": "Degradado", "down": "Indisponível"}.get(
            raw_status.lower(), raw_status.title()
        )
        status_icon = "🟢" if raw_status == "healthy" else "🔴"
        status_accent = "#10B981" if raw_status == "healthy" else "#EF4444"

        # Formatar data
        raw_date = health.get("trained_at", "")
        try:
            from datetime import datetime
            dt = datetime.strptime(raw_date, "%Y%m%d_%H%M%S")
            formatted_date = dt.strftime("%d/%m/%Y às %H:%M")
        except (ValueError, TypeError):
            formatted_date = raw_date

        # Big-number tiles dos metadados do modelo
        meta_tiles = (
            "<div style='display:grid; grid-template-columns:repeat(4, 1fr);"
            " gap:0.7rem; padding:0.6rem 0.2rem 0.4rem 0.2rem;'>"
            + _big_number_tile("Status", f"{status_icon} {status_pt}", accent=status_accent)
            + _big_number_tile("Modelo", health.get("model_name", "N/A"))
            + _big_number_tile("Treinado em", formatted_date)
            + _big_number_tile("Threshold", f"{health.get('threshold', 0):.4f}")
            + "</div>"
        )
        st.markdown(meta_tiles, unsafe_allow_html=True)

        # Métricas em cards — big-number tiles
        if health.get("metrics"):
            st.markdown("#### 📊 Métricas do Modelo")
            metrics = health["metrics"]
            metric_tiles = (
                "<div style='display:grid; grid-template-columns:repeat(5, 1fr);"
                " gap:0.7rem; padding:0.4rem 0.2rem 0.6rem 0.2rem;'>"
                + _big_number_tile("ROC-AUC", f"{metrics.get('roc_auc', 0):.4f}")
                + _big_number_tile("PR-AUC", f"{metrics.get('pr_auc', 0):.4f}")
                + _big_number_tile("F1-Score", f"{metrics.get('f1', 0):.4f}")
                + _big_number_tile("Precision", f"{metrics.get('precision', 0):.4f}")
                + _big_number_tile("Recall", f"{metrics.get('recall', 0):.4f}")
                + "</div>"
            )
            st.markdown(metric_tiles, unsafe_allow_html=True)

            # Gráfico radar das métricas
            metric_names = ["ROC-AUC", "PR-AUC", "F1", "Precision", "Recall"]
            metric_values = [metrics.get("roc_auc", 0), metrics.get("pr_auc", 0),
                             metrics.get("f1", 0), metrics.get("precision", 0), metrics.get("recall", 0)]

            fig = go.Figure(go.Scatterpolar(
                r=metric_values + [metric_values[0]],
                theta=metric_names + [metric_names[0]],
                fill="toself",
                fillcolor="rgba(0,188,212,0.3)",
                line=dict(color="#00BCD4", width=3),
                marker=dict(size=10, color="#00BCD4"),
                text=[f"{v:.3f}" for v in metric_values + [metric_values[0]]],
                textposition="top center",
                mode="lines+markers+text",
                textfont=dict(color="#FAFAFA", size=12),
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1],
                        showticklabels=False,
                        ticks="",
                        gridcolor="rgba(51,65,85,0.4)",
                        linecolor="rgba(51,65,85,0.4)",
                    ),
                    angularaxis=dict(
                        tickfont=dict(color="#FAFAFA", size=13),
                        gridcolor="rgba(51,65,85,0.4)",
                        linecolor="rgba(51,65,85,0.4)",
                    ),
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#FAFAFA"),
                height=400,
                title=dict(text="<b>Radar de Métricas</b>", x=0.02, font=dict(color="#FAFAFA", size=15)),
                showlegend=False,
                margin=dict(t=60, b=30, l=30, r=30),
            )
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao consultar saúde: {e}")

# ── MLFLOW UI ──
with st.container(border=True):
    st.subheader("🧪 Experimentos MLflow")
    import os
    mlflow_ui = os.getenv("MLFLOW_UI_URL", "http://localhost:5000")
    st.markdown(
        f"""
        <div style='background:#0F1420; border:1px solid #2D3748; border-radius:8px;
                    padding:1.2rem; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='color:#CBD5E1; font-size:0.95rem; margin-bottom:0.3rem;'>
                    Acesse a interface do MLflow para comparar runs, ver métricas por experimento e baixar artefatos.
                </div>
                <div style='color:#94A3B8; font-size:0.8rem;'>URL: {mlflow_ui}</div>
            </div>
            <a href='{mlflow_ui}' target='_blank' style='
                background:#00BCD4; color:#0F1420; text-decoration:none;
                padding:0.6rem 1.2rem; border-radius:8px; font-weight:700;
                font-size:0.95rem;'>
                Abrir MLflow ↗
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── DRIFT (PSI) ──
with st.container(border=True):
    st.subheader("📉 Análise de Drift (PSI)")
    st.caption("Compara a distribuição das features entre treino e dados atuais")

    if st.button("🔄 Gerar Relatório de Drift", type="primary"):
        with st.spinner("Calculando PSI por feature..."):
            try:
                resp = httpx.get(get_api_url("/monitoring/drift"), timeout=30)
                resp.raise_for_status()
                st.session_state["drift_report"] = resp.json()
            except Exception as e:
                st.error(f"Erro: {e}")

    if "drift_report" in st.session_state:
        drift = st.session_state["drift_report"]
        status = drift["overall_status"]

        # Semáforo visual
        status_map = {"ok": ("🟢", "Modelo Estável", "#10B981"),
                      "warning": ("🟡", "Atenção", "#F59E0B"),
                      "alert": ("🔴", "Drift Detectado", "#EF4444")}
        icon, label, color = status_map.get(status, ("⚪", "Desconhecido", "#6B7280"))

        drift_tiles = (
            "<div style='display:grid; grid-template-columns:repeat(3, 1fr);"
            " gap:0.7rem; padding:0.6rem 0.2rem 0.6rem 0.2rem;'>"
            + _big_number_tile("Status", f"{icon} {label}", accent=color)
            + _big_number_tile("Features com Drift", f"{len(drift.get('features_drifted', []))}", accent="#EF4444")
            + _big_number_tile("Features em Atenção", f"{len(drift.get('features_warning', []))}", accent="#F59E0B")
            + "</div>"
        )
        st.markdown(drift_tiles, unsafe_allow_html=True)

        st.info(drift.get("recommendation", ""))

        # Gráfico PSI
        if drift.get("feature_psi"):
            st.plotly_chart(psi_bar_chart(drift["feature_psi"]), use_container_width=True)

        if drift.get("features_drifted"):
            st.error(f"**Features com drift significativo (PSI > 0.2):** {', '.join(drift['features_drifted'])}")
        if drift.get("features_warning"):
            st.warning(f"**Features em atenção (PSI 0.1-0.2):** {', '.join(drift['features_warning'])}")
