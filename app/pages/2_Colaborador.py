"""Página 2 — Detalhe do Colaborador: perfil, risco, SHAP, explicação IA e PDF."""

import io
import streamlit as st
import httpx
import plotly.graph_objects as go
import pandas as pd

from components.sidebar import get_api_url
from components.theme import (
    apply_theme,
    EXTRA_EQUAL_HEIGHT_COLUMNS,
    EXTRA_EXPANDER_LARGE_PADDING,
    EXTRA_OUTER_FULL_HEIGHT,
)

st.set_page_config(page_title="Colaborador", page_icon="👤", layout="wide")
st.title("👤 Análise Individual do Colaborador")
st.caption(
    "Perfil completo, nível de risco, fatores que mais influenciam a probabilidade "
    "de saída e análise IA sob medida para o colaborador."
)

# CSS do tema — cards de perfil com altura igual + expander grande + caixa externa 100% height
apply_theme(
    extra_css=EXTRA_OUTER_FULL_HEIGHT
    + EXTRA_EQUAL_HEIGHT_COLUMNS
    + EXTRA_EXPANDER_LARGE_PADDING
)


@st.cache_data(ttl=60)
def load_employee_options():
    """Carrega lista de IDs com info resumida para o dropdown."""
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
    except Exception:
        return pd.DataFrame()


df_all = load_employee_options()

if df_all.empty:
    st.warning("Sem dados disponíveis.")
    st.stop()

# ── FILTROS ──
from components.translations import tr_dept, tr_role

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    dept_raw_options = sorted(df_all["department"].dropna().unique().tolist())
    dept_pt_to_raw = {tr_dept(d): d for d in dept_raw_options}
    dept_pt_options = ["Todos"] + sorted(dept_pt_to_raw.keys())
    sel_dept_pt = st.selectbox("Departamento", dept_pt_options)

if sel_dept_pt != "Todos":
    sel_dept_raw = dept_pt_to_raw[sel_dept_pt]
    df_filtered = df_all[df_all["department"] == sel_dept_raw]
else:
    df_filtered = df_all

with col_f2:
    role_raw_options = sorted(df_filtered["job_role"].dropna().unique().tolist())
    role_pt_to_raw = {tr_role(r): r for r in role_raw_options}
    role_pt_options = ["Todos"] + sorted(role_pt_to_raw.keys())
    sel_role_pt = st.selectbox("Cargo", role_pt_options)

if sel_role_pt != "Todos":
    sel_role_raw = role_pt_to_raw[sel_role_pt]
    df_filtered = df_filtered[df_filtered["job_role"] == sel_role_raw]

with col_f3:
    options = df_filtered["id"].tolist()

    def format_option(eid):
        row = df_filtered[df_filtered["id"] == eid].iloc[0]
        risk = f" — {row['risk_level']}" if row.get("risk_level") else ""
        return f"ID {eid} — {tr_role(row['job_role'])} ({tr_dept(row['department'])}){risk}"

    default_idx = 0
    # Vindo via query param (LinkColumn da tabela do dashboard)
    query_params = st.query_params
    target_from_url = query_params.get("employee_id")
    if target_from_url:
        try:
            target_id = int(target_from_url)
            if target_id in options:
                default_idx = options.index(target_id)
        except (ValueError, TypeError):
            pass
    # Vindo via session_state (fallback para outros fluxos)
    elif "selected_employee_id" in st.session_state:
        target = st.session_state.pop("selected_employee_id")
        if target in options:
            default_idx = options.index(target)

    if options:
        employee_id = st.selectbox("Colaborador", options=options, index=default_idx, format_func=format_option)
    else:
        st.warning("Nenhum colaborador com os filtros selecionados.")
        st.stop()

st.markdown("---")

# ── ANÁLISE AUTOMÁTICA ──
if employee_id:
    # Buscar predição + SHAP
    with st.spinner("Calculando risco e fatores SHAP..."):
        try:
            pred_resp = httpx.post(get_api_url("/predict"), json={"employee_id": employee_id}, timeout=30)
            pred_resp.raise_for_status()
            prediction = pred_resp.json()

            emp_resp = httpx.get(get_api_url(f"/employees/{employee_id}"), timeout=10)
            emp_resp.raise_for_status()
            emp = emp_resp.json()
        except Exception as e:
            st.error(f"Erro: {e}")
            st.stop()

    prob = prediction["attrition_probability"]
    risk_level = prediction["risk_level"]

    # Mapeamento de nomes técnicos para linguagem de RH (PT-BR)
    name_map = {
        # Categóricos
        "cat__over_time_Yes": "Hora Extra",
        "cat__over_time_No": "Sem Hora Extra",
        "cat__business_travel_Travel_Frequently": "Viaja Frequentemente",
        "cat__business_travel_Travel_Rarely": "Viaja Raramente",
        "cat__business_travel_Non-Travel": "Não Viaja",
        "cat__marital_status_Single": "Solteiro(a)",
        "cat__marital_status_Married": "Casado(a)",
        "cat__marital_status_Divorced": "Divorciado(a)",
        "cat__gender_Male": "Gênero: Masculino",
        "cat__gender_Female": "Gênero: Feminino",
        "cat__department_Sales": "Dept. Vendas",
        "cat__department_Research & Development": "Dept. P&D",
        "cat__department_Human Resources": "Dept. RH",
        "cat__job_role_Sales Executive": "Cargo: Executivo de Vendas",
        "cat__job_role_Sales Representative": "Cargo: Representante de Vendas",
        "cat__job_role_Research Scientist": "Cargo: Cientista de Pesquisa",
        "cat__job_role_Laboratory Technician": "Cargo: Técnico de Laboratório",
        "cat__job_role_Manufacturing Director": "Cargo: Diretor de Manufatura",
        "cat__job_role_Healthcare Representative": "Cargo: Rep. de Saúde",
        "cat__job_role_Manager": "Cargo: Gerente",
        "cat__job_role_Research Director": "Cargo: Diretor de Pesquisa",
        "cat__job_role_Human Resources": "Cargo: RH",
        "cat__education_field_Life Sciences": "Formação: Ciências da Vida",
        "cat__education_field_Medical": "Formação: Medicina",
        "cat__education_field_Technical Degree": "Formação: Técnica",
        "cat__education_field_Marketing": "Formação: Marketing",
        "cat__education_field_Human Resources": "Formação: RH",
        "cat__education_field_Other": "Formação: Outra",
        # Ordinais
        "ord__job_satisfaction": "Satisfação no Trabalho",
        "ord__environment_satisfaction": "Satisfação com Ambiente",
        "ord__work_life_balance": "Equilíbrio Vida-Trabalho",
        "ord__stock_option_level": "Opções de Ações",
        "ord__job_involvement": "Envolvimento no Trabalho",
        "ord__relationship_satisfaction": "Satisfação nos Relacionamentos",
        "ord__performance_rating": "Avaliação de Desempenho",
        "ord__job_level": "Nível do Cargo",
        "ord__education": "Nível de Escolaridade",
        # Numéricos
        "num__monthly_income": "Salário Mensal",
        "num__monthly_rate": "Taxa Mensal",
        "num__hourly_rate": "Taxa Horária",
        "num__daily_rate": "Taxa Diária",
        "num__num_companies_worked": "Empresas Anteriores",
        "num__distance_from_home": "Distância de Casa",
        "num__years_at_company": "Anos na Empresa",
        "num__years_in_current_role": "Anos no Cargo Atual",
        "num__years_since_last_promotion": "Anos sem Promoção",
        "num__years_with_curr_manager": "Anos com Gestor Atual",
        "num__training_times_last_year": "Treinamentos no Ano",
        "num__total_working_years": "Anos de Experiência",
        "num__age": "Idade",
        "num__percent_salary_hike": "% Aumento Salarial",
    }

    factors = prediction.get("top_factors", [])

    # Tons balanceados — visíveis mas não agressivos
    color_map = {"baixo": "#10B981", "médio": "#3B82F6", "alto": "#D97706", "crítico": "#DC2626"}
    gauge_color = color_map.get(risk_level, "#0891B2")

    # ── PERFIL (header horizontal com múltiplos campos) ──
    # Buscar dados completos
    try:
        full_emp_resp = httpx.get(get_api_url(f"/employees/{employee_id}"), timeout=10)
        full_emp_resp.raise_for_status()
        full_emp_profile = full_emp_resp.json()
    except Exception:
        full_emp_profile = emp

    def interp_satisfaction(v):
        try:
            v = int(v)
        except (ValueError, TypeError):
            return "—"
        return {1: "Baixa", 2: "Média", 3: "Alta", 4: "Muito Alta"}.get(v, "—")

    travel_map = {
        "Travel_Rarely": "Raramente",
        "Travel_Frequently": "Frequente",
        "Non-Travel": "Não viaja",
    }

    def safe(v, suffix=""):
        """Retorna valor ou '—' se vazio/None."""
        if v is None or v == "" or v == "None":
            return "—"
        return f"{v}{suffix}" if suffix else str(v)

    def render_field_row(label: str, value) -> str:
        """Renderiza um par label/valor em linha."""
        return (
            f"<div style='padding: 0.4rem 0; border-bottom: 1px solid rgba(45,55,72,0.5);'>"
            f"<div style='color:#00BCD4; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.4px; margin-bottom:0.15rem;'>{label}</div>"
            f"<div style='color:#FAFAFA; font-size:1rem; font-weight:600; line-height:1.3;'>{value}</div>"
            f"</div>"
        )

    def render_group_vertical(title: str, fields: list) -> str:
        """Grupo: caixa externa com título + caixa interna azul escuro com os itens."""
        rows = "".join(render_field_row(lbl, val) for lbl, val in fields)
        # Remover border-bottom do último item
        rows = rows.rsplit("border-bottom: 1px solid rgba(45,55,72,0.5);", 1)
        rows = ("border-bottom: none;".join(rows)) if len(rows) == 2 else rows[0]
        return (
            f"<div style='flex:1; background:#1A1F2E; border:1px solid #2D3748; border-radius:8px; padding:0.8rem 0.9rem;'>"
            f"<div style='color:#94A3B8; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.6px; margin-bottom:0.6rem; font-weight:700;'>{title}</div>"
            f"<div style='background:#0F1420; border:1px solid #2D3748; border-radius:6px; padding: 0.3rem 0.8rem;'>"
            f"{rows}"
            f"</div>"
            f"</div>"
        )

    # Monta os 4 grupos — empilhados verticalmente DENTRO, lado a lado FORA
    group_profissional = render_group_vertical("Profissional", [
        ("Cargo", tr_role(emp.get("job_role") or "")),
        ("Departamento", tr_dept(emp.get("department") or "")),
        ("Nível do Cargo", safe(full_emp_profile.get("job_level"))),
        ("Anos no Cargo", safe(full_emp_profile.get("years_in_current_role"))),
    ])
    group_experiencia = render_group_vertical("Experiência e Carreira", [
        ("Anos na Empresa", safe(emp.get("years_at_company"))),
        ("Experiência Total", safe(full_emp_profile.get("total_working_years"), " anos")),
        ("Sem Promoção", safe(full_emp_profile.get("years_since_last_promotion"), " anos")),
        ("Empresas Anteriores", safe(full_emp_profile.get("num_companies_worked"))),
    ])
    salary = emp.get("monthly_income", 0) or 0
    overtime_map = {"Yes": "Sim", "No": "Não"}
    overtime_val = full_emp_profile.get("over_time")
    group_remuneracao = render_group_vertical("Remuneração e Jornada", [
        ("Salário Mensal", f"R$ {salary:,}" if salary else "—"),
        ("Último Aumento", safe(full_emp_profile.get("percent_salary_hike"), "%")),
        ("Hora Extra", overtime_map.get(overtime_val, safe(overtime_val))),
        ("Viagens", travel_map.get(full_emp_profile.get("business_travel"), safe(full_emp_profile.get("business_travel")))),
    ])
    group_pessoal = render_group_vertical("Perfil Pessoal e Engajamento", [
        ("Idade", safe(full_emp_profile.get("age"), " anos")),
        ("Distância de Casa", safe(full_emp_profile.get("distance_from_home"), " km")),
        ("Satisfação no Trabalho", interp_satisfaction(full_emp_profile.get("job_satisfaction"))),
        ("Equilíbrio Vida-Trabalho", interp_satisfaction(full_emp_profile.get("work_life_balance"))),
    ])

    # Cabeçalho "Perfil" + link pro Simulador pré-selecionando esse colaborador
    col_perfil_title, col_perfil_link = st.columns([8, 1])
    with col_perfil_title:
        st.markdown("#### 👤 Perfil")
    with col_perfil_link:
        st.page_link(
            "pages/7_Simulador.py",
            label="🎛️ Simular ações",
            help="Abre o Simulador 'E se?' para este colaborador",
        )

    # 4 grupos lado a lado (colunas), cada um com seus cards empilhados verticalmente dentro
    st.markdown(
        f"<div style='display:flex; gap:0.6rem; margin-bottom:1rem;'>"
        f"{group_profissional}{group_experiencia}{group_remuneracao}{group_pessoal}"
        f"</div>",
        unsafe_allow_html=True,
    )
    # Salva o ID selecionado pro Simulador ler via session_state
    st.session_state["simulator_preselect_id"] = employee_id

    # ── GAUGE + SHAP (lado a lado — SHAP mais largo) ──
    col_gauge, col_shap = st.columns([1, 2])

    with col_gauge:
        st.markdown("#### 🎯 Nível de Risco")
        with st.container(border=True):
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=prob * 100,
                number={"suffix": "%", "font": {"size": 48, "color": gauge_color}},
                gauge={
                    "axis": {
                        "range": [0, 100],
                        "tickvals": [0, 20, 40, 70, 100],
                        "tickwidth": 1,
                        "tickcolor": "#CBD5E1",
                        "tickfont": {"size": 11, "color": "#94A3B8"},
                    },
                    "bar": {"color": gauge_color, "thickness": 0.35},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 1,
                    "bordercolor": "#334155",
                    "steps": [
                        {"range": [0, 20], "color": "rgba(16,185,129,0.18)"},
                        {"range": [20, 40], "color": "rgba(59,130,246,0.18)"},
                        {"range": [40, 70], "color": "rgba(217,119,6,0.18)"},
                        {"range": [70, 100], "color": "rgba(220,38,38,0.18)"},
                    ],
                    "threshold": {"line": {"color": gauge_color, "width": 3}, "thickness": 0.85, "value": prob * 100},
                },
            ))
            fig.update_layout(
                height=260,
                margin=dict(t=20, b=5, l=20, r=20),
                paper_bgcolor="rgba(0,0,0,0)",
                font={"color": "#FAFAFA"},
            )
            st.plotly_chart(fig, use_container_width=True)

            # Badge de nível de risco — centralizado verticalmente no espaço abaixo do gauge
            st.markdown(
                f"<div style='display:flex; justify-content:center; margin-top:0.9rem; margin-bottom:0.9rem;'>"
                f"<div style='padding: 0.4rem 1.5rem; background:{gauge_color}; "
                f"border-radius: 6px; color:white; font-weight:bold; font-size:0.95rem;'>"
                f"{risk_level.upper()}</div></div>",
                unsafe_allow_html=True,
            )

    with col_shap:
        st.markdown("#### 📊 Fatores que Influenciam o Risco")
        with st.container(border=True):
            if factors:
                factor_names = [name_map.get(f["feature"], f["feature"].split("__")[-1].replace("_", " ").title()) for f in factors]
                factor_values = [f["shap_value"] for f in factors]
                factor_colors = ["#DC2626" if v > 0 else "#10B981" for v in factor_values]

                fig_shap = go.Figure(go.Bar(
                    x=factor_values,
                    y=factor_names,
                    orientation="h",
                    marker_color=factor_colors,
                    text=[f"{v:+.3f}" for v in factor_values],
                    textposition="outside",
                    textfont=dict(size=11, color="#FAFAFA"),
                ))
                # Labels em bold via HTML <b>
                factor_names_bold = [f"<b>{name}</b>" for name in factor_names]
                fig_shap.update_traces(y=factor_names_bold)

                fig_shap.update_layout(
                    height=310,
                    margin=dict(l=10, r=40, t=10, b=25),
                    yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#FAFAFA")),
                    xaxis=dict(tickfont=dict(size=9, color="#94A3B8"), title=None, gridcolor="#334155"),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                fig_shap.add_vline(x=0, line_dash="solid", line_color="#475569", line_width=1)
                st.plotly_chart(fig_shap, use_container_width=True)
                st.markdown(
                    "<div style='display:flex; gap:2rem; justify-content:flex-start; "
                    "font-size:0.85rem; color:#94A3B8; margin-top:0.5rem; padding-left:0.5rem;'>"
                    "<span>🔴 Aumenta risco</span>"
                    "<span>🟢 Diminui risco</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("Sem fatores SHAP disponíveis.")

    if st.button("🤖 Análise Detalhada por IA", type="primary", use_container_width=True):
        try:
            full_resp = httpx.get(get_api_url(f"/employees/{employee_id}"), timeout=10)
            full_resp.raise_for_status()
            full_emp = full_resp.json()
        except Exception:
            full_emp = emp

        # Fatores SHAP em linguagem de negócio
        factors_lines = []
        for f in factors:
            fname = name_map.get(f["feature"], f["feature"])
            magnitude_desc = "forte" if abs(f["shap_value"]) > 0.5 else ("moderado" if abs(f["shap_value"]) > 0.2 else "leve")
            direction = "PUXA PARA CIMA" if f["shap_value"] > 0 else "PUXA PARA BAIXO"
            factors_lines.append(f"  • {fname}  →  impacto {magnitude_desc} ({f['shap_value']:+.3f}), {direction} o risco de saída")
        factors_text = "\n".join(factors_lines)

        # Interpretações semânticas das escalas 1-4
        def interp_scale(v):
            try:
                v = int(v)
                return {1: "Baixa", 2: "Média", 3: "Alta", 4: "Muito Alta"}.get(v, str(v))
            except (ValueError, TypeError):
                return "N/D"

        attrition_hist = full_emp.get("attrition") or emp.get("attrition")
        status_colaborador = "Ex-colaborador (já saiu)" if attrition_hist == "Yes" else "Colaborador ativo"

        # Benchmarks do dataset IBM HR
        salary_median = 4919  # mediana do dataset
        salary_vs_median = (emp.get("monthly_income", 0) / salary_median - 1) * 100
        salary_comp = f"{abs(salary_vs_median):.0f}% {'acima' if salary_vs_median >= 0 else 'abaixo'} da mediana da empresa (R$ {salary_median:,})"

        prompt = f"""Você é um Business Partner de RH sênior preparando um dossiê de retenção para apresentar à liderança de People.
O relatório é para o TIME DE RH usar em reuniões 1:1 com gestores. Linguagem profissional, objetiva, orientada a ação.
NÃO use jargão técnico de ML (SHAP, threshold, predição). Converta para termos de negócio.

## PERFIL DO COLABORADOR (ID #{employee_id}) — {status_colaborador}

**Identificação e perfil profissional**
- Cargo: {emp.get('job_role', '—')} | Nível {full_emp.get('job_level', '—')} | {emp.get('department', '—')}
- Tempo de casa: {emp.get('years_at_company', '—')} anos (no cargo atual há {full_emp.get('years_in_current_role', '—')} anos)
- Experiência total: {full_emp.get('total_working_years', '—')} anos | Passou por {full_emp.get('num_companies_worked', '—')} empresas antes
- Gestor atual há: {full_emp.get('years_with_curr_manager', '—')} anos
- Última promoção: {full_emp.get('years_since_last_promotion', '—')} anos atrás
- Formação: {full_emp.get('education_field', '—')} (nível {full_emp.get('education', '—')})

**Perfil pessoal**
- Idade: {full_emp.get('age', '—')} | Gênero: {full_emp.get('gender', '—')} | Estado civil: {full_emp.get('marital_status', '—')}
- Distância casa-trabalho: {full_emp.get('distance_from_home', '—')} km

**Remuneração e benefícios**
- Salário: R$ {emp.get('monthly_income', 0):,}/mês ({salary_comp})
- Último reajuste: {full_emp.get('percent_salary_hike', '—')}%
- Stock options: nível {full_emp.get('stock_option_level', '—')} (escala 0-3)

**Carga de trabalho**
- Hora extra frequente: {full_emp.get('over_time', '—')}
- Padrão de viagens: {full_emp.get('business_travel', '—')}
- Treinamentos recebidos no último ano: {full_emp.get('training_times_last_year', '—')}

**Engajamento e satisfação (escala 1-4)**
- Satisfação com o trabalho: {interp_scale(full_emp.get('job_satisfaction'))} ({full_emp.get('job_satisfaction', '—')}/4)
- Satisfação com o ambiente: {interp_scale(full_emp.get('environment_satisfaction'))} ({full_emp.get('environment_satisfaction', '—')}/4)
- Satisfação com relacionamentos: {interp_scale(full_emp.get('relationship_satisfaction'))} ({full_emp.get('relationship_satisfaction', '—')}/4)
- Equilíbrio vida-trabalho: {interp_scale(full_emp.get('work_life_balance'))} ({full_emp.get('work_life_balance', '—')}/4)
- Envolvimento no trabalho: {interp_scale(full_emp.get('job_involvement'))} ({full_emp.get('job_involvement', '—')}/4)
- Avaliação de desempenho: {interp_scale(full_emp.get('performance_rating'))} ({full_emp.get('performance_rating', '—')}/4)

## RESULTADO DA ANÁLISE PREDITIVA
- **Probabilidade de saída nos próximos meses: {prob:.1%}**
- **Classificação: {risk_level.upper()}**

## PRINCIPAIS DRIVERS (segundo o modelo)
{factors_text}

---

## ENTREGUE O RELATÓRIO NO FORMATO ABAIXO

Use **markdown** com as seções exatas. Tom corporativo, direto e acionável.

### 📋 Sumário Executivo
Em 2-3 linhas: qual é a situação, qual é a recomendação principal. É o que a liderança lê se tiver 30 segundos.

### 🎯 Diagnóstico
Parágrafo único (4-6 linhas) explicando o contexto desse colaborador. Evidencie contradições relevantes (ex: alto desempenho + sem promoção; salário acima da mediana + alta insatisfação). Use os dados REAIS. Não use termos técnicos.

### 🔍 Fatores-chave de influência
Liste os 5 fatores principais. Para cada um:
- **Nome do fator em RH** (ex: "Hora extra frequente")
- **Dado observado**: "{emp.get('job_role', 'cargo')} com...". Use o valor real.
- **Leitura de negócio**: 1-2 linhas explicando por que isso está puxando o risco para onde está. Contexto humano, não estatístico.

### ⚠️ Alertas e contradições
2-4 bullets destacando sinais específicos (positivos ou negativos) que merecem atenção do gestor. Ex: "Há {full_emp.get('years_since_last_promotion', 'N')} anos sem promoção apesar da avaliação {interp_scale(full_emp.get('performance_rating'))}".

### 🚀 Plano de Ação Recomendado
Tabela markdown com 4-5 ações ESPECÍFICAS para este colaborador. Nada genérico como "fazer 1:1" — diga sobre o quê, com que frequência, com base em qual dado.

| # | Ação | Racional (baseado em dado real) | Responsável | Prazo |
|---|------|---------------------------------|-------------|-------|
| 1 | [ação específica] | [cite o dado que motivou] | Gestor direto / Comitê de Remuneração / BP de RH | Imediato / 30 dias / 60 dias / 90 dias |

### 💡 Conversa sugerida com o gestor
3-4 perguntas-guia que o RH pode levar para o gestor direto. Ex: "O colaborador já sinalizou interesse em...?", "Como foi a última conversa de carreira?".

### 📈 Indicadores para acompanhar
Lista com 3-4 métricas que o RH deve observar nos próximos meses para medir efeito das ações.

---

## REGRAS OBRIGATÓRIAS
1. **Tom conforme o risco**:
   - BAIXO → reforço positivo, ações preventivas leves
   - MÉDIO → atenção preventiva, acompanhamento estruturado
   - ALTO/CRÍTICO → alerta construtivo, ações urgentes nas próximas 2-4 semanas
2. **NUNCA invente** informações. Use APENAS os dados acima. Se não tem a informação, omita.
3. **NÃO use**: "churn", "SHAP", "threshold", "modelo ML", "predição" no texto visível ao RH. Use "análise preditiva", "indicadores", "probabilidade de saída".
4. **NÃO termine** com perguntas abertas ao usuário. Encerre o relatório.
5. **Use números concretos** (R$, anos, %) sempre que possível. Ações vagas ("melhorar retenção") são proibidas.
6. Português brasileiro formal-corporativo. Sem emojis excessivos (apenas os dos cabeçalhos).
7. Extensão ideal: 500-800 palavras no total."""

        # Loading customizado (círculo giratório CSS em vez do skater do Streamlit)
        loading_placeholder = st.empty()
        loading_placeholder.markdown(
            """
            <style>
            @keyframes spin-hr {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .hr-loader-wrap {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 2rem 0;
            }
            .hr-loader {
                width: 48px;
                height: 48px;
                border: 4px solid rgba(0, 188, 212, 0.2);
                border-top-color: #00BCD4;
                border-radius: 50%;
                animation: spin-hr 0.9s linear infinite;
            }
            .hr-loader-text {
                margin-top: 1rem;
                color: #94A3B8;
                font-size: 0.9rem;
            }
            </style>
            <div class="hr-loader-wrap">
                <div class="hr-loader"></div>
                <div class="hr-loader-text">Gerando análise detalhada...</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        try:
            resp = httpx.post(
                get_api_url("/agent/chat"),
                json={"message": prompt},
                timeout=90,
            )
            resp.raise_for_status()
            result = resp.json()
            ai_report = result["response"]
            st.session_state["ai_report"] = ai_report
            st.session_state["ai_report_emp"] = employee_id
        except Exception as e:
            st.error(f"Erro: {e}")
        finally:
            loading_placeholder.empty()

    # Exibir relatório se disponível
    if st.session_state.get("ai_report") and st.session_state.get("ai_report_emp") == employee_id:
        with st.expander("🤖 Análise Detalhada por IA", expanded=True):
            ai_report = st.session_state["ai_report"]
            # Escapar $ para evitar que o Streamlit interprete como LaTeX/MathJax
            ai_report_display = ai_report.replace("$", r"\$")
            st.markdown(ai_report_display)

            # ── EXPORTAR PDF ──
            st.markdown("---")
            st.markdown("### 📄 Exportar Relatório")

            try:
                import re
                from reportlab.lib.pagesizes import A4
                from reportlab.lib import colors as rl_colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
                from reportlab.lib.units import cm
                from datetime import datetime

                buffer = io.BytesIO()
                doc = SimpleDocTemplate(
                    buffer, pagesize=A4,
                    topMargin=2*cm, bottomMargin=2*cm,
                    leftMargin=2*cm, rightMargin=2*cm,
                    title=f"Relatório Colaborador {employee_id}",
                    author="People Analytics — HR Intelligence",
                )
                styles = getSampleStyleSheet()

                # Estilos customizados
                style_title = ParagraphStyle(
                    name="TitleCustom", parent=styles["Title"],
                    textColor=rl_colors.HexColor("#00BCD4"),
                    fontSize=22, spaceAfter=12, alignment=TA_CENTER,
                )
                style_subtitle = ParagraphStyle(
                    name="SubtitleCustom", parent=styles["Normal"],
                    textColor=rl_colors.HexColor("#64748B"),
                    fontSize=10, alignment=TA_CENTER, spaceAfter=20,
                )
                style_h2 = ParagraphStyle(
                    name="H2Custom", parent=styles["Heading2"],
                    textColor=rl_colors.HexColor("#00BCD4"),
                    fontSize=14, spaceBefore=12, spaceAfter=8,
                    borderPadding=4,
                )
                style_h3 = ParagraphStyle(
                    name="H3Custom", parent=styles["Heading3"],
                    textColor=rl_colors.HexColor("#1E293B"),
                    fontSize=12, spaceBefore=8, spaceAfter=6,
                )
                style_body = ParagraphStyle(
                    name="BodyCustom", parent=styles["Normal"],
                    fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6,
                )
                style_bullet = ParagraphStyle(
                    name="BulletCustom", parent=styles["Normal"],
                    fontSize=10, leading=14, leftIndent=15, spaceAfter=3,
                )
                style_risk_badge = ParagraphStyle(
                    name="RiskBadge", parent=styles["Normal"],
                    textColor=rl_colors.white,
                    fontSize=14, alignment=TA_CENTER,
                    backColor=rl_colors.HexColor(color_map.get(risk_level, "#6B7280")),
                    borderPadding=10, spaceAfter=12,
                )

                story = []

                # === CAPA ===
                story.append(Paragraph("Relatório de Análise de Retenção", style_title))
                story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", style_subtitle))

                # Card de identificação do colaborador
                id_data = [
                    ["ID do Colaborador", str(employee_id)],
                    ["Cargo", emp.get("job_role", "—")],
                    ["Departamento", emp.get("department", "—")],
                    ["Salário Mensal", f"R$ {emp.get('monthly_income', 0):,}"],
                    ["Anos na Empresa", str(emp.get("years_at_company", "—"))],
                ]
                id_table = Table(id_data, colWidths=[6*cm, 11*cm])
                id_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), rl_colors.HexColor("#F1F5F9")),
                    ("TEXTCOLOR", (0, 0), (0, -1), rl_colors.HexColor("#475569")),
                    ("TEXTCOLOR", (1, 0), (1, -1), rl_colors.HexColor("#0F172A")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                story.append(id_table)
                story.append(Spacer(1, 0.5*cm))

                # Badge de risco
                story.append(Paragraph(
                    f"NÍVEL DE RISCO: {risk_level.upper()} — {prob:.1%}",
                    style_risk_badge,
                ))
                story.append(Spacer(1, 0.5*cm))

                # === FATORES SHAP ===
                story.append(Paragraph("Fatores de Risco (Análise SHAP)", style_h2))
                story.append(Paragraph(
                    "Os fatores abaixo foram identificados pelo modelo preditivo como os de maior impacto no risco de saída deste colaborador.",
                    style_body,
                ))
                story.append(Spacer(1, 0.3*cm))

                shap_data = [["Fator", "Valor SHAP", "Impacto"]]
                for f in factors:
                    name = name_map.get(f["feature"], f["feature"].split("__")[-1].replace("_", " ").title())
                    direction = "Aumenta risco" if f["shap_value"] > 0 else "Diminui risco"
                    shap_data.append([name, f"{f['shap_value']:+.4f}", direction])

                shap_table = Table(shap_data, colWidths=[9*cm, 3.5*cm, 4.5*cm])
                shap_table.setStyle(TableStyle([
                    # Header
                    ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#00BCD4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("ALIGN", (1, 0), (2, 0), "CENTER"),
                    # Corpo
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#E2E8F0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFC")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]))
                # Colorir "Aumenta risco" em vermelho, "Diminui" em verde
                for i, f in enumerate(factors, start=1):
                    if f["shap_value"] > 0:
                        shap_table.setStyle(TableStyle([
                            ("TEXTCOLOR", (2, i), (2, i), rl_colors.HexColor("#EF4444")),
                            ("FONTNAME", (2, i), (2, i), "Helvetica-Bold"),
                        ]))
                    else:
                        shap_table.setStyle(TableStyle([
                            ("TEXTCOLOR", (2, i), (2, i), rl_colors.HexColor("#10B981")),
                            ("FONTNAME", (2, i), (2, i), "Helvetica-Bold"),
                        ]))
                story.append(shap_table)
                story.append(Spacer(1, 0.8*cm))

                # === ANÁLISE IA ===
                story.append(Paragraph("Análise Detalhada por IA", style_h2))

                # Remove emojis (Helvetica não suporta) e caracteres não-latinos
                def strip_emojis(text: str) -> str:
                    """Remove emojis do texto para compatibilidade com Helvetica."""
                    # Remove blocos Unicode de emojis
                    emoji_pattern = re.compile(
                        "["
                        "\U0001F600-\U0001F64F"  # emoticons
                        "\U0001F300-\U0001F5FF"  # símbolos & pictogramas
                        "\U0001F680-\U0001F6FF"  # transporte & mapas
                        "\U0001F700-\U0001F77F"  # símbolos alquímicos
                        "\U0001F780-\U0001F7FF"  # formas geométricas
                        "\U0001F800-\U0001F8FF"  # setas
                        "\U0001F900-\U0001F9FF"  # símbolos suplementares
                        "\U0001FA00-\U0001FA6F"  # símbolos & pictogramas estendidos
                        "\U0001FA70-\U0001FAFF"  # símbolos & pictogramas estendidos A
                        "\U00002600-\U000027BF"  # símbolos diversos + dingbats
                        "\U0001F1E0-\U0001F1FF"  # bandeiras
                        "\u200d"
                        "\u2640-\u2642"
                        "\u2600-\u2B55"
                        "\u23cf\u23e9\u231a\ufe0f\u3030"
                        "]+",
                        flags=re.UNICODE,
                    )
                    return emoji_pattern.sub("", text).strip()

                # Parser de markdown básico para ReportLab Paragraph
                def md_to_rl(text: str) -> str:
                    """Converte markdown simples para tags HTML suportadas pelo ReportLab."""
                    text = strip_emojis(text)
                    # Bold **x** → <b>x</b>
                    text = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", text)
                    # Italic *x* → <i>x</i>
                    text = re.sub(r"(?<!\*)\*([^\*\n]+)\*(?!\*)", r"<i>\1</i>", text)
                    # Code `x` → <font name=Courier>x</font>
                    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
                    return text

                def is_separator_line(line: str) -> bool:
                    """Detecta linhas que são apenas separadores (---, ***, ===)."""
                    stripped = line.strip()
                    return bool(stripped) and set(stripped) <= set("-*=_ ") and len(stripped) >= 3

                # Processar linhas do relatório — detectar headers, bullets, parágrafos
                lines = ai_report.split("\n")
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if not line:
                        i += 1
                        continue

                    # Pular separadores (---, ***, etc.)
                    if is_separator_line(line):
                        i += 1
                        continue

                    # Header H3 (### ou ##)
                    if line.startswith("### "):
                        story.append(Paragraph(md_to_rl(line[4:]), style_h3))
                    elif line.startswith("## "):
                        story.append(Paragraph(md_to_rl(line[3:]), style_h3))
                    elif line.startswith("# "):
                        story.append(Paragraph(md_to_rl(line[2:]), style_h3))
                    # Lista com - ou *
                    elif line.startswith(("- ", "* ")):
                        item = line[2:]
                        story.append(Paragraph(f"• {md_to_rl(item)}", style_bullet))
                    # Lista numerada
                    elif re.match(r"^\d+\.\s", line):
                        story.append(Paragraph(md_to_rl(line), style_bullet))
                    # Parágrafo normal
                    else:
                        # Tentar detectar pseudo-tabelas (linha com múltiplos |)
                        if line.count("|") >= 2 and i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
                            # Coletar linhas de tabela
                            table_lines = []
                            while i < len(lines) and lines[i].strip().startswith("|"):
                                raw = lines[i].strip()
                                if set(raw) <= set("|-: "):  # linha separadora
                                    i += 1
                                    continue
                                cells = [c.strip() for c in raw.split("|")[1:-1]]
                                # Converter cada célula com md_to_rl (remove emojis, processa **bold**)
                                cells_rl = [Paragraph(md_to_rl(c), style_body) for c in cells]
                                table_lines.append(cells_rl)
                                i += 1
                            if len(table_lines) >= 2:
                                # Calcular larguras baseadas no número de colunas
                                # Largura útil da página A4 com margens: ~17cm
                                n_cols = len(table_lines[0])
                                total_width = 17 * cm

                                # Heurística: primeira coluna estreita se for "#" ou numérica
                                if n_cols == 5:
                                    # Formato: # | Ação | Racional | Responsável | Prazo
                                    col_widths = [0.8*cm, 4*cm, 6*cm, 3.5*cm, 2.7*cm]
                                elif n_cols == 4:
                                    col_widths = [4*cm, 6.5*cm, 3.5*cm, 3*cm]
                                elif n_cols == 3:
                                    col_widths = [6*cm, 5.5*cm, 5.5*cm]
                                else:
                                    col_widths = [total_width / n_cols] * n_cols

                                # Estilo específico para conteúdo da tabela (mais compacto)
                                style_table_cell = ParagraphStyle(
                                    name="TableCell", parent=styles["Normal"],
                                    fontSize=9, leading=12, spaceAfter=0, alignment=TA_JUSTIFY,
                                )

                                # Reprocessar células com o estilo de tabela (mais compacto)
                                table_data = []
                                for row_idx, row in enumerate(table_lines):
                                    new_row = []
                                    for cell in row:
                                        if isinstance(cell, Paragraph):
                                            # Já é Paragraph; extrair texto e recriar com estilo adequado
                                            txt = cell.text
                                        else:
                                            txt = str(cell)
                                        # Header: sem markdown bold
                                        if row_idx == 0:
                                            new_row.append(Paragraph(strip_emojis(txt.replace("**", "").replace("*", "")), ParagraphStyle(
                                                name="TableHeader", parent=styles["Normal"],
                                                fontSize=10, leading=13, textColor=rl_colors.white,
                                                fontName="Helvetica-Bold", alignment=1,
                                            )))
                                        else:
                                            new_row.append(Paragraph(txt, style_table_cell))
                                    table_data.append(new_row)

                                tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
                                tbl.setStyle(TableStyle([
                                    ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#00BCD4")),
                                    ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#E2E8F0")),
                                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFC")]),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                ]))
                                story.append(tbl)
                                story.append(Spacer(1, 0.3*cm))
                                continue
                        story.append(Paragraph(md_to_rl(line), style_body))
                    i += 1

                # === RODAPÉ ===
                story.append(Spacer(1, 1*cm))
                footer_style = ParagraphStyle(
                    name="Footer", parent=styles["Normal"],
                    textColor=rl_colors.HexColor("#94A3B8"),
                    fontSize=8, alignment=TA_CENTER,
                )
                story.append(Paragraph(
                    "People Analytics — HR Intelligence | Powered by XGBoost + SHAP + Gemini",
                    footer_style,
                ))

                doc.build(story)
                pdf_bytes = buffer.getvalue()

                st.download_button(
                    label="📄 Baixar PDF",
                    data=pdf_bytes,
                    file_name=f"relatorio_retencao_colaborador_{employee_id}.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            except ImportError:
                st.warning("ReportLab não instalado. Execute: `pip install reportlab`")
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
