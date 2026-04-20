"""Página 5 — Relatório Consolidado de Retenção em PDF.

Multi-select de colaboradores ou top-N em risco → gera PDF executivo.
"""

from datetime import datetime

import httpx
import pandas as pd
import streamlit as st

from components.employee_table import render_employee_table
from components.pdf_report import build_retention_report_pdf
from components.sidebar import get_api_url
from components.theme import apply_theme
from components.translations import tr_dept, tr_role

st.set_page_config(page_title="Relatório", page_icon="📄", layout="wide")
st.title("📄 Relatório de Ações de Retenção")
st.caption(
    "Gera um PDF consolidado com perfil, risco, fatores SHAP e análise IA "
    "dos colaboradores selecionados. Ideal para reuniões com gestores e liderança de People."
)

# CSS do tema
apply_theme()


@st.cache_data(ttl=60)
def load_employees():
    """Carrega todos os colaboradores."""
    employees = []
    page = 1
    while True:
        try:
            r = httpx.get(
                get_api_url("/employees"),
                params={"page_size": 100, "page": page},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            employees.extend(data["employees"])
            if len(employees) >= data["total"]:
                break
            page += 1
        except Exception:
            break
    return pd.DataFrame(employees)


df_all = load_employees()
if df_all.empty:
    st.warning("Sem dados disponíveis.")
    st.stop()

# ── MODO DE SELEÇÃO ──
st.markdown("### 🎯 Selecione os colaboradores")
mode = st.radio(
    "Modo",
    ["Top N em maior risco", "Selecionar manualmente", "Por departamento"],
    horizontal=True,
)

selected_ids: list[int] = []

if mode == "Top N em maior risco":
    with st.container(border=True):
        col_n, col_info = st.columns([1, 3])
        with col_n:
            n = st.number_input("Quantidade (N)", min_value=1, max_value=50, value=5, step=1)
        df_sorted = df_all[df_all["risk_score"].notna()].sort_values("risk_score", ascending=False)
        top = df_sorted.head(int(n))
        with col_info:
            st.caption(f"**{len(top)}** colaboradores — risco variando de "
                       f"{top['risk_score'].max():.1%} a {top['risk_score'].min():.1%}")
        selected_ids = top["id"].tolist()
        # Tabela com visual consistente do Dashboard (custom HTML)
        render_employee_table(
            top,
            columns=["id", "job_role", "department", "monthly_income", "risk_score", "risk_level"],
        )

elif mode == "Selecionar manualmente":
    with st.container(border=True):
        options = df_all["id"].tolist()
        def _format(eid):
            row = df_all[df_all["id"] == eid].iloc[0]
            risk = f" — {row['risk_level']}" if row.get("risk_level") else ""
            return f"ID {eid} — {tr_role(row['job_role'])} ({tr_dept(row['department'])}){risk}"
        selected_ids = st.multiselect(
            "Colaboradores",
            options=options,
            format_func=_format,
            help="Selecione até 20 colaboradores para manter o PDF legível",
            placeholder="Selecione um ou mais colaboradores",
        )
        if len(selected_ids) > 20:
            st.warning(f"⚠️ Você selecionou {len(selected_ids)}. Recomendamos no máximo 20 por relatório.")

else:  # Por departamento
    with st.container(border=True):
        # Opções traduzidas para PT, mapeando de volta para EN ao filtrar
        dept_raw_options = sorted(df_all["department"].dropna().unique().tolist())
        dept_map_pt_to_raw = {tr_dept(d): d for d in dept_raw_options}
        dept_pt_options = ["Todos"] + sorted(dept_map_pt_to_raw.keys())
        sel_dept_pt = st.selectbox("Departamento", dept_pt_options)
        min_risk = st.slider("Score mínimo de risco", 0.0, 1.0, 0.5, 0.05)
        filtered = df_all[df_all["risk_score"].notna()]
        if sel_dept_pt != "Todos":
            sel_dept_raw = dept_map_pt_to_raw[sel_dept_pt]
            filtered = filtered[filtered["department"] == sel_dept_raw]
        filtered = filtered[filtered["risk_score"] >= min_risk]
        selected_ids = filtered["id"].tolist()
        st.caption(f"**{len(selected_ids)}** colaboradores atendem o filtro")
        if selected_ids:
            render_employee_table(
                filtered,
                columns=["id", "job_role", "department", "risk_score", "risk_level"],
            )

# ── OPÇÕES DO PDF ──
st.markdown("### ⚙️ Opções do relatório")
with st.container(border=True):
    col_o1, col_o2 = st.columns(2)
    with col_o1:
        custom_title = st.text_input(
            "Título", value="Relatório de Ações de Retenção",
        )
    with col_o2:
        include_summary = st.checkbox("Incluir resumo executivo", value=True)
    include_ia = st.checkbox(
        "Incluir análise IA por colaborador",
        value=False,
        help="Gera uma avaliação textual com Gemini para cada colaborador (aumenta tempo + consome tokens).",
    )

# ── GERAR ──
st.markdown("### 🚀 Gerar relatório")

if not selected_ids:
    st.info("Selecione pelo menos 1 colaborador para gerar o relatório.")
    st.stop()

if st.button(f"📄 Gerar PDF ({len(selected_ids)} colaboradores)", type="primary", use_container_width=True):
    employees_data = []
    prog = st.progress(0.0, text="Iniciando...")

    try:
        # ── 1. Predição + SHAP em lote (1 chamada pra todos) ──
        prog.progress(0.15, text=f"Calculando risco de {len(selected_ids)} colaboradores...")
        pred_resp = httpx.post(
            get_api_url("/predict/batch"),
            json={"employee_ids": [int(x) for x in selected_ids]},
            timeout=120,
        )
        pred_resp.raise_for_status()
        predictions_by_id = {p["employee_id"]: p for p in pred_resp.json().get("predictions", [])}

        # ── 2. Dados cadastrais dos colaboradores (1 chamada, filtra client-side) ──
        prog.progress(0.35, text="Carregando dados cadastrais...")
        emp_by_id: dict[int, dict] = {}
        page = 1
        while True:
            r = httpx.get(
                get_api_url("/employees"),
                params={"page_size": 100, "page": page},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            for e in data["employees"]:
                if e["id"] in set(selected_ids):
                    emp_by_id[e["id"]] = e
            if len(emp_by_id) >= len(selected_ids) or len(data["employees"]) == 0:
                break
            page += 1

        # ── 3. Insights LLM em batch (se solicitado) — UMA chamada async ──
        insights_by_id: dict[int, dict] = {}
        if include_ia:
            prog.progress(0.55, text=f"Gerando análise IA em batch (async + semaphore) para {len(selected_ids)}...")
            try:
                ai_resp = httpx.post(
                    get_api_url("/insights/batch"),
                    json=[int(x) for x in selected_ids],
                    timeout=300,  # batch de N colaboradores pode levar mais tempo
                )
                ai_resp.raise_for_status()
                for ins in ai_resp.json().get("insights", []):
                    insights_by_id[ins["employee_id"]] = ins
            except Exception as e:
                st.warning(f"⚠️ Batch LLM falhou — PDF será gerado sem análise IA. Erro: {e}")

        # ── 4. Monta employees_data no formato esperado pelo PDF ──
        prog.progress(0.85, text="Montando PDF...")
        for eid in selected_ids:
            pred = predictions_by_id.get(eid)
            emp = emp_by_id.get(eid)
            if not pred or not emp:
                st.warning(f"Falha em #{eid}: dados incompletos")
                continue

            emp_data = {
                "employee_id": eid,
                "job_role": emp.get("job_role"),
                "department": emp.get("department"),
                "monthly_income": emp.get("monthly_income", 0),
                "years_at_company": emp.get("years_at_company", 0),
                "attrition_probability": pred.get("attrition_probability", 0),
                "risk_level": pred.get("risk_level", "—"),
                "top_factors": pred.get("top_factors", []),
            }

            # Converte insight estruturado (JSON) em markdown pra caber no PDF
            ins = insights_by_id.get(eid)
            if ins:
                parts = []
                if ins.get("summary"):
                    parts.append(f"**Resumo**\n\n{ins['summary']}")
                if ins.get("main_factors"):
                    factors_md = "\n".join(f"- {f}" for f in ins["main_factors"])
                    parts.append(f"**Fatores principais**\n\n{factors_md}")
                if ins.get("recommended_actions"):
                    actions_md = "\n".join(f"- {a}" for a in ins["recommended_actions"])
                    parts.append(f"**Ações recomendadas**\n\n{actions_md}")
                emp_data["ai_report"] = "\n\n".join(parts)

            employees_data.append(emp_data)

        prog.empty()
    except Exception as e:
        prog.empty()
        st.error(f"Erro ao processar lote: {e}")
        st.stop()

    if not employees_data:
        st.error("Nenhum colaborador processado com sucesso.")
        st.stop()

        try:
            pdf_bytes = build_retention_report_pdf(
                employees_data,
                title=custom_title,
                include_executive_summary=include_summary,
            )
        except ImportError:
            st.error("ReportLab não instalado. Execute: `pip install reportlab`")
            st.stop()
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
            st.stop()

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.success(f"✅ PDF gerado com {len(employees_data)} colaborador(es)")
        st.download_button(
            "📥 Baixar PDF",
            data=pdf_bytes,
            file_name=f"relatorio_retencao_{ts}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
