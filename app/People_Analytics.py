"""Entrada principal — People Analytics."""

import streamlit as st

st.set_page_config(
    page_title="People Analytics",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("👥 People Analytics")
st.caption("Plataforma de inteligência para retenção de talentos com IA")
st.markdown("---")

# Módulos (label, href, icon, title, desc)
# Os hrefs usam as URLs do Streamlit multipage (sem /pages prefix, usa o nome da página)
modules = [
    ("Dashboard", "📊", "Dashboard", "KPIs, filtros self-service, risco por departamento e top colaboradores críticos"),
    ("Colaborador", "👤", "Colaborador", "Análise individual com explicabilidade SHAP, relatório IA e exportação em PDF"),
    ("Chat", "💬", "Chat IA", "Perguntas em linguagem natural sobre dados, conceitos de RH e gráficos automáticos"),
    ("Cadastro", "➕", "Cadastro", "Gerenciamento de colaboradores com análise preditiva automática ao cadastrar"),
    ("Monitoramento", "📈", "Monitoramento", "PSI e drift do modelo, métricas de performance e saúde do sistema"),
    ("Observabilidade", "🔍", "Observabilidade", "Latência de requisições, tokens consumidos e custos estimados por operação"),
]

# CSS dos cards
st.markdown(
    """
    <style>
    .module-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-top: 0.5rem;
    }
    .module-card {
        display: block;
        background: #1E2538;
        border: 1px solid #3A4660;
        border-radius: 10px;
        padding: 1.2rem 1.3rem;
        text-decoration: none !important;
        color: inherit !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
        transition: all 0.2s ease;
        cursor: pointer;
        min-height: 150px;
    }
    .module-card:hover {
        background: #252D44;
        border-color: #5C6A85;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }
    .module-card-inner {
        background: #0F1420;
        border: 1px solid #2D3748;
        border-radius: 6px;
        padding: 0.9rem 1rem;
        height: 100%;
    }
    .module-card-title {
        color: #FAFAFA;
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .module-card-desc {
        color: #94A3B8;
        font-size: 0.82rem;
        line-height: 1.4;
        margin: 0;
    }
    .module-card-icon {
        font-size: 1.3rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Renderizar grid de cards — anchor <a> envolvendo TODO o card
cards_html = ""
for href, icon, title, desc in modules:
    cards_html += (
        f"<a href='{href}' target='_self' class='module-card'>"
        f"  <div class='module-card-inner'>"
        f"    <div class='module-card-title'>"
        f"      <span class='module-card-icon'>{icon}</span>"
        f"      <span>{title}</span>"
        f"    </div>"
        f"    <div class='module-card-desc'>{desc}</div>"
        f"  </div>"
        f"</a>"
    )

st.markdown(
    f"<div class='module-grid'>{cards_html}</div>",
    unsafe_allow_html=True,
)
