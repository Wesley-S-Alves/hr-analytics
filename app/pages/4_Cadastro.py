"""Página 4 — Cadastro de Colaboradores com geração via IA."""

import json

import streamlit as st
import httpx

from components.employee_table import render_employee_table
from components.sidebar import get_api_url
from components.theme import (
    apply_theme,
    EXTRA_EQUAL_HEIGHT_COLUMNS,
    EXTRA_NESTED_INNER_BOX,
    EXTRA_TABS,
)

st.set_page_config(page_title="Cadastro", page_icon="➕", layout="wide")
st.title("➕ Cadastro de Colaboradores")
st.caption(
    "Cadastre colaboradores manualmente, via IA ou em lote por CSV. "
    "Consulte a lista completa com filtros e veja a análise preditiva de risco "
    "gerada automaticamente após cada cadastro."
)

# CSS do tema — 2 camadas aninhadas (form) + colunas altura igual + tabs estilizadas
apply_theme(
    extra_css=EXTRA_NESTED_INNER_BOX
    + EXTRA_EQUAL_HEIGHT_COLUMNS
    + EXTRA_TABS
)

tab_cadastrar, tab_listar, tab_upload = st.tabs(["📝 Cadastrar", "📋 Listar", "📤 Upload CSV"])

with tab_cadastrar:
    # Botão para gerar dados fictícios com IA
    if st.button("🤖 Gerar com IA", help="Usa Gemini para preencher com dados fictícios realistas"):
        with st.spinner("Gerando dados fictícios..."):
            try:
                from hr_analytics.llm.client import gemini_client
                from hr_analytics.llm.prompts import SYSTEM_PROMPT

                prompt = (
                    "Gere dados fictícios realistas de UM colaborador brasileiro para "
                    "um sistema de RH. Retorne um JSON com os campos:\n"
                    "age, gender (Male/Female), marital_status (Single/Married/Divorced), "
                    "education (1-5), education_field, distance_from_home (1-30), "
                    "department (Sales/Research & Development/Human Resources), "
                    "job_role, job_level (1-5), business_travel (Travel_Rarely/Travel_Frequently/Non-Travel), "
                    "over_time (Yes/No), daily_rate (100-1500), hourly_rate (30-100), "
                    "monthly_rate (2000-25000), monthly_income (1000-20000), "
                    "percent_salary_hike (11-25), stock_option_level (0-3), "
                    "total_working_years (0-40), years_at_company (0-30), "
                    "years_in_current_role (0-18), years_since_last_promotion (0-15), "
                    "years_with_curr_manager (0-17), num_companies_worked (0-9), "
                    "training_times_last_year (0-6), "
                    "environment_satisfaction (1-4), job_involvement (1-4), "
                    "job_satisfaction (1-4), relationship_satisfaction (1-4), "
                    "work_life_balance (1-4), performance_rating (3-4).\n"
                    "Retorne APENAS o JSON, sem explicações."
                )

                response_text, _, _ = gemini_client.generate_sync(
                    prompt, "Você é um gerador de dados fictícios de RH."
                )
                generated = json.loads(response_text)
                st.session_state["generated_employee"] = generated
                st.success("Dados gerados! Revise e clique em Cadastrar.")
            except Exception as e:
                st.error(f"Erro ao gerar dados: {e}")

    # Formulário de cadastro
    defaults = st.session_state.get("generated_employee", {})

    with st.form("employee_form"):
        col1, col2, col3 = st.columns(3)

        # Opções em PT → valores EN (compat com o modelo treinado)
        GENDER_OPTS = {"Masculino": "Male", "Feminino": "Female"}
        MARITAL_OPTS = {"Solteiro(a)": "Single", "Casado(a)": "Married", "Divorciado(a)": "Divorced"}
        DEPT_OPTS = {"Vendas": "Sales", "Pesquisa e Desenvolvimento": "Research & Development", "Recursos Humanos": "Human Resources"}
        TRAVEL_OPTS = {"Raramente": "Travel_Rarely", "Frequentemente": "Travel_Frequently", "Não viaja": "Non-Travel"}
        OVERTIME_OPTS = {"Sim": "Yes", "Não": "No"}

        with col1:
            with st.container(border=True):
                st.subheader("Dados Pessoais")
                with st.container(border=True):
                    age = st.number_input("Idade", 18, 70, defaults.get("age", 30))
                    gender_label = st.selectbox("Gênero", list(GENDER_OPTS))
                    gender = GENDER_OPTS[gender_label]
                    marital_label = st.selectbox("Estado Civil", list(MARITAL_OPTS))
                    marital_status = MARITAL_OPTS[marital_label]
                    education = st.slider("Escolaridade (1=Fundamental · 5=Doutorado)", 1, 5, defaults.get("education", 3))
                    education_field = st.text_input("Área de Formação", defaults.get("education_field", "Life Sciences"))
                    distance_from_home = st.number_input("Distância de Casa (km)", 1, 30, defaults.get("distance_from_home", 5))

        with col2:
            with st.container(border=True):
                st.subheader("Dados Profissionais")
                with st.container(border=True):
                    dept_label = st.selectbox("Departamento", list(DEPT_OPTS))
                    department = DEPT_OPTS[dept_label]
                    job_role = st.text_input("Cargo", defaults.get("job_role", "Sales Executive"))
                    job_level = st.slider("Nível (1-5)", 1, 5, defaults.get("job_level", 2))
                    travel_label = st.selectbox("Frequência de Viagens", list(TRAVEL_OPTS))
                    business_travel = TRAVEL_OPTS[travel_label]
                    overtime_label = st.selectbox("Hora Extra", list(OVERTIME_OPTS))
                    over_time = OVERTIME_OPTS[overtime_label]
                    monthly_income = st.number_input("Salário Mensal (R$)", 1000, 20000, defaults.get("monthly_income", 5000))

        with col3:
            with st.container(border=True):
                st.subheader("Experiência e Satisfação")
                with st.container(border=True):
                    total_working_years = st.number_input("Anos de Experiência", 0, 40, defaults.get("total_working_years", 8))
                    years_at_company = st.number_input("Anos na Empresa", 0, 30, defaults.get("years_at_company", 3))
                    years_in_current_role = st.number_input("Anos no Cargo", 0, 18, defaults.get("years_in_current_role", 2))
                    years_since_last_promotion = st.number_input("Anos sem Promoção", 0, 15, defaults.get("years_since_last_promotion", 1))
                    job_satisfaction = st.slider("Satisfação no Trabalho (1-4)", 1, 4, defaults.get("job_satisfaction", 3))
                    work_life_balance = st.slider("Equilíbrio Vida-Trabalho (1-4)", 1, 4, defaults.get("work_life_balance", 3))

        submitted = st.form_submit_button("➕ Cadastrar Colaborador", type="primary", use_container_width=True)

        if submitted:
            employee_data = {
                "age": age, "gender": gender, "marital_status": marital_status,
                "education": education, "education_field": education_field,
                "distance_from_home": distance_from_home, "department": department,
                "job_role": job_role, "job_level": job_level,
                "business_travel": business_travel, "over_time": over_time,
                "daily_rate": defaults.get("daily_rate", 800),
                "hourly_rate": defaults.get("hourly_rate", 65),
                "monthly_rate": defaults.get("monthly_rate", 14000),
                "monthly_income": monthly_income,
                "percent_salary_hike": defaults.get("percent_salary_hike", 15),
                "stock_option_level": defaults.get("stock_option_level", 1),
                "total_working_years": total_working_years,
                "years_at_company": years_at_company,
                "years_in_current_role": years_in_current_role,
                "years_since_last_promotion": years_since_last_promotion,
                "years_with_curr_manager": defaults.get("years_with_curr_manager", 2),
                "num_companies_worked": defaults.get("num_companies_worked", 2),
                "training_times_last_year": defaults.get("training_times_last_year", 3),
                "environment_satisfaction": defaults.get("environment_satisfaction", 3),
                "job_involvement": defaults.get("job_involvement", 3),
                "job_satisfaction": job_satisfaction,
                "relationship_satisfaction": defaults.get("relationship_satisfaction", 3),
                "work_life_balance": work_life_balance,
                "performance_rating": defaults.get("performance_rating", 3),
            }

            # Checagem de duplicação — avisa se já existe alguém muito similar
            try:
                check_resp = httpx.get(
                    get_api_url("/employees"),
                    params={"department": department, "page_size": 100},
                    timeout=10,
                )
                if check_resp.status_code == 200:
                    existing = check_resp.json().get("employees", [])
                    dup_matches = [
                        e for e in existing
                        if e.get("job_role") == job_role
                        and abs((e.get("age") or 0) - age) <= 1
                        and abs((e.get("monthly_income") or 0) - monthly_income) <= 300
                        and abs((e.get("years_at_company") or 0) - years_at_company) <= 1
                    ]
                    if dup_matches:
                        ids_sample = ", ".join(f"#{e['id']}" for e in dup_matches[:3])
                        st.warning(
                            f"⚠️ Possível duplicação: {len(dup_matches)} colaborador(es) com perfil muito similar "
                            f"já cadastrado(s) ({ids_sample}). Verifique se é pretendido antes de cadastrar novamente."
                        )
            except Exception:
                pass  # check de duplicação é best-effort

            try:
                resp = httpx.post(get_api_url("/employees"), json=employee_data, timeout=10)
                resp.raise_for_status()
                result = resp.json()
                new_id = result["id"]
                st.success(f"Colaborador cadastrado com ID {new_id}!")
                st.session_state.pop("generated_employee", None)

                # Análise preditiva imediata — dentro de caixa com tema
                with st.container(border=True):
                    st.subheader("🔍 Análise Preditiva do Novo Colaborador")
                    with st.spinner("Rodando modelo preditivo + análise IA..."):
                        try:
                            # 1. Predição
                            pred_resp = httpx.post(
                                get_api_url("/predict"),
                                json={"employee_id": new_id},
                                timeout=30,
                            )
                            pred_resp.raise_for_status()
                            pred = pred_resp.json()

                            prob = pred["attrition_probability"]
                            risk = pred["risk_level"]
                            color_map = {"baixo": "🟢", "médio": "🔵", "alto": "🟠", "crítico": "🔴"}

                            # Caixa interna: risco + fatores SHAP
                            with st.container(border=True):
                                st.markdown(
                                    f"**Risco de Saída:** {color_map.get(risk, '⚪')} "
                                    f"{risk.upper()} ({prob:.1%})".replace("$", r"\$")
                                )
                                if pred.get("top_factors"):
                                    st.markdown("**Fatores principais:**")
                                    for f in pred["top_factors"]:
                                        direction = "⬆️" if f["impact"] == "aumenta_risco" else "⬇️"
                                        fname = f["feature"].split("__")[-1].replace("_", " ").title()
                                        st.markdown(
                                            f"- {direction} {fname} (SHAP: {f['shap_value']:+.3f})".replace("$", r"\$")
                                        )

                            # 2. Análise IA em caixa interna separada
                            factors_str = ", ".join(
                                f"{f['feature']}={f['shap_value']:+.3f}" for f in pred.get("top_factors", [])
                            )
                            prompt = (
                                f"Novo colaborador cadastrado (ID {new_id}). "
                                f"Cargo: {job_role}, Departamento: {department}, Salário: R${monthly_income:,}. "
                                f"Risco previsto: {risk} ({prob:.1%}). Fatores: {factors_str}. "
                                f"Faça uma avaliação rápida deste perfil e sugira ações preventivas."
                            )
                            ai_resp = httpx.post(
                                get_api_url("/agent/chat"),
                                json={"message": prompt},
                                timeout=60,
                            )
                            ai_resp.raise_for_status()
                            with st.container(border=True):
                                st.markdown("**🤖 Análise IA:**")
                                ia_text = ai_resp.json()["response"] or ""
                                st.markdown(ia_text.replace("$", r"\$"))

                        except Exception as e:
                            st.warning(f"Análise preditiva falhou: {e}")

            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

with tab_listar:
    # Tradução EN → PT na exibição (valores reais no banco continuam em EN)
    from components.translations import tr_dept, tr_role, tr_overtime

    # Mapeamentos PT → raw pra filtrar corretamente no backend
    DEPT_MAP_LIST = {
        "Vendas": "Sales",
        "Pesquisa e Desenvolvimento": "Research & Development",
        "Recursos Humanos": "Human Resources",
    }
    ROLE_MAP_LIST = {
        "Executivo de Vendas": "Sales Executive",
        "Cientista de Pesquisa": "Research Scientist",
        "Técnico de Laboratório": "Laboratory Technician",
        "Diretor de Manufatura": "Manufacturing Director",
        "Representante de Saúde": "Healthcare Representative",
        "Gerente": "Manager",
        "Representante de Vendas": "Sales Representative",
        "Diretor de Pesquisa": "Research Director",
        "Profissional de RH": "Human Resources",
    }

    # Filtros no mesmo estilo do Dashboard: header + colunas soltas (sem caixa)
    st.markdown("### 🔎 Filtros")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        sel_dept_pt = st.selectbox(
            "Departamento", ["Todos"] + list(DEPT_MAP_LIST.keys()),
            key="filter_dept",
        )
        filter_dept = DEPT_MAP_LIST.get(sel_dept_pt, "Todos")
    with col_f2:
        filter_risk = st.selectbox(
            "Nível de Risco", ["Todos", "crítico", "alto", "médio", "baixo"],
            key="filter_risk",
        )
    with col_f3:
        sel_role_pt = st.selectbox(
            "Cargo", ["Todos"] + list(ROLE_MAP_LIST.keys()),
            key="filter_role_list",
        )
        filter_role = ROLE_MAP_LIST.get(sel_role_pt, "Todos")

    try:
        # Carregar todos de uma vez para a tabela paginar nativamente
        all_emp = []
        page = 1
        while True:
            params = {"page_size": 100, "page": page}
            if filter_dept != "Todos":
                params["department"] = filter_dept
            if filter_risk != "Todos":
                params["risk_level"] = filter_risk
            resp = httpx.get(get_api_url("/employees"), params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            all_emp.extend(data["employees"])
            if len(all_emp) >= data["total"]:
                break
            page += 1

        with st.container(border=True):
            st.subheader("📋 Colaboradores Cadastrados")
            st.caption(f"Total: **{len(all_emp)}** colaboradores")

            if all_emp:
                import pandas as pd
                df = pd.DataFrame(all_emp)

                # Filtro de cargo (client-side) — usa valor raw do mapa
                if filter_role != "Todos":
                    df = df[df["job_role"] == filter_role]

                # Tabela com visual padrão (mesmo do Dashboard e Relatório)
                render_employee_table(
                    df,
                    columns=["id", "age", "job_role", "department", "monthly_income",
                             "over_time", "years_at_company", "risk_score", "risk_level"],
                )
            else:
                st.info("Nenhum colaborador encontrado com os filtros selecionados.")
    except Exception as e:
        st.error(f"Erro ao carregar lista: {e}")

# ═════════════════════════════════════════════════════════════
# ABA: Upload CSV — cadastro em lote + predição imediata
# ═════════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("📤 Upload em lote via CSV")
    st.caption(
        "Envie um CSV com os dados de múltiplos colaboradores para cadastro "
        "em lote. Após o cadastro, o sistema roda predição de risco automaticamente "
        "e devolve o CSV enriquecido com `risk_score` e `risk_level`."
    )

    with st.expander("📋 Ver formato esperado do CSV", expanded=False):
        required_cols = [
            "age", "gender", "marital_status", "education", "education_field",
            "distance_from_home", "department", "job_role", "job_level",
            "business_travel", "over_time", "daily_rate", "hourly_rate",
            "monthly_rate", "monthly_income", "percent_salary_hike",
            "stock_option_level", "total_working_years", "years_at_company",
            "years_in_current_role", "years_since_last_promotion",
            "years_with_curr_manager", "num_companies_worked",
            "training_times_last_year", "environment_satisfaction",
            "job_involvement", "job_satisfaction", "relationship_satisfaction",
            "work_life_balance", "performance_rating",
        ]
        st.code(",".join(required_cols), language="text")
        st.caption("Valores em inglês (ex: gender='Male'/'Female', department='Sales') para compatibilidade com o modelo.")

    uploaded = st.file_uploader("Selecione o CSV", type=["csv"], key="upload_csv")
    if uploaded is not None:
        import pandas as pd

        try:
            df_up = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Falha ao ler CSV: {e}")
            st.stop()

        st.success(f"✅ CSV carregado: {len(df_up)} linhas, {len(df_up.columns)} colunas")
        st.dataframe(df_up.head(10), use_container_width=True, hide_index=True)

        if st.button("🚀 Cadastrar e prever risco", type="primary", use_container_width=True):
            results = []
            failures = []
            prog = st.progress(0, text="Processando...")

            for i, row in df_up.iterrows():
                prog.progress((i + 1) / len(df_up), text=f"Cadastrando linha {i+1}/{len(df_up)}...")
                try:
                    payload = row.to_dict()
                    # Força tipos primitivos (pandas pode trazer numpy types)
                    payload = {k: (int(v) if isinstance(v, (int, float)) and float(v).is_integer() else
                                    v if not isinstance(v, float) else float(v))
                               for k, v in payload.items() if pd.notna(v)}
                    r = httpx.post(get_api_url("/employees"), json=payload, timeout=10)
                    if r.status_code == 201:
                        new_emp = r.json()
                        # Predição
                        pred = httpx.post(
                            get_api_url("/predict"),
                            json={"employee_id": new_emp["id"]},
                            timeout=30,
                        ).json()
                        row_out = dict(payload)
                        row_out["id"] = new_emp["id"]
                        row_out["risk_score"] = pred.get("attrition_probability")
                        row_out["risk_level"] = pred.get("risk_level")
                        results.append(row_out)
                    else:
                        failures.append({"row": i + 1, "error": r.text[:200]})
                except Exception as e:
                    failures.append({"row": i + 1, "error": str(e)[:200]})

            prog.empty()

            col_s1, col_s2 = st.columns(2)
            col_s1.metric("✅ Cadastrados", len(results))
            col_s2.metric("❌ Falhas", len(failures))

            if results:
                df_out = pd.DataFrame(results)
                csv_bytes = df_out.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 Baixar CSV enriquecido (com risco)",
                    data=csv_bytes,
                    file_name="colaboradores_cadastrados_com_risco.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                )
                st.dataframe(
                    df_out[["id", "job_role", "department", "monthly_income", "risk_score", "risk_level"]],
                    use_container_width=True, hide_index=True, height=300,
                )

            if failures:
                with st.expander(f"⚠️ {len(failures)} falha(s) — ver detalhes"):
                    st.dataframe(pd.DataFrame(failures), use_container_width=True, hide_index=True)
