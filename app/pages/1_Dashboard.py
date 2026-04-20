"""Página 1 — Dashboard: análise self-service com filtros e explicação IA."""

import streamlit as st
import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from components.sidebar import get_api_url
from components.theme import apply_theme

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("📊 Visão Geral de Risco")
st.caption(
    "Panorama consolidado do risco de saída — KPIs, distribuição por nível, drivers "
    "principais e ranking dos colaboradores mais críticos."
)


@st.cache_data(ttl=60)
def load_all_employees():
    all_emp = []
    page = 1
    try:
        while True:
            resp = httpx.get(get_api_url("/employees"), params={"page_size": 100, "page": page}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_emp.extend(data["employees"])
            if len(all_emp) >= data["total"]:
                break
            page += 1
        return pd.DataFrame(all_emp)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


df = load_all_employees()
if df.empty:
    st.warning("Sem dados. Verifique se a API está rodando e o banco populado.")
    st.stop()

# ── DICIONÁRIOS DE TRADUÇÃO ──
DEPT_PT = {
    "Sales": "Vendas",
    "Research & Development": "Pesquisa & Desenvolvimento",
    "Human Resources": "Recursos Humanos",
}
ROLE_PT = {
    "Sales Executive": "Executivo de Vendas",
    "Sales Representative": "Representante de Vendas",
    "Research Scientist": "Cientista de Pesquisa",
    "Laboratory Technician": "Técnico de Laboratório",
    "Manufacturing Director": "Diretor de Manufatura",
    "Healthcare Representative": "Representante de Saúde",
    "Manager": "Gerente",
    "Research Director": "Diretor de Pesquisa",
    "Human Resources": "Recursos Humanos",
}
GENDER_PT = {"Male": "Masculino", "Female": "Feminino"}
OVERTIME_PT = {"Yes": "Sim", "No": "Não"}


def tr_dept(v):
    return DEPT_PT.get(v, v)


def tr_role(v):
    return ROLE_PT.get(v, v)


def tr_gender(v):
    return GENDER_PT.get(v, v)


# Adicionar colunas traduzidas ao df
df["dept_pt"] = df["department"].map(tr_dept)
df["role_pt"] = df["job_role"].map(tr_role)
df["gender_pt"] = df["gender"].map(tr_gender)

# ── FILTROS ──
st.markdown("### 🔎 Filtros")
col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
with col_f1:
    depts_pt = ["Todos"] + sorted(df["dept_pt"].dropna().unique().tolist())
    sel_dept_pt = st.selectbox("Departamento", depts_pt)
with col_f2:
    roles_pt = ["Todos"] + sorted(df["role_pt"].dropna().unique().tolist())
    sel_role_pt = st.selectbox("Cargo", roles_pt)
with col_f3:
    sel_gender_pt = st.selectbox("Gênero", ["Todos", "Masculino", "Feminino"])
with col_f4:
    sel_risk = st.selectbox("Nível de Risco", ["Todos", "crítico", "alto", "médio", "baixo"])
with col_f5:
    sel_overtime_pt = st.selectbox("Hora Extra", ["Todos", "Sim", "Não"])

# Aplicar filtros
filtered = df.copy()
if sel_dept_pt != "Todos":
    filtered = filtered[filtered["dept_pt"] == sel_dept_pt]
if sel_role_pt != "Todos":
    filtered = filtered[filtered["role_pt"] == sel_role_pt]
if sel_gender_pt != "Todos":
    filtered = filtered[filtered["gender_pt"] == sel_gender_pt]
if sel_risk != "Todos":
    filtered = filtered[filtered["risk_level"] == sel_risk]
if sel_overtime_pt != "Todos":
    filtered = filtered[filtered["over_time"].map(lambda x: OVERTIME_PT.get(x, x)) == sel_overtime_pt]

with_risk = filtered[filtered["risk_score"].notna()]

# Calcular KPIs
total = len(filtered)
critical = len(with_risk[with_risk["risk_level"] == "crítico"])
high_r = len(with_risk[with_risk["risk_level"] == "alto"])
medium_r = len(with_risk[with_risk["risk_level"] == "médio"])
low_r = len(with_risk[with_risk["risk_level"] == "baixo"])

# ── BOTÃO IA ──
if st.button("🤖 Explicar com IA"):
    descs = []
    if sel_dept_pt != "Todos": descs.append(f"departamento={sel_dept_pt}")
    if sel_role_pt != "Todos": descs.append(f"cargo={sel_role_pt}")
    if sel_gender_pt != "Todos": descs.append(f"gênero={sel_gender_pt}")
    if sel_risk != "Todos": descs.append(f"risco={sel_risk}")
    if sel_overtime_pt != "Todos": descs.append(f"hora_extra={sel_overtime_pt}")
    avg_risk = with_risk["risk_score"].mean() if not with_risk.empty else 0
    prompt = (
        f"Analise os dados do dashboard com filtros: {', '.join(descs) or 'sem filtros'}. "
        f"Total: {total}. Crítico: {critical}, alto: {high_r}, médio: {medium_r}, baixo: {low_r}. "
        f"Risco médio: {avg_risk:.1%}. Explique e sugira ações."
    )
    with st.spinner("Gerando análise com IA..."):
        try:
            resp = httpx.post(get_api_url("/agent/chat"), json={"message": prompt}, timeout=60)
            resp.raise_for_status()
            st.session_state["ia_explanation_text"] = resp.json()["response"]
        except Exception as e:
            st.session_state["ia_explanation_text"] = f"Erro ao gerar análise: {e}"

if st.session_state.get("ia_explanation_text"):
    with st.expander("🤖 Análise por IA dos dados filtrados", expanded=True):
        st.markdown(st.session_state["ia_explanation_text"].replace("$", r"\$"))

st.markdown("---")

# ── INDICADORES-CHAVE (KPI Cards com fundo colorido) ──
st.markdown("### 📈 Indicadores-chave")


def kpi_card(icon: str, label: str, value: str, bg_color: str, border_color: str, text_color: str = "#FAFAFA") -> str:
    """KPI card com fundo colorido."""
    return (
        f"<div style='background:{bg_color}; border-left: 4px solid {border_color}; "
        f"border-radius:8px; padding:1rem 1.2rem; height:100%;'>"
        f"<div style='color:{text_color}; opacity:0.85; font-size:0.75rem; text-transform:uppercase; "
        f"letter-spacing:0.5px; margin-bottom:0.3rem;'>{icon} {label}</div>"
        f"<div style='color:{text_color}; font-size:1.8rem; font-weight:700; line-height:1;'>{value}</div>"
        f"</div>"
    )


# Linha 1 — Distribuição por Nível de Risco
c1, c2, c3, c4, c5 = st.columns(5)
kpi_rows_1 = [
    (c1, "👥", "Total", f"{total:,}", "#1E293B", "#00BCD4"),
    (c2, "🔴", "Crítico", f"{critical:,}", "#3F1515", "#DC2626"),
    (c3, "🟠", "Alto", f"{high_r:,}", "#3F2A0F", "#D97706"),
    (c4, "🔵", "Médio", f"{medium_r:,}", "#13233F", "#3B82F6"),
    (c5, "🟢", "Baixo", f"{low_r:,}", "#0F2A1E", "#10B981"),
]
for col, icon, label, value, bg, border in kpi_rows_1:
    with col:
        st.markdown(kpi_card(icon, label, value, bg, border), unsafe_allow_html=True)

st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

# Linha 2 — Indicadores de Negócio
if not filtered.empty:
    avg_risk = with_risk["risk_score"].mean() if not with_risk.empty else 0
    avg_salary = filtered["monthly_income"].mean() if "monthly_income" in filtered.columns else 0
    avg_tenure = filtered["years_at_company"].mean() if "years_at_company" in filtered.columns else 0
    overtime_pct = (filtered["over_time"] == "Yes").mean() * 100 if "over_time" in filtered.columns else 0
    at_risk_pct = (critical + high_r) / total * 100 if total > 0 else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_rows_2 = [
        (k1, "⚠️", "% Alto/Crítico", f"{at_risk_pct:.1f}%", "#2A1B1B", "#DC2626"),
        (k2, "📊", "Risco Médio", f"{avg_risk:.1%}", "#1B1F2A", "#00BCD4"),
        (k3, "💰", "Salário Médio", f"R$ {avg_salary:,.0f}", "#1B2A24", "#10B981"),
        (k4, "⏱️", "Tempo Médio", f"{avg_tenure:.1f} anos", "#1F1B2A", "#8B5CF6"),
        (k5, "⏰", "Fazem Hora Extra", f"{overtime_pct:.0f}%", "#2A2318", "#D97706"),
    ]
    for col, icon, label, value, bg, border in kpi_rows_2:
        with col:
            st.markdown(kpi_card(icon, label, value, bg, border), unsafe_allow_html=True)

st.markdown("---")

# ── HELPER: tabela visual com opacidade proporcional ──

def render_risk_bar_table(
    labels: list,
    values: list,
    counts: list,
    first_col_title: str = "Item",
    value_title: str = "Risco",
):
    """Tabela compacta com barra proporcional de 0 a 100%.

    - labels: rotulos (ex: departamentos, cargos)
    - values: valores 0-1 (%)
    - counts: quantidade por linha
    - barra sempre vai de 0% a 100% (escala fixa)
    """

    def color_for(v: float) -> str:
        """Cor baseada no nível de risco (0-1) — mesma paleta da tabela de distribuição."""
        if v < 0.2:
            return "#10B981"   # Baixo — verde
        elif v < 0.4:
            return "#3B82F6"   # Médio — azul
        elif v < 0.7:
            return "#F59E0B"   # Alto — laranja
        return "#DC2626"       # Crítico — vermelho

    # Header da tabela — 3 colunas (sem "Pessoas")
    header_html = (
        "<div style='display:grid; grid-template-columns: 1.5fr 0.9fr 2fr; gap:0.6rem; "
        "padding: 0.5rem 0.5rem; border-bottom: 1px solid rgba(45,55,72,0.6); "
        "color:#94A3B8; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.5px; font-weight:700;'>"
        f"<div>{first_col_title}</div>"
        f"<div style='text-align:right;'>{value_title}</div>"
        "<div>Intensidade</div>"
        "</div>"
    )

    # Linhas — barra sempre de 0 a 100%
    rows_html = ""
    for label, val, cnt in zip(labels, values, counts):
        color = color_for(val)
        bar_width = val * 100
        r_hex, g_hex, b_hex = color[1:3], color[3:5], color[5:7]
        # Track escuro (0 → 100%) + barra colorida proporcional + label "100%" à direita
        bar_html = (
            f"<div style='background: rgba(15,20,32,0.6); border: 1px solid rgba(45,55,72,0.5); "
            f"border-radius:5px; height: 28px; position:relative; overflow:hidden; width:100%;'>"
            f"<div style='background: {color}; height:100%; width:{bar_width}%; border-radius:4px; "
            f"box-shadow: 0 0 8px rgba({int(r_hex,16)}, {int(g_hex,16)}, {int(b_hex,16)}, 0.4);'></div>"
            f"<div style='position:absolute; right:8px; top:50%; transform:translateY(-50%); "
            f"color:#64748B; font-size:0.7rem;'>100%</div>"
            f"</div>"
        )
        rows_html += (
            "<div style='display:grid; grid-template-columns: 1.5fr 0.9fr 2fr; gap:0.6rem; "
            "padding: 1.4rem 0.7rem; border-bottom: 1px solid rgba(45,55,72,0.4); align-items:center;'>"
            f"<div style='color:#FAFAFA; font-weight:600; font-size:0.95rem;'>{label}</div>"
            f"<div style='text-align:right; color:{color}; font-weight:700; font-size:1rem;'>{val:.1%}</div>"
            f"{bar_html}"
            "</div>"
        )

    # Remover border-bottom do último item — mesmo padrão da col2
    if rows_html:
        parts = rows_html.rsplit("border-bottom: 1px solid rgba(45,55,72,0.4);", 1)
        rows_html = "border-bottom: none;".join(parts) if len(parts) == 2 else parts[0]

    # Wrapper interno azul escuro — mesmo padrão da col2 (padding simétrico)
    return (
        f"<div style='background:#0F1420; border:1px solid #2D3748; "
        f"border-radius:6px; padding: 0.4rem 0.6rem;'>"
        f"{header_html}{rows_html}"
        f"</div>"
    )


# Paleta unificada (mesma do tema dark)
COLOR_LOW = "#10B981"      # verde — baixo
COLOR_MED = "#3B82F6"      # azul — médio
COLOR_HIGH = "#F59E0B"     # laranja — alto
COLOR_CRITICAL = "#DC2626" # vermelho — crítico
COLOR_PRIMARY = "#00BCD4"  # ciano primário (tema)
COLOR_CHART_BLUE = "#3B82F6"  # azul médio — usado em gráficos "neutros" (histograma, linha)
BG_PAPER = "rgba(0,0,0,0)" # transparente — herda fundo da caixa interna
BG_PLOT = "rgba(0,0,0,0)"
TEXT_MAIN = "#FAFAFA"
TEXT_MUTED = "#94A3B8"
GRID_COLOR = "rgba(45,55,72,0.5)"


def apply_chart_theme(fig, height: int = 380):
    """Aplica tema escuro unificado a qualquer figure Plotly."""
    fig.update_layout(
        height=height,
        paper_bgcolor=BG_PAPER,
        plot_bgcolor=BG_PLOT,
        font=dict(color=TEXT_MAIN, family="sans-serif"),
        title_text="",  # título vazio — renderizado fora no header da caixinha
        xaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED, size=11), title_font=dict(color=TEXT_MUTED, size=12)),
        yaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED, size=11), title_font=dict(color=TEXT_MUTED, size=12)),
        margin=dict(t=10, b=40, l=40, r=30),
        legend=dict(font=dict(color=TEXT_MAIN, size=11)),
    )
    return fig


def chart_box_header(title: str):
    """Header estilo 'PROFISSIONAL' do perfil — caps, cinza, com divisor."""
    st.markdown(
        f"<div style='color:#94A3B8; font-size:0.75rem; text-transform:uppercase; "
        f"letter-spacing:0.6px; margin-bottom:0.6rem; font-weight:700;'>"
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def inner_box_start():
    """Abre a caixa interna (mais escura) onde vai o gráfico/tabela."""
    st.markdown(
        "<div style='background:#0F1420; border:1px solid #2D3748; "
        "border-radius:6px; padding: 0.5rem;'>",
        unsafe_allow_html=True,
    )


def inner_box_end():
    """Fecha a caixa interna."""
    st.markdown("</div>", unsafe_allow_html=True)


# CSS global — só aplica no stVerticalBlock que é filho direto de stLayoutWrapper
# (padrão do st.container(border=True) no Streamlit moderno)
apply_theme()


# ── SEÇÃO 1 — Risco Geral ──
if not with_risk.empty:
    st.markdown("### 📊 Análise de Risco")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        with st.container(border=True):
            chart_box_header("Risco Médio por Departamento")
            dept_risk = with_risk.groupby("dept_pt")["risk_score"].agg(["mean", "count"]).reset_index()
            dept_risk.columns = ["Departamento", "Risco Médio", "Colaboradores"]
            dept_risk = dept_risk.sort_values("Risco Médio", ascending=False)
            st.markdown(
                render_risk_bar_table(
                    labels=dept_risk["Departamento"].tolist(),
                    values=dept_risk["Risco Médio"].tolist(),
                    counts=dept_risk["Colaboradores"].tolist(),
                    first_col_title="Departamento",
                    value_title="Risco Médio",
                ),
                unsafe_allow_html=True,
            )

    with col_g2:
        with st.container(border=True):
            chart_box_header("Distribuição de Risco por Departamento")

            risk_order = ["baixo", "médio", "alto", "crítico"]
            risk_order_pt = ["Baixo", "Médio", "Alto", "Crítico"]
            risk_colors = {
                "Baixo": "#10B981",
                "Médio": "#3B82F6",
                "Alto": "#F59E0B",
                "Crítico": "#DC2626",
            }
            pivot = (with_risk.groupby(["dept_pt", "risk_level"]).size()
                     .unstack(fill_value=0)
                     .reindex(columns=risk_order, fill_value=0))
            pivot.columns = risk_order_pt
            totals = pivot.sum(axis=1)
            pivot_pct = pivot.div(totals, axis=0) * 100
            # Ordena pelo % de Crítico (decrescente) — departamentos mais problemáticos no topo
            pivot_pct = pivot_pct.sort_values("Crítico", ascending=False)
            pivot = pivot.loc[pivot_pct.index]
            totals = totals.loc[pivot_pct.index]

            header_html = (
                "<div style='display:grid; grid-template-columns: 1.6fr repeat(4, 1fr) 0.9fr; gap:0.3rem; "
                "padding: 0.5rem 0.5rem; border-bottom: 1px solid rgba(45,55,72,0.6); "
                "color:#94A3B8; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.5px; font-weight:700;'>"
                "<div>Departamento</div>"
                f"<div style='text-align:center; color:{risk_colors['Baixo']};'>● Baixo</div>"
                f"<div style='text-align:center; color:{risk_colors['Médio']};'>● Médio</div>"
                f"<div style='text-align:center; color:{risk_colors['Alto']};'>● Alto</div>"
                f"<div style='text-align:center; color:{risk_colors['Crítico']};'>● Crítico</div>"
                "<div style='text-align:right;'>Total</div>"
                "</div>"
            )

            rows_html = ""
            for dept in pivot.index:
                row_cells = f"<div style='color:#FAFAFA; font-weight:600; font-size:0.9rem;'>{dept}</div>"
                for lvl in risk_order_pt:
                    pct = pivot_pct.loc[dept, lvl]
                    count = int(pivot.loc[dept, lvl])
                    color = risk_colors[lvl]
                    opacity = min(pct / 50, 1.0)
                    row_cells += (
                        f"<div style='text-align:center; background: rgba({int(color[1:3],16)}, {int(color[3:5],16)}, {int(color[5:7],16)}, {opacity * 0.25}); "
                        f"border-radius:4px; padding: 0.3rem 0.2rem;'>"
                        f"<div style='color:{color}; font-weight:700; font-size:0.95rem;'>{pct:.1f}%</div>"
                        f"<div style='color:#64748B; font-size:0.7rem;'>{count}</div>"
                        f"</div>"
                    )
                row_cells += f"<div style='text-align:right; color:#94A3B8; font-size:0.9rem; align-self:center;'>{int(totals.loc[dept])}</div>"
                rows_html += (
                    f"<div style='display:grid; grid-template-columns: 1.6fr repeat(4, 1fr) 0.9fr; gap:0.3rem; "
                    f"padding: 0.5rem 0.5rem; border-bottom: 1px solid rgba(45,55,72,0.4); align-items:center;'>"
                    f"{row_cells}"
                    f"</div>"
                )

            # Remover border-bottom do último item (visual mais limpo)
            if rows_html:
                rows_html = rows_html.rsplit("border-bottom: 1px solid rgba(45,55,72,0.4);", 1)
                rows_html = "border-bottom: none;".join(rows_html) if len(rows_html) == 2 else rows_html[0]
            st.markdown(
                f"<div style='background:#0F1420; border:1px solid #2D3748; "
                f"border-radius:6px; padding: 0.4rem 0.6rem 1.2rem 0.6rem;'>{header_html}{rows_html}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── SEÇÃO 2 — Por Cargo e Gênero ──
    st.markdown("### 👥 Por Cargo e Gênero")
    col_g3, col_g4 = st.columns(2)

    with col_g3:
        with st.container(border=True):
            chart_box_header("Top 10 Cargos com Maior Risco Médio")
            role_risk = (with_risk.groupby("role_pt")["risk_score"]
                         .agg(["mean", "count"]).reset_index()
                         .rename(columns={"mean": "Risco Médio", "count": "Colaboradores"}))
            role_risk = role_risk[role_risk["Colaboradores"] >= 3].sort_values("Risco Médio", ascending=True).tail(10)
            if not role_risk.empty:
                max_val = role_risk["Risco Médio"].max()
                fig3 = px.bar(
                    role_risk, x="Risco Médio", y="role_pt", orientation="h",
                    color="Risco Médio",
                    color_continuous_scale=[COLOR_LOW, COLOR_HIGH, COLOR_CRITICAL],
                    text=role_risk["Risco Médio"].apply(lambda x: f"{x:.1%}"),
                    labels={"role_pt": "Cargo"},
                    hover_data={"Colaboradores": True},
                )
                fig3.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_MAIN, size=11))
                apply_chart_theme(fig3, height=360)
                fig3.update_layout(
                    xaxis_tickformat=".0%",
                    coloraxis_showscale=False,
                    xaxis=dict(range=[0, max_val * 1.25], gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                    yaxis=dict(title=None, tickfont=dict(color=TEXT_MAIN, size=11)),
                    margin=dict(l=10, r=80, t=10, b=40),
                )
                st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    with col_g4:
        with st.container(border=True):
            chart_box_header("Risco Médio por Departamento × Gênero")
            gender_dept = (with_risk.groupby(["dept_pt", "gender_pt"])["risk_score"]
                           .mean().reset_index())
            fig4 = px.bar(
                gender_dept, x="dept_pt", y="risk_score", color="gender_pt",
                barmode="group",
                labels={"dept_pt": "Departamento", "risk_score": "Risco Médio", "gender_pt": "Gênero"},
                color_discrete_map={"Masculino": "#8B5CF6", "Feminino": "#3B82F6"},
                text=gender_dept["risk_score"].apply(lambda x: f"{x:.1%}"),
            )
            max_v = gender_dept["risk_score"].max()
            fig4.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_MAIN, size=11))
            apply_chart_theme(fig4, height=360)
            fig4.update_layout(
                yaxis_tickformat=".0%",
                yaxis=dict(range=[0, max_v * 1.25], gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                xaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                margin=dict(t=10, b=40, l=40, r=30),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font=dict(color=TEXT_MAIN, size=11),
                ),
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False, "staticPlot": False})

    st.markdown("---")

    # ── SEÇÃO 3 — Drivers de Risco ──
    st.markdown("### 🎯 Drivers de Risco")
    col_g5, col_g6 = st.columns(2)

    with col_g5:
        with st.container(border=True):
            chart_box_header("Impacto da Hora Extra no Risco")
            overtime_risk = (with_risk.groupby("over_time")
                             .agg(risk_mean=("risk_score", "mean"),
                                  qtd=("risk_score", "count"))
                             .reset_index())
            overtime_risk["label_pt"] = overtime_risk["over_time"].map({"Yes": "Com Hora Extra", "No": "Sem Hora Extra"})
            fig5 = go.Figure()
            fig5.add_trace(go.Bar(
                x=overtime_risk["label_pt"],
                y=overtime_risk["risk_mean"],
                text=[f"<b>{v:.1%}</b><br>{q} colaboradores" for v, q in zip(overtime_risk["risk_mean"], overtime_risk["qtd"])],
                textposition="outside",
                marker_color=[COLOR_CRITICAL if v == "Yes" else COLOR_LOW for v in overtime_risk["over_time"]],
                textfont=dict(color=TEXT_MAIN, size=12),
                cliponaxis=False,
            ))
            max_v = overtime_risk["risk_mean"].max()
            fig5.update_layout(showlegend=False)
            apply_chart_theme(fig5, height=320)
            fig5.update_layout(
                yaxis_tickformat=".0%",
                yaxis=dict(range=[0, max_v * 1.4], gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                xaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
            )
            st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    with col_g6:
        if "monthly_income" in with_risk.columns:
            with st.container(border=True):
                chart_box_header("Risco por Faixa Salarial")
                bins = [0, 2500, 5000, 7500, 10000, 15000, 25000]
                labels = ["Até R$ 2.5k", "R$ 2.5k–5k", "R$ 5k–7.5k", "R$ 7.5k–10k", "R$ 10k–15k", "R$ 15k+"]
                with_risk_copy = with_risk.copy()
                with_risk_copy["faixa_salarial"] = pd.cut(with_risk_copy["monthly_income"], bins=bins, labels=labels)
                salary_risk = (with_risk_copy.groupby("faixa_salarial", observed=True)["risk_score"]
                               .agg(["mean", "count"]).reset_index())
                salary_risk.columns = ["Faixa Salarial", "Risco Médio", "Colaboradores"]
                max_v = salary_risk["Risco Médio"].max()
                fig6 = px.bar(
                    salary_risk, x="Faixa Salarial", y="Risco Médio", color="Risco Médio",
                    color_continuous_scale=[COLOR_LOW, COLOR_HIGH, COLOR_CRITICAL],
                    text=salary_risk["Risco Médio"].apply(lambda x: f"{x:.1%}"),
                    hover_data={"Colaboradores": True},
                )
                fig6.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=TEXT_MAIN, size=12))
                apply_chart_theme(fig6, height=320)
                fig6.update_layout(
                    yaxis_tickformat=".0%",
                    coloraxis_showscale=False,
                    yaxis=dict(range=[0, max_v * 1.25], gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                    xaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                )
                st.plotly_chart(fig6, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    col_g7, col_g8 = st.columns(2)

    with col_g7:
        if "years_at_company" in with_risk.columns:
            with st.container(border=True):
                chart_box_header("Risco por Tempo de Casa")
                tenure_bins = [0, 2, 5, 10, 20, 50]
                tenure_labels = ["0–2 anos", "2–5 anos", "5–10 anos", "10–20 anos", "20+ anos"]
                with_risk_t = with_risk.copy()
                with_risk_t["faixa_tempo"] = pd.cut(with_risk_t["years_at_company"], bins=tenure_bins, labels=tenure_labels, include_lowest=True)
                tenure_risk = (with_risk_t.groupby("faixa_tempo", observed=True)["risk_score"]
                               .agg(["mean", "count"]).reset_index())
                tenure_risk.columns = ["Tempo de Casa", "Risco Médio", "Colaboradores"]
                fig7 = px.line(
                    tenure_risk, x="Tempo de Casa", y="Risco Médio",
                    markers=True,
                    line_shape="spline",
                )
                fig7.update_traces(
                    line=dict(color=COLOR_CHART_BLUE, width=3),
                    marker=dict(size=14, color=COLOR_CHART_BLUE, line=dict(color="#0E1117", width=2)),
                    text=tenure_risk["Risco Médio"].apply(lambda x: f"{x:.1%}"),
                    textposition="top center",
                    textfont=dict(color=TEXT_MAIN, size=11),
                    mode="lines+markers+text",
                )
                max_v = tenure_risk["Risco Médio"].max()
                apply_chart_theme(fig7, height=320)
                fig7.update_layout(
                    yaxis_tickformat=".0%",
                    yaxis=dict(range=[0, max_v * 1.3], gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                    xaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_MUTED)),
                )
                st.plotly_chart(fig7, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    with col_g8:
        with st.container(border=True):
            chart_box_header("Distribuição de Scores de Risco")
            # Histograma com cor por faixa: baixo/médio/alto/crítico
            # Classifica cada score em sua faixa antes de agrupar no histograma
            def _risk_band(score):
                if score < 0.2: return "Baixo"
                if score < 0.4: return "Médio"
                if score < 0.7: return "Alto"
                return "Crítico"
            with_risk_banded = with_risk.copy()
            with_risk_banded["risk_band"] = with_risk_banded["risk_score"].apply(_risk_band)
            band_order = ["Baixo", "Médio", "Alto", "Crítico"]
            band_colors = {
                "Baixo": COLOR_LOW,
                "Médio": COLOR_MED,
                "Alto": COLOR_HIGH,
                "Crítico": COLOR_CRITICAL,
            }

            fig2 = px.histogram(
                with_risk_banded, x="risk_score", nbins=30,
                color="risk_band",
                category_orders={"risk_band": band_order},
                color_discrete_map=band_colors,
                labels={"risk_score": "Probabilidade de Saída", "count": "Colaboradores", "risk_band": "Nível"},
            )
            fig2.add_vline(x=0.2, line_dash="dash", line_color=COLOR_LOW)
            fig2.add_vline(x=0.4, line_dash="dash", line_color=COLOR_MED)
            fig2.add_vline(x=0.7, line_dash="dash", line_color=COLOR_CRITICAL)
            apply_chart_theme(fig2, height=320)
            # Ajuste fino: legenda no topo-direito, barras empilhadas
            fig2.update_layout(
                barmode="stack",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    st.markdown("---")

    # ── TABELA ──
    st.markdown("### 🔴 Colaboradores Mais Críticos")
    st.caption("Clique em 🔍 Ver detalhes para abrir a análise do colaborador")

    # Mapeamento de cor por nível de risco
    LEVEL_COLORS = {
        "baixo": COLOR_LOW,
        "médio": COLOR_MED,
        "alto": COLOR_HIGH,
        "crítico": COLOR_CRITICAL,
    }

    # ── Paginação ──
    PAGE_SIZE = 10
    all_critical = with_risk.sort_values("risk_score", ascending=False).reset_index(drop=True)
    total_rows = len(all_critical)
    total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)

    if "dashboard_page" not in st.session_state:
        st.session_state.dashboard_page = 1
    # Reset se filtros mudaram e estamos numa página inexistente
    if st.session_state.dashboard_page > total_pages:
        st.session_state.dashboard_page = 1

    current_page = st.session_state.dashboard_page
    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE

    with st.container(border=True):
        top = all_critical.iloc[start_idx:end_idx]

        # Header
        table_header = (
            "<div style='display:grid; grid-template-columns: 1fr 0.5fr 1.8fr 1.5fr 0.9fr 1fr 0.9fr 0.7fr 0.9fr 1fr; "
            "gap:0.5rem; padding: 0.6rem 0.5rem; border-bottom: 1px solid rgba(45,55,72,0.6); "
            "color:#94A3B8; font-size:0.68rem; text-transform:uppercase; letter-spacing:0.5px; font-weight:700;'>"
            "<div>Ação</div>"
            "<div style='text-align:right;'>ID</div>"
            "<div>Cargo</div>"
            "<div>Departamento</div>"
            "<div>Gênero</div>"
            "<div style='text-align:right;'>Salário</div>"
            "<div style='text-align:center;'>H.Extra</div>"
            "<div style='text-align:center;'>Anos</div>"
            "<div style='text-align:right;'>Score</div>"
            "<div style='text-align:center;'>Nível</div>"
            "</div>"
        )

        # Linhas
        table_rows = ""
        for _, r in top.iterrows():
            eid = int(r["id"])
            ot = OVERTIME_PT.get(r.get("over_time", ""), r.get("over_time", ""))
            level = (r.get("risk_level") or "").lower()
            level_color = LEVEL_COLORS.get(level, "#94A3B8")
            level_pt = level.capitalize()
            score = r["risk_score"]
            r_hex, g_hex, b_hex = level_color[1:3], level_color[3:5], level_color[5:7]
            badge_bg = f"rgba({int(r_hex,16)}, {int(g_hex,16)}, {int(b_hex,16)}, 0.2)"

            table_rows += (
                "<div style='display:grid; grid-template-columns: 1fr 0.5fr 1.8fr 1.5fr 0.9fr 1fr 0.9fr 0.7fr 0.9fr 1fr; "
                "gap:0.5rem; padding: 0.7rem 0.5rem; border-bottom: 1px solid rgba(45,55,72,0.4); "
                "align-items:center;'>"
                f"<div><a href='/Colaborador?employee_id={eid}' target='_self' "
                f"style='color:#00BCD4; text-decoration:none; font-size:0.82rem; font-weight:600;'>🔍 Ver detalhes</a></div>"
                f"<div style='text-align:right; color:#94A3B8; font-size:0.85rem;'>{eid}</div>"
                f"<div style='color:#FAFAFA; font-size:0.88rem;'>{tr_role(r.get('job_role', ''))}</div>"
                f"<div style='color:#FAFAFA; font-size:0.88rem;'>{tr_dept(r.get('department', ''))}</div>"
                f"<div style='color:#94A3B8; font-size:0.85rem;'>{tr_gender(r.get('gender', ''))}</div>"
                f"<div style='text-align:right; color:#FAFAFA; font-size:0.88rem;'>R$ {r.get('monthly_income', 0):,}</div>"
                f"<div style='text-align:center; color:#94A3B8; font-size:0.85rem;'>{ot}</div>"
                f"<div style='text-align:center; color:#94A3B8; font-size:0.85rem;'>{r.get('years_at_company', '')}</div>"
                f"<div style='text-align:right; color:{level_color}; font-weight:700; font-size:0.95rem;'>{score:.1%}</div>"
                f"<div style='text-align:center;'>"
                f"<span style='background:{badge_bg}; color:{level_color}; padding:0.25rem 0.7rem; "
                f"border-radius:4px; font-weight:700; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.5px;'>"
                f"{level_pt}</span></div>"
                "</div>"
            )

        st.markdown(
            f"<div style='background:#0F1420; border:1px solid #2D3748; border-radius:6px; "
            f"padding: 0.4rem 0.6rem 1.2rem 0.6rem;'>{table_header}{table_rows}</div>",
            unsafe_allow_html=True,
        )

        # ── Controles de paginação ──
        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])

        with nav_col1:
            if st.button("← Anterior", disabled=(current_page <= 1), use_container_width=True, key="prev_page"):
                st.session_state.dashboard_page = max(1, current_page - 1)
                st.rerun()

        with nav_col2:
            st.markdown(
                f"<div style='text-align:center; color:#94A3B8; font-size:0.9rem; padding-top:0.4rem;'>"
                f"Página <b style='color:#FAFAFA;'>{current_page}</b> de <b style='color:#FAFAFA;'>{total_pages}</b> "
                f"— mostrando {start_idx + 1}–{min(end_idx, total_rows)} de {total_rows} colaboradores"
                f"</div>",
                unsafe_allow_html=True,
            )

        with nav_col3:
            if st.button("Próxima →", disabled=(current_page >= total_pages), use_container_width=True, key="next_page"):
                st.session_state.dashboard_page = min(total_pages, current_page + 1)
                st.rerun()

    # ── EXPORT CSV FILTRADO ──
    st.markdown(" ")
    csv_export = filtered.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 Baixar CSV dos dados filtrados",
        data=csv_export,
        file_name=f"colaboradores_filtrados_{len(filtered)}.csv",
        mime="text/csv",
        use_container_width=True,
        help="Exporta todos os colaboradores que passam pelos filtros ativos (não só a página visível).",
    )
