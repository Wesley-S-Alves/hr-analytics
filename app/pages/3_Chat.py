"""Página 3 — Chat com o Agente de People Analytics.

Suporta respostas em texto + gráficos automáticos.
Botões de exemplo na sidebar acionam o modelo diretamente.
"""

import re
import uuid

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import httpx

from components.sidebar import get_api_url
from components.theme import apply_theme, EXTRA_CHAT
from components.translations import (
    DEPT_PT, ROLE_PT, EDUCATION_FIELD_PT, MARITAL_PT, TRAVEL_PT,
)

st.set_page_config(page_title="Chat IA", page_icon="💬", layout="wide")
st.title("💬 Chat — Agente de People Analytics")
st.caption(
    "Faça perguntas em linguagem natural sobre risco, attrition, fatores, departamentos "
    "e melhores práticas de retenção. Gráficos são gerados automaticamente quando aplicável."
)

# CSS do tema + chat messages neutralizados + avatars neutros + sidebar buttons
apply_theme(extra_css=EXTRA_CHAT)

# Estado da conversação
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_message" not in st.session_state:
    st.session_state.pending_message = None


def send_message_only_response(message: str):
    """Envia mensagem e adiciona SOMENTE a resposta ao histórico (user já foi adicionado)."""
    try:
        resp = httpx.post(
            get_api_url("/agent/chat"),
            json={"message": message, "conversation_id": st.session_state.conversation_id},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["response"],
            "chart": result.get("chart"),
            "tools_used": result.get("tools_used", []),
        })
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Erro: {e}"})


def send_message(message: str):
    """Envia mensagem para o agente — adiciona user + resposta."""
    st.session_state.messages.append({"role": "user", "content": message})
    try:
        resp = httpx.post(
            get_api_url("/agent/chat"),
            json={"message": message, "conversation_id": st.session_state.conversation_id},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["response"],
            "chart": result.get("chart"),
            "tools_used": result.get("tools_used", []),
            "structured_data": result.get("structured_data"),
        })
    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Erro: {e}",
        })


# Paleta coesa para séries múltiplas (dark theme)
SERIES_PALETTE = [
    "#00BCD4",  # ciano
    "#8B5CF6",  # roxo
    "#10B981",  # verde
    "#F59E0B",  # âmbar
    "#EC4899",  # rosa
    "#3B82F6",  # azul
    "#14B8A6",  # teal
    "#F97316",  # laranja
    "#6366F1",  # índigo
    "#A78BFA",  # lavanda
]

# Tradução EN→PT comum em títulos/labels
EN_PT_TERMS = {
    "department": "Departamento",
    "departments": "Departamentos",
    "job role": "Cargo",
    "job roles": "Cargos",
    "role": "Cargo",
    "roles": "Cargos",
    "attrition pct": "% Attrition",
    "attrition": "Attrition",
    "pct": "%",
    "percent": "%",
    "average": "Média",
    "avg": "Média",
    "salary": "Salário",
    "income": "Salário",
    "monthly income": "Salário Mensal",
    "count": "Total",
    "total": "Total",
    "over time": "Hora Extra",
    "overtime": "Hora Extra",
    "gender": "Gênero",
    "age": "Idade",
    "years at company": "Anos na Empresa",
    "years in current role": "Anos no Cargo",
    "years": "Anos",
    "risk": "Risco",
    "risk level": "Nível de Risco",
    "risk score": "Score de Risco",
    "low": "Baixo",
    "medium": "Médio",
    "high": "Alto",
    "critical": "Crítico",
    "employees": "Colaboradores",
    "employee": "Colaborador",
    "male": "Masculino",
    "female": "Feminino",
    "yes": "Sim",
    "no": "Não",
    # Adiciona traduções específicas de valores de dept/cargo/formação/etc.
    **DEPT_PT,              # "Sales" → "Vendas", etc.
    **ROLE_PT,              # "Sales Executive" → "Executivo de Vendas", etc.
    **EDUCATION_FIELD_PT,   # "Life Sciences" → "Ciências da Vida", etc.
    **MARITAL_PT,           # "Single" → "Solteiro(a)", etc.
    **TRAVEL_PT,            # "Travel_Rarely" → "Viaja raramente", etc.
}


def _translate(text: str) -> str:
    """Traduz termos comuns EN→PT em títulos e labels do chart."""
    if not text:
        return ""
    out = text
    # Ordem: termos longos primeiro pra não quebrar matches parciais
    for en, pt in sorted(EN_PT_TERMS.items(), key=lambda x: -len(x[0])):
        # Case-insensitive replacement preservando primeira letra maiúscula quando for title
        out = re.sub(rf"\b{re.escape(en)}\b", pt, out, flags=re.IGNORECASE)
    return out


def _is_percent(y_label: str, title: str) -> bool:
    """Heurística pra detectar se o eixo Y é percentual."""
    joined = f"{y_label} {title}".lower()
    return any(t in joined for t in ["%", "pct", "percent", "attrition"])


def _styled_layout(fig, title: str, chart_data: dict, show_legend: bool = False):
    """Aplica layout consistente: título bem estilizado, eixos limpos, fundo transparente."""
    y_label = _translate(chart_data.get("y_label", ""))
    x_label = _translate(chart_data.get("x_label", ""))
    is_pct = _is_percent(y_label, title)
    tickformat = ".0f"
    ticksuffix = "%" if is_pct else ""

    fig.update_layout(
        title=dict(
            text=f"<b>{_translate(title)}</b>",
            x=0.02, y=0.95,
            font=dict(size=15, color="#FAFAFA"),
        ),
        height=420,
        margin=dict(l=50, r=30, t=60, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FAFAFA", family="Inter, system-ui, sans-serif"),
        showlegend=show_legend,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#CBD5E1"),
            orientation="v",
            x=1.02, y=1,
        ),
    )
    fig.update_xaxes(
        title=dict(text=x_label, font=dict(size=12, color="#94A3B8")),
        tickfont=dict(size=11, color="#CBD5E1"),
        gridcolor="rgba(51,65,85,0.3)",
        zeroline=False,
        showline=False,
    )
    fig.update_yaxes(
        title=dict(text=y_label, font=dict(size=12, color="#94A3B8")),
        tickfont=dict(size=11, color="#CBD5E1"),
        gridcolor="rgba(51,65,85,0.3)",
        zeroline=False,
        showline=False,
        tickformat=tickformat,
        ticksuffix=ticksuffix,
    )
    return fig


def render_chart(chart_data: dict, key: str | None = None):
    """Renderiza gráfico Plotly com tema consistente e paleta coesa."""
    chart_type = chart_data.get("chart_type", "bar")
    title = chart_data.get("title", "")
    items = chart_data.get("data", [])
    if not items:
        return

    # Key único por chamada — evita StreamlitDuplicateElementId
    if key is None:
        key = f"chart_{uuid.uuid4().hex[:8]}"

    is_pct = _is_percent(chart_data.get("y_label", ""), title)
    val_fmt = (lambda v: f"{v:.1f}%") if is_pct else (lambda v: f"{v:,.0f}" if v >= 10 else f"{v:.1f}")

    if chart_type == "grouped_bar":
        df = pd.DataFrame(items)
        groups = list(df["group"].unique())
        fig = go.Figure()
        for i, group in enumerate(groups):
            gd = df[df["group"] == group]
            fig.add_trace(go.Bar(
                name=_translate(str(group)),
                x=[_translate(str(x)) for x in gd["label"]],
                y=gd["value"],
                text=[val_fmt(v) for v in gd["value"]],
                textposition="outside",
                textfont=dict(size=10, color="#CBD5E1"),
                marker=dict(
                    color=SERIES_PALETTE[i % len(SERIES_PALETTE)],
                    line=dict(width=0),
                ),
                hovertemplate=f"<b>{_translate(str(group))}</b><br>%{{x}}: %{{y}}{'%' if is_pct else ''}<extra></extra>",
            ))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.1)
        _styled_layout(fig, title, chart_data, show_legend=True)
        st.plotly_chart(fig, use_container_width=True, key=key)
        return

    labels = [_translate(str(item["label"])) for item in items]
    values = [item["value"] for item in items]

    if chart_type == "pie":
        fig = go.Figure(go.Pie(
            labels=labels, values=values,
            textinfo="percent+label", textposition="outside",
            marker=dict(colors=SERIES_PALETTE[:len(labels)], line=dict(color="#0F1420", width=2)),
            hole=0.4,
        ))
        fig.update_layout(
            title=dict(text=f"<b>{_translate(title)}</b>", x=0.02, y=0.95,
                       font=dict(size=15, color="#FAFAFA")),
            height=420, margin=dict(l=30, r=30, t=60, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#FAFAFA"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#CBD5E1")),
        )
    elif chart_type == "horizontal_bar":
        pairs = sorted(zip(labels, values), key=lambda x: x[1])
        labs, vals = [p[0] for p in pairs], [p[1] for p in pairs]
        fig = go.Figure(go.Bar(
            x=vals, y=labs, orientation="h",
            text=[val_fmt(v) for v in vals],
            textposition="outside",
            textfont=dict(size=10, color="#CBD5E1"),
            marker=dict(
                color=vals,
                colorscale=[[0, "#10B981"], [0.5, "#F59E0B"], [1, "#DC2626"]],
                line=dict(width=0),
            ),
            hovertemplate=f"<b>%{{y}}</b>: %{{x}}{'%' if is_pct else ''}<extra></extra>",
        ))
        _styled_layout(fig, title, chart_data, show_legend=False)
    else:
        fig = go.Figure(go.Bar(
            x=labels, y=values,
            text=[val_fmt(v) for v in values],
            textposition="outside",
            textfont=dict(size=10, color="#CBD5E1"),
            marker=dict(
                color=SERIES_PALETTE[0],
                line=dict(width=0),
            ),
            hovertemplate=f"<b>%{{x}}</b>: %{{y}}{'%' if is_pct else ''}<extra></extra>",
        ))
        fig.update_layout(bargap=0.3)
        _styled_layout(fig, title, chart_data, show_legend=False)

    st.plotly_chart(fig, use_container_width=True, key=key)


# ── SIDEBAR — Exemplos clicáveis ──
st.sidebar.subheader("💡 Exemplos de perguntas")
examples = [
    "Quantos colaboradores tem por departamento?",
    "Qual o percentual de attrition por departamento?",
    "Qual a média salarial por cargo?",
    "Quem tem maior risco de saída por time?",
    "Por que o colaborador 3 está em risco?",
    "Quantos colaboradores fazem hora extra por departamento?",
    "Quais são as melhores práticas de retenção de talentos?",
]

for example in examples:
    if st.sidebar.button(example, key=f"ex_{hash(example)}"):
        st.session_state.pending_message = example

if st.sidebar.button("🗑️ Limpar conversa"):
    st.session_state.messages = []
    st.session_state.conversation_id = str(uuid.uuid4())
    st.rerun()

# ── Processar mensagem pendente (do botão sidebar) ──
# Adiciona a mensagem do usuário primeiro, depois processa
if st.session_state.pending_message:
    pending = st.session_state.pending_message
    st.session_state.pending_message = None
    # Adicionar mensagem do usuário ao histórico ANTES de processar
    st.session_state.messages.append({"role": "user", "content": pending})
    st.session_state["_processing"] = pending

def safe_md(text: str) -> str:
    """Escapa $ (MathJax) e traduz termos comuns EN→PT no texto de resposta."""
    if not text:
        return ""
    # Tradução primeiro (pra pegar termos antes do escape de $)
    translated = _translate(text)
    # Depois escapa $ pra não virar LaTeX
    return translated.replace("$", r"\$")


# ── Exibir histórico ──
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(safe_md(msg["content"]))
        if msg.get("chart"):
            render_chart(msg["chart"], key=f"hist_chart_{idx}")
        if msg.get("tools_used"):
            with st.expander("🔧 Tools utilizados"):
                for tool in msg["tools_used"]:
                    st.code(tool)

# ── Processar mensagem que estava pendente (após renderizar a do usuário) ──
if st.session_state.get("_processing"):
    pending = st.session_state.pop("_processing")
    with st.chat_message("assistant"):
        with st.spinner("Analisando..."):
            send_message_only_response(pending)
            last = st.session_state.messages[-1]
            st.markdown(safe_md(last["content"]))
            if last.get("chart"):
                render_chart(last["chart"], key=f"proc_chart_{len(st.session_state.messages)}")

# ── Input do usuário ──
if prompt := st.chat_input("Faça uma pergunta sobre People Analytics..."):
    # Adicionar mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(safe_md(prompt))
    # Processar resposta
    with st.chat_message("assistant"):
        with st.spinner("Analisando..."):
            send_message_only_response(prompt)
            last = st.session_state.messages[-1]
            st.markdown(safe_md(last["content"]))
            if last.get("chart"):
                render_chart(last["chart"], key=f"input_chart_{len(st.session_state.messages)}")
