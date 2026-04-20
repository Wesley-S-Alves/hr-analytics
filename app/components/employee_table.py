"""Tabela customizada HTML de colaboradores — mesmo visual da tabela de
"Colaboradores Mais Críticos" do Dashboard.

Uso:
    from components.employee_table import render_employee_table
    render_employee_table(df, columns=["id", "job_role", "department", "monthly_income", "risk_score", "risk_level"])
"""

import streamlit as st

from components.translations import tr_dept, tr_gender, tr_overtime, tr_role

LEVEL_COLORS = {
    "baixo": "#10B981",
    "médio": "#3B82F6",
    "alto": "#F59E0B",
    "crítico": "#DC2626",
}

# Configuração visual por coluna: label, ratio (flex), alinhamento, formatter
_COLUMN_SPECS = {
    "id": {"label": "ID", "ratio": 0.5, "align": "right",
           "format": lambda v, _r: f"<span style='color:#94A3B8; font-size:0.85rem;'>{int(v)}</span>"},
    "age": {"label": "Idade", "ratio": 0.6, "align": "center",
            "format": lambda v, _r: f"<span style='color:#94A3B8; font-size:0.85rem;'>{int(v)}</span>"},
    "job_role": {"label": "Cargo", "ratio": 1.8, "align": "left",
                 "format": lambda v, _r: f"<span style='color:#FAFAFA; font-size:0.88rem;'>{tr_role(v or '')}</span>"},
    "department": {"label": "Departamento", "ratio": 1.5, "align": "left",
                   "format": lambda v, _r: f"<span style='color:#FAFAFA; font-size:0.88rem;'>{tr_dept(v or '')}</span>"},
    "gender": {"label": "Gênero", "ratio": 0.9, "align": "left",
               "format": lambda v, _r: f"<span style='color:#94A3B8; font-size:0.85rem;'>{tr_gender(v or '')}</span>"},
    "monthly_income": {"label": "Salário", "ratio": 1.0, "align": "right",
                       "format": lambda v, _r: f"<span style='color:#FAFAFA; font-size:0.88rem;'>R$ {int(v or 0):,}</span>"},
    "over_time": {"label": "H.Extra", "ratio": 0.8, "align": "center",
                  "format": lambda v, _r: f"<span style='color:#94A3B8; font-size:0.85rem;'>{tr_overtime(v or '')}</span>"},
    "years_at_company": {"label": "Anos", "ratio": 0.7, "align": "center",
                         "format": lambda v, _r: f"<span style='color:#94A3B8; font-size:0.85rem;'>{int(v or 0)}</span>"},
    "risk_score": {"label": "Score", "ratio": 0.9, "align": "right",
                   "format": lambda v, r: _format_risk_score(v, r)},
    "risk_level": {"label": "Nível", "ratio": 1.0, "align": "center",
                   "format": lambda v, _r: _format_risk_badge(v)},
}


def _format_risk_score(v, r) -> str:
    """Formata score com cor baseada no risk_level."""
    if v is None:
        return "<span style='color:#94A3B8;'>—</span>"
    level = (r.get("risk_level") or "").lower()
    color = LEVEL_COLORS.get(level, "#94A3B8")
    return f"<span style='color:{color}; font-weight:700; font-size:0.95rem;'>{v:.1%}</span>"


def _format_risk_badge(v) -> str:
    """Badge colorido com o nível de risco."""
    if not v:
        return "<span style='color:#94A3B8;'>—</span>"
    level = v.lower()
    color = LEVEL_COLORS.get(level, "#94A3B8")
    r_hex, g_hex, b_hex = color[1:3], color[3:5], color[5:7]
    badge_bg = f"rgba({int(r_hex,16)}, {int(g_hex,16)}, {int(b_hex,16)}, 0.2)"
    return (
        f"<span style='background:{badge_bg}; color:{color}; padding:0.25rem 0.7rem;"
        f" border-radius:4px; font-weight:700; font-size:0.78rem; text-transform:uppercase;"
        f" letter-spacing:0.5px;'>{level.capitalize()}</span>"
    )


def render_employee_table(df, columns: list[str]) -> None:
    """Renderiza tabela HTML de colaboradores com visual consistente.

    Args:
        df: DataFrame com colunas conforme `columns`.
        columns: lista de nomes de colunas a exibir. Valores aceitos:
            id, age, job_role, department, gender, monthly_income, over_time,
            years_at_company, risk_score, risk_level.
    """
    # Valida colunas suportadas
    specs = [(c, _COLUMN_SPECS[c]) for c in columns if c in _COLUMN_SPECS]
    if not specs:
        st.info("Sem colunas suportadas para renderizar.")
        return

    ratios = [s["ratio"] for _, s in specs]
    grid_cols = " ".join(f"{r}fr" for r in ratios)

    # Header
    header_cells = ""
    for _col, spec in specs:
        align = spec["align"]
        header_cells += (
            f"<div style='text-align:{align};'>{spec['label']}</div>"
        )
    header_html = (
        f"<div style='display:grid; grid-template-columns: {grid_cols}; gap:0.5rem;"
        f" padding: 0.6rem 0.5rem; border-bottom: 1px solid rgba(45,55,72,0.6);"
        f" color:#94A3B8; font-size:0.68rem; text-transform:uppercase;"
        f" letter-spacing:0.5px; font-weight:700;'>"
        f"{header_cells}"
        f"</div>"
    )

    # Linhas
    rows_html = ""
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        cells = ""
        for col, spec in specs:
            value = row_dict.get(col)
            align = spec["align"]
            cell_content = spec["format"](value, row_dict)
            cells += f"<div style='text-align:{align};'>{cell_content}</div>"
        rows_html += (
            f"<div style='display:grid; grid-template-columns: {grid_cols};"
            f" gap:0.5rem; padding: 0.7rem 0.5rem;"
            f" border-bottom: 1px solid rgba(45,55,72,0.4); align-items:center;'>"
            f"{cells}"
            f"</div>"
        )

    # Remove border-bottom do último item (visual mais limpo)
    if rows_html:
        parts = rows_html.rsplit("border-bottom: 1px solid rgba(45,55,72,0.4);", 1)
        rows_html = "border-bottom: none;".join(parts) if len(parts) == 2 else parts[0]

    st.markdown(
        f"<div style='background:#0F1420; border:1px solid #2D3748; border-radius:6px;"
        f" padding: 0.4rem 0.6rem 1.2rem 0.6rem;'>"
        f"{header_html}{rows_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
