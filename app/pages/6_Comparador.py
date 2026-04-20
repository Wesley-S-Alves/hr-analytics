"""Página 6 — Comparador de Colaboradores (2-3 lado a lado)."""

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.sidebar import get_api_url
from components.theme import apply_theme
from components.translations import (
    tr_dept, tr_role, tr_gender, tr_marital, tr_travel,
    tr_overtime, tr_satisfaction,
)

st.set_page_config(page_title="Comparador", page_icon="🆚", layout="wide")
st.title("🆚 Comparador de Colaboradores")
st.caption(
    "Compare 2 ou 3 colaboradores lado a lado — perfil, risco, SHAP e salário. "
    "Útil para priorização de ações de retenção."
)

# CSS do tema
apply_theme()


@st.cache_data(ttl=60)
def load_employees():
    employees = []
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
            employees.extend(d["employees"])
            if len(employees) >= d["total"]:
                break
            page += 1
        except Exception:
            break
    return pd.DataFrame(employees)


df_all = load_employees()
if df_all.empty:
    st.warning("Sem dados disponíveis.")
    st.stop()

# ── FILTROS — facilitam encontrar colaboradores do mesmo grupo ──
st.markdown("### 🔎 Filtros")
col_f1, col_f2 = st.columns(2)
with col_f1:
    depts = ["Todos"] + sorted(df_all["department"].dropna().unique().tolist())
    dept_options = ["Todos"] + sorted({tr_dept(d) for d in depts if d != "Todos"})
    sel_dept_pt = st.selectbox("Departamento", dept_options, key="cmp_dept")

# Aplicar filtro de departamento já pra afetar as opções de cargo
if sel_dept_pt != "Todos":
    df_filtered = df_all[df_all["department"].apply(tr_dept) == sel_dept_pt]
else:
    df_filtered = df_all

with col_f2:
    roles = sorted(df_filtered["job_role"].dropna().unique().tolist())
    role_options = ["Todos"] + sorted({tr_role(r) for r in roles})
    sel_role_pt = st.selectbox("Cargo", role_options, key="cmp_role")

if sel_role_pt != "Todos":
    df_filtered = df_filtered[df_filtered["job_role"].apply(tr_role) == sel_role_pt]

# ── SELEÇÃO ──
st.markdown(f"### 🎯 Escolha 2 ou 3 colaboradores  ·  {len(df_filtered)} disponíveis")

if len(df_filtered) < 2:
    st.warning("Apenas 1 colaborador atende aos filtros. Ajuste os filtros para comparar pelo menos 2.")
    st.stop()

options = df_filtered["id"].tolist()


def _format(eid):
    row = df_filtered[df_filtered["id"] == eid].iloc[0]
    r_raw = row.get("risk_level") or ""
    risk = f" — {r_raw}" if r_raw else ""
    role_pt = tr_role(row["job_role"])
    dept_pt = tr_dept(row["department"])
    return f"ID {eid} — {role_pt} ({dept_pt}){risk}"


col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    id1 = st.selectbox("Colaborador A", options, index=0, format_func=_format, key="cmp_1")
with col_s2:
    idx2 = 1 if len(options) > 1 else 0
    id2 = st.selectbox("Colaborador B", options, index=idx2, format_func=_format, key="cmp_2")
with col_s3:
    id3 = st.selectbox(
        "Colaborador C (opcional)", [None] + options,
        format_func=lambda x: "— Nenhum —" if x is None else _format(x),
        key="cmp_3",
    )

selected_ids = [id1, id2]
if id3 is not None:
    selected_ids.append(id3)

# Remove duplicatas mantendo ordem
seen = set()
selected_ids = [x for x in selected_ids if not (x in seen or seen.add(x))]

if len(selected_ids) < 2:
    st.info("Selecione pelo menos 2 colaboradores diferentes.")
    st.stop()

# ── CARREGA DADOS DOS SELECIONADOS ──
with st.spinner("Calculando predições..."):
    data_by_id = {}
    for eid in selected_ids:
        try:
            emp = httpx.get(get_api_url(f"/employees/{int(eid)}"), timeout=10).json()
            pred = httpx.post(get_api_url("/predict"), json={"employee_id": int(eid)}, timeout=30).json()
            data_by_id[eid] = {"emp": emp, "pred": pred}
        except Exception as e:
            st.error(f"Falha ao carregar #{eid}: {e}")
            st.stop()


# ── PERFIL LADO A LADO ──
def risk_color(level: str) -> str:
    return {"baixo": "#10B981", "médio": "#3B82F6", "alto": "#F59E0B", "crítico": "#DC2626"}.get(level, "#6B7280")


# Mapa de tradução de nomes de features SHAP → PT-BR
FEATURE_NAME_PT = {
    "over_time_Yes": "Hora Extra",
    "over_time_No": "Sem Hora Extra",
    "business_travel_Travel_Frequently": "Viaja Frequentemente",
    "business_travel_Travel_Rarely": "Viaja Raramente",
    "business_travel_Non-Travel": "Não Viaja",
    "marital_status_Single": "Solteiro(a)",
    "marital_status_Married": "Casado(a)",
    "marital_status_Divorced": "Divorciado(a)",
    "gender_Male": "Gênero: Masculino",
    "gender_Female": "Gênero: Feminino",
    "department_Sales": "Dept. Vendas",
    "department_Research & Development": "Dept. P&D",
    "department_Human Resources": "Dept. RH",
    "job_role_Sales Executive": "Cargo: Exec. Vendas",
    "job_role_Sales Representative": "Cargo: Rep. Vendas",
    "job_role_Research Scientist": "Cargo: Cientista",
    "job_role_Laboratory Technician": "Cargo: Téc. Lab.",
    "job_role_Manufacturing Director": "Cargo: Dir. Manuf.",
    "job_role_Healthcare Representative": "Cargo: Rep. Saúde",
    "job_role_Manager": "Cargo: Gerente",
    "job_role_Research Director": "Cargo: Dir. Pesq.",
    "job_role_Human Resources": "Cargo: RH",
    "job_satisfaction": "Satisfação no Trabalho",
    "environment_satisfaction": "Satisfação com Ambiente",
    "work_life_balance": "Equilíbrio Vida-Trabalho",
    "stock_option_level": "Opções de Ações",
    "job_involvement": "Envolvimento no Trabalho",
    "relationship_satisfaction": "Satisfação nos Relacionamentos",
    "performance_rating": "Avaliação de Desempenho",
    "job_level": "Nível do Cargo",
    "education": "Escolaridade",
    "monthly_income": "Salário Mensal",
    "monthly_rate": "Taxa Mensal",
    "hourly_rate": "Taxa Horária",
    "daily_rate": "Taxa Diária",
    "num_companies_worked": "Empresas Anteriores",
    "distance_from_home": "Distância de Casa",
    "years_at_company": "Anos na Empresa",
    "years_in_current_role": "Anos no Cargo Atual",
    "years_since_last_promotion": "Anos sem Promoção",
    "years_with_curr_manager": "Anos com Gestor Atual",
    "training_times_last_year": "Treinamentos no Ano",
    "total_working_years": "Anos de Experiência",
    "age": "Idade",
    "percent_salary_hike": "% Aumento Salarial",
}


def _translate_feature(feat: str) -> str:
    key = feat.split("__")[-1]
    return FEATURE_NAME_PT.get(key, key.replace("_", " ").title())


st.markdown("### 👤 Perfil comparativo")
cols = st.columns(len(selected_ids))
for col, eid in zip(cols, selected_ids):
    emp = data_by_id[eid]["emp"]
    pred = data_by_id[eid]["pred"]
    level = pred.get("risk_level", "—")
    prob = pred.get("attrition_probability", 0)
    color = risk_color(level)

    with col:
        with st.container(border=True):
            st.markdown(
                f"<div style='text-align:center; padding:0.4rem 0;'>"
                f"<div style='color:#94A3B8; font-size:0.75rem; text-transform:uppercase;'>ID</div>"
                f"<div style='color:#FAFAFA; font-size:1.4rem; font-weight:700;'>#{eid}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            # Badge de risco
            st.markdown(
                f"<div style='background:{color}; color:white; text-align:center; "
                f"padding:0.5rem; border-radius:6px; font-weight:700; margin:0.5rem 0;'>"
                f"{level.upper()} — {prob:.1%}</div>",
                unsafe_allow_html=True,
            )
            # Stats — tudo em PT-BR
            salary = emp.get("monthly_income", 0) or 0
            stats = [
                ("Cargo", tr_role(emp.get("job_role", ""))),
                ("Departamento", tr_dept(emp.get("department", ""))),
                ("Salário", f"R$ {salary:,}" if salary else "—"),
                ("Anos na Empresa", emp.get("years_at_company", "—")),
                ("Hora Extra", tr_overtime(emp.get("over_time", ""))),
                ("Viagens", tr_travel(emp.get("business_travel", ""))),
                ("Satisfação Trab.", tr_satisfaction(emp.get("job_satisfaction"))),
                ("Equilíbrio Vida", tr_satisfaction(emp.get("work_life_balance"))),
                ("Estado Civil", tr_marital(emp.get("marital_status", ""))),
                ("Gênero", tr_gender(emp.get("gender", ""))),
            ]
            html = "<div style='background:#0F1420; border:1px solid #2D3748; border-radius:6px; padding:0.6rem 0.8rem;'>"
            for label, val in stats:
                html += (
                    f"<div style='padding:0.3rem 0; border-bottom:1px solid rgba(45,55,72,0.5);'>"
                    f"<div style='color:#94A3B8; font-size:0.7rem; text-transform:uppercase;'>{label}</div>"
                    f"<div style='color:#FAFAFA; font-size:0.95rem; font-weight:600;'>{val}</div>"
                    f"</div>"
                )
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

# ── GAUGE COMPARATIVO ──
st.markdown("### 🎯 Comparação de risco")
with st.container(border=True):
    fig = go.Figure()
    for eid in selected_ids:
        prob = data_by_id[eid]["pred"].get("attrition_probability", 0) * 100
        fig.add_trace(go.Bar(
            x=[f"Colaborador #{eid}"],
            y=[prob],
            name=f"#{eid}",
            marker_color=risk_color(data_by_id[eid]["pred"].get("risk_level", "")),
            text=[f"{prob:.1f}%"],
            textposition="outside",
            textfont=dict(size=14, color="#FAFAFA"),
        ))
    fig.update_layout(
        height=300, showlegend=False,
        yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="rgba(51,65,85,0.3)", tickfont=dict(color="#CBD5E1")),
        xaxis=dict(tickfont=dict(color="#FAFAFA")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=40, l=40, r=20),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── FATORES PRINCIPAIS (linguagem de RH, não técnica) ──
st.markdown("### 🔍 Principais fatores que influenciam o risco")
st.caption(
    "Para cada colaborador, os 5 fatores mais relevantes identificados pelo modelo. "
    "🔴 aumentam o risco de saída · 🟢 contribuem para retenção."
)

def _describe_magnitude(abs_val: float) -> str:
    if abs_val > 0.5: return "Forte"
    if abs_val > 0.2: return "Moderado"
    return "Leve"

cols2 = st.columns(len(selected_ids))
for col, eid in zip(cols2, selected_ids):
    factors = data_by_id[eid]["pred"].get("top_factors", [])
    with col:
        with st.container(border=True):
            st.markdown(f"**Colaborador #{eid}**")
            if not factors:
                st.info("Sem fatores disponíveis.")
                continue

            for f in factors:
                name = _translate_feature(f["feature"])
                val = f["shap_value"]
                direction_icon = "🔴" if val > 0 else "🟢"
                direction_text = "Aumenta risco" if val > 0 else "Protege"
                mag_text = _describe_magnitude(abs(val))
                color = "#DC2626" if val > 0 else "#10B981"

                # Card leve com barra de magnitude
                bar_width = min(100, int(abs(val) * 100 / 0.8 * 100))  # escala pra 0-100%
                bar_width = min(100, max(5, int(abs(val) / 0.8 * 100)))
                st.markdown(
                    f"<div style='background:#0F1420; border:1px solid #2D3748; "
                    f"border-radius:6px; padding:0.55rem 0.75rem; margin-bottom:0.4rem;'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<div style='color:#FAFAFA; font-size:0.88rem; font-weight:600;'>"
                    f"{direction_icon} {name}</div>"
                    f"<div style='color:{color}; font-size:0.72rem; font-weight:700;'>{mag_text}</div>"
                    f"</div>"
                    f"<div style='color:#94A3B8; font-size:0.72rem; margin-top:0.1rem;'>"
                    f"{direction_text} — impacto {mag_text.lower()}</div>"
                    f"<div style='margin-top:0.35rem; background:#1A1F2E; border-radius:3px; height:5px;'>"
                    f"<div style='background:{color}; width:{bar_width}%; height:5px; border-radius:3px;'></div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

st.caption(
    "💡 Compare os fatores entre colaboradores para identificar padrões. "
    "Se vários compartilham o mesmo driver (ex: hora extra), considere uma ação "
    "em nível de time ou departamento."
)
