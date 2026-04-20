"""Página 7 — Simulador 'E se?'.

Seleciona um colaborador, permite alterar atributos-chave via sliders
e mostra o novo risco previsto — SEM tocar no banco (usa /predict/simulate).
"""

import httpx
import streamlit as st

from components.sidebar import get_api_url
from components.theme import apply_theme
from components.translations import (
    format_employee_option, tr_dept, tr_role,
)

st.set_page_config(page_title="Simulador", page_icon="🎛️", layout="wide")
st.title("🎛️ Simulador")
st.caption(
    "Escolha um colaborador, altere atributos como salário, hora extra e tempo "
    "sem promoção, e veja como o risco muda em tempo real."
)

# CSS
apply_theme()


@st.cache_data(ttl=60)
def load_employees_light():
    emps = []
    page = 1
    while True:
        try:
            r = httpx.get(
                get_api_url("/employees"),
                params={"page_size": 100, "page": page},
                timeout=15,
            )
            r.raise_for_status()
            d = r.json()
            emps.extend(d["employees"])
            if len(emps) >= d["total"]:
                break
            page += 1
        except Exception:
            break
    return emps


employees = load_employees_light()
if not employees:
    st.warning("Sem dados.")
    st.stop()

# ── FILTROS + SELEÇÃO ──
st.markdown("### 🎯 Escolha um colaborador")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    dept_raw_options = sorted({e["department"] for e in employees if e.get("department")})
    dept_pt_to_raw = {tr_dept(d): d for d in dept_raw_options}
    dept_pt_options = ["Todos"] + sorted(dept_pt_to_raw.keys())
    sel_dept_pt = st.selectbox("Departamento", dept_pt_options, key="sim_dept")

filtered_emps = employees
if sel_dept_pt != "Todos":
    sel_dept_raw = dept_pt_to_raw[sel_dept_pt]
    filtered_emps = [e for e in filtered_emps if e.get("department") == sel_dept_raw]

with col_f2:
    role_raw_options = sorted({e["job_role"] for e in filtered_emps if e.get("job_role")})
    role_pt_to_raw = {tr_role(r): r for r in role_raw_options}
    role_pt_options = ["Todos"] + sorted(role_pt_to_raw.keys())
    sel_role_pt = st.selectbox("Cargo", role_pt_options, key="sim_role")

if sel_role_pt != "Todos":
    sel_role_raw = role_pt_to_raw[sel_role_pt]
    filtered_emps = [e for e in filtered_emps if e.get("job_role") == sel_role_raw]

with col_f3:
    if not filtered_emps:
        st.selectbox("Colaborador", ["— Nenhum —"], disabled=True, key="sim_sel_empty")
        st.warning("Nenhum colaborador com esses filtros.")
        st.stop()

    # Pré-seleção via session_state (vindo da página Colaborador)
    preselect_id = st.session_state.pop("simulator_preselect_id", None)
    default_index = 0
    if preselect_id is not None:
        for i, e in enumerate(filtered_emps):
            if e.get("id") == preselect_id:
                default_index = i
                break

    sel = st.selectbox(
        "Colaborador",
        filtered_emps,
        index=default_index,
        format_func=lambda e: format_employee_option(e),
        key="sim_sel",
    )

emp_id = sel["id"]

# Busca dados completos (com fields necessários pro simulador)
emp = httpx.get(get_api_url(f"/employees/{emp_id}"), timeout=10).json()

# ── SLIDERS ──
st.markdown("### 🎚️ Altere os atributos")
with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        current_income = int(emp.get("monthly_income", 5000) or 5000)
        new_income = st.slider(
            "Salário Mensal (R\\$)",
            1000, 25000,
            value=current_income,
            step=100,
            help="Ajustar salário geralmente reduz risco quando a insatisfação vem de remuneração.",
        )
        delta_income = new_income - current_income
        if delta_income != 0:
            sign = "+" if delta_income > 0 else "-"
            st.caption(f"Variação: {sign}R\\$ {abs(delta_income):,}")

    with col2:
        new_overtime = st.selectbox(
            "Hora Extra",
            ["Não", "Sim"],
            index=0 if emp.get("over_time") == "No" else 1,
            help="Remover hora extra costuma ser uma das ações mais efetivas de retenção.",
        )
        new_overtime_val = "Yes" if new_overtime == "Sim" else "No"

    with col3:
        new_years_since_promo = st.slider(
            "Anos sem promoção",
            0, 15,
            value=int(emp.get("years_since_last_promotion", 0) or 0),
            help="Promover (=0) costuma melhorar percepção de carreira.",
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        new_job_sat = st.slider(
            "Satisfação no Trabalho (1-4)",
            1, 4,
            value=int(emp.get("job_satisfaction", 3) or 3),
            help="Ações como feedback estruturado, mentoria e redesenho de atribuições elevam essa pontuação.",
        )
    with col5:
        new_wlb = st.slider(
            "Equilíbrio Vida-Trabalho (1-4)",
            1, 4,
            value=int(emp.get("work_life_balance", 3) or 3),
            help="Reduzir sobrecarga, permitir flexibilidade e remover reuniões desnecessárias eleva essa pontuação.",
        )
    with col6:
        new_level = st.slider(
            "Nível do Cargo (1-5)",
            1, 5,
            value=int(emp.get("job_level", 2) or 2),
            help="Promoção eleva o nível do cargo — simule o impacto de uma promoção.",
        )

    col7, col8, col9 = st.columns(3)
    with col7:
        new_env_sat = st.slider(
            "Satisfação com Ambiente (1-4)",
            1, 4,
            value=int(emp.get("environment_satisfaction", 3) or 3),
            help="Remanejamento de equipe, mudança de gestor ou cultura de time elevam essa pontuação.",
        )
    with col8:
        new_training = st.slider(
            "Treinamentos no último ano",
            0, 10,
            value=int(emp.get("training_times_last_year", 2) or 2),
            help="Investir em capacitação costuma melhorar percepção de desenvolvimento e retenção.",
        )
    with col9:
        travel_map_pt = {"Não viaja": "Non-Travel", "Viaja raramente": "Travel_Rarely", "Viaja frequentemente": "Travel_Frequently"}
        travel_current = emp.get("business_travel", "Travel_Rarely")
        travel_current_pt = next((k for k, v in travel_map_pt.items() if v == travel_current), "Viaja raramente")
        new_travel_pt = st.selectbox(
            "Frequência de Viagens",
            list(travel_map_pt.keys()),
            index=list(travel_map_pt.keys()).index(travel_current_pt),
            help="Reduzir viagens pode aliviar carga sobre quem está em atrito com rotina intensa de deslocamento.",
        )
        new_travel_val = travel_map_pt[new_travel_pt]

    col10, col11, col12 = st.columns(3)
    with col10:
        new_stock = st.slider(
            "Nível de Stock Options (0-3)",
            0, 3,
            value=int(emp.get("stock_option_level", 0) or 0),
            help="Stock options são um dos fatores mais fortes de retenção de longo prazo.",
        )
    with col11:
        new_salary_hike = st.slider(
            "% Último Aumento",
            0, 25,
            value=int(emp.get("percent_salary_hike", 11) or 11),
            help="Percentual do último reajuste salarial.",
        )
    with col12:
        new_job_involv = st.slider(
            "Envolvimento no Trabalho (1-4)",
            1, 4,
            value=int(emp.get("job_involvement", 3) or 3),
            help="Atribuir responsabilidades mais significativas e autonomia costuma elevar essa pontuação.",
        )

# ── MONTA OVERRIDES — só campos que realmente mudaram vs o estado atual ──
current = {
    "monthly_income": current_income,
    "over_time": emp.get("over_time"),
    "years_since_last_promotion": int(emp.get("years_since_last_promotion", 0) or 0),
    "job_satisfaction": int(emp.get("job_satisfaction", 3) or 3),
    "work_life_balance": int(emp.get("work_life_balance", 3) or 3),
    "job_level": int(emp.get("job_level", 2) or 2),
    "environment_satisfaction": int(emp.get("environment_satisfaction", 3) or 3),
    "training_times_last_year": int(emp.get("training_times_last_year", 2) or 2),
    "business_travel": emp.get("business_travel", "Travel_Rarely"),
    "stock_option_level": int(emp.get("stock_option_level", 0) or 0),
    "percent_salary_hike": int(emp.get("percent_salary_hike", 11) or 11),
    "job_involvement": int(emp.get("job_involvement", 3) or 3),
}
new_values = {
    "monthly_income": new_income,
    "over_time": new_overtime_val,
    "years_since_last_promotion": new_years_since_promo,
    "job_satisfaction": new_job_sat,
    "work_life_balance": new_wlb,
    "job_level": new_level,
    "environment_satisfaction": new_env_sat,
    "training_times_last_year": new_training,
    "business_travel": new_travel_val,
    "stock_option_level": new_stock,
    "percent_salary_hike": new_salary_hike,
    "job_involvement": new_job_involv,
}
# Filtra: só overrides de valores que divergem do atual (evita snapping/rounding bugs)
overrides = {k: v for k, v in new_values.items() if current.get(k) != v}

# ── CALCULA BASELINE E CENÁRIO VIA DRY-RUN ──
with st.spinner("Simulando..."):
    # Baseline: simulação sem overrides = predição do estado atual
    try:
        r_base = httpx.post(
            get_api_url("/predict/simulate"),
            json={"employee_id": int(emp_id), "overrides": {}},
            timeout=30,
        )
        r_base.raise_for_status()
        baseline = r_base.json()
    except Exception as e:
        st.error(f"Erro ao calcular baseline: {e}")
        st.stop()

    # Se nada mudou, cenário = baseline (sem chamada extra)
    if not overrides:
        scenario = baseline
    else:
        try:
            r_sim = httpx.post(
                get_api_url("/predict/simulate"),
                json={"employee_id": int(emp_id), "overrides": overrides},
                timeout=30,
            )
            r_sim.raise_for_status()
            scenario = r_sim.json()
        except Exception as e:
            st.error(f"Erro ao simular cenário: {e}")
            st.stop()

# ── Visualização: baseline vs cenário ──
st.markdown("### 📊 Baseline vs Cenário")


def risk_color(level: str) -> str:
    return {"baixo": "#10B981", "médio": "#3B82F6", "alto": "#F59E0B", "crítico": "#DC2626"}.get(level, "#6B7280")


base_prob = baseline["attrition_probability"]
scenario_prob = scenario["attrition_probability"]
base_level = baseline["risk_level"]
scenario_level = scenario["risk_level"]
delta = scenario_prob - base_prob
delta_pct_points = delta * 100

delta_color = "#10B981" if delta < 0 else ("#DC2626" if delta > 0 else "#94A3B8")
delta_sign = "+" if delta > 0 else ""

with st.container(border=True):
    # Layout com flex — 2 tiles lado a lado (centralizados, largura limitada) com seta no meio
    tiles_html = (
        f"<div style='display:flex; align-items:stretch; gap:0.8rem; justify-content:center;"
        f" max-width:85%; margin:0 auto; padding-bottom:1rem;'>"
        # Baseline
        f"<div style='flex:1; background:#0F1420; border:1px solid #2D3748; border-radius:8px;"
        f" padding:1.1rem; text-align:center; display:flex; flex-direction:column; justify-content:center;'>"
        f"<div style='color:#94A3B8; font-size:0.75rem; text-transform:uppercase;"
        f" letter-spacing:0.5px; margin-bottom:0.4rem;'>Baseline (atual)</div>"
        f"<div style='color:{risk_color(base_level)}; font-size:2.4rem; font-weight:700; line-height:1.1;'>"
        f"{base_prob:.1%}</div>"
        f"<div style='color:#CBD5E1; font-size:0.95rem; margin-top:0.3rem;'>{base_level.upper()}</div>"
        # Espaço reservado pra alinhar com o delta do cenário
        f"<div style='font-size:0.9rem; margin-top:0.4rem; visibility:hidden;'>placeholder</div>"
        f"</div>"
        # Seta no meio (sem ocupar flex)
        f"<div style='display:flex; align-items:center; color:#94A3B8; font-size:2rem; padding:0 0.5rem;'>→</div>"
        # Cenário
        f"<div style='flex:1; background:#0F1420; border:1px solid #2D3748; border-radius:8px;"
        f" padding:1.1rem; text-align:center; display:flex; flex-direction:column; justify-content:center;'>"
        f"<div style='color:#94A3B8; font-size:0.75rem; text-transform:uppercase;"
        f" letter-spacing:0.5px; margin-bottom:0.4rem;'>Cenário</div>"
        f"<div style='color:{risk_color(scenario_level)}; font-size:2.4rem; font-weight:700; line-height:1.1;'>"
        f"{scenario_prob:.1%}</div>"
        f"<div style='color:#CBD5E1; font-size:0.95rem; margin-top:0.3rem;'>{scenario_level.upper()}</div>"
        f"<div style='color:{delta_color}; font-size:0.9rem; margin-top:0.4rem; font-weight:700;'>"
        f"{delta_sign}{delta_pct_points:.1f} p.p.</div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(tiles_html, unsafe_allow_html=True)

# ── Barras comparativas ──
import plotly.graph_objects as go

# Cada barra em uma categoria x — sem legenda, cada coluna já identifica
fig = go.Figure(go.Bar(
    x=["Baseline", "Cenário"],
    y=[base_prob * 100, scenario_prob * 100],
    marker_color=[risk_color(base_level), risk_color(scenario_level)],
    text=[f"{base_prob:.1%}", f"{scenario_prob:.1%}"],
    textposition="outside",
    textfont=dict(size=14, color="#FAFAFA"),
))
fig.update_layout(
    height=280, showlegend=False,
    yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="rgba(51,65,85,0.3)",
               tickfont=dict(color="#CBD5E1")),
    xaxis=dict(tickfont=dict(color="#FAFAFA", size=13)),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=30, b=30, l=40, r=20),
    bargap=0.5,
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Resumo textual ──
st.markdown("### 💡 Resumo do impacto")
# `overrides` já contém só os campos que divergem do atual
changed = overrides

with st.container(border=True):
    if not changed:
        st.info("Nenhum atributo foi alterado — o cenário é igual ao baseline.")
    else:
        mudancas = []
        if "monthly_income" in changed:
            mudancas.append(f"salário R\\${current['monthly_income']:,} → R\\${new_income:,}")
        if "over_time" in changed:
            mudancas.append(f"hora extra: {'Sim' if current['over_time']=='Yes' else 'Não'} → {new_overtime}")
        if "years_since_last_promotion" in changed:
            mudancas.append(f"anos sem promoção: {current['years_since_last_promotion']} → {new_years_since_promo}")
        if "job_satisfaction" in changed:
            mudancas.append(f"satisfação: {current['job_satisfaction']} → {new_job_sat}")
        if "work_life_balance" in changed:
            mudancas.append(f"equilíbrio: {current['work_life_balance']} → {new_wlb}")
        if "job_level" in changed:
            mudancas.append(f"nível: {current['job_level']} → {new_level}")

        direction = "reduziria" if delta < 0 else "aumentaria"
        verb_color = "#10B981" if delta < 0 else "#DC2626"
        if abs(delta_pct_points) < 0.1:
            st.info(f"Alterando **{', '.join(mudancas)}**, a probabilidade praticamente não muda "
                    "(o modelo pondera vários fatores — tente mudanças maiores).")
        else:
            st.markdown(
                f"Alterando **{', '.join(mudancas)}**, a probabilidade de saída "
                f"<span style='color:{verb_color}; font-weight:700;'>{direction} "
                f"em {abs(delta_pct_points):.1f} p.p.</span>",
                unsafe_allow_html=True,
            )
