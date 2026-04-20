"""Gerador de relatórios PDF de retenção (único + batch).

Usa ReportLab. Inclui capa, resumo executivo, e seção por colaborador
com perfil, risco, fatores SHAP, ações recomendadas e análise IA.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

# ReportLab é importado lazy dentro da função pra a página abrir
# mesmo se o pacote estiver faltando — aí retornamos erro amigável.

RISK_COLOR_MAP = {
    "baixo": "#10B981",
    "médio": "#3B82F6",
    "alto": "#F59E0B",
    "crítico": "#DC2626",
}


def _strip_emojis(text: str) -> str:
    """Remove emojis — Helvetica do ReportLab não suporta."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U0001F1E0-\U0001F1FF"
        "\u200d"
        "\u2640-\u2642"
        "\u23cf\u23e9\u231a\ufe0f\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text or "").strip()


def _md_to_rl(text: str) -> str:
    """Converte markdown simples → tags ReportLab."""
    text = _strip_emojis(text)
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^\*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    return text


def build_retention_report_pdf(
    employees_data: list[dict[str, Any]],
    title: str = "Relatório de Ações de Retenção",
    include_executive_summary: bool = True,
) -> bytes:
    """Constrói um PDF multi-colaborador.

    Args:
        employees_data: lista de dicts com chaves:
            - employee_id, job_role, department, monthly_income, years_at_company
            - attrition_probability, risk_level
            - top_factors (list de {feature, shap_value, impact, magnitude})
            - ai_report (str markdown da análise IA — opcional)
        title: título no header.
        include_executive_summary: inclui página de resumo no início.

    Returns:
        PDF como bytes.
    """
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
        title=title,
        author="People Analytics — HR Intelligence",
    )
    styles = getSampleStyleSheet()

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

    story = []

    # ── CAPA ──
    story.append(Paragraph(title, style_title))
    story.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}<br/>"
        f"Colaboradores analisados: {len(employees_data)}",
        style_subtitle,
    ))
    story.append(Spacer(1, 1 * cm))

    # ── RESUMO EXECUTIVO ──
    if include_executive_summary and employees_data:
        story.append(Paragraph("Resumo Executivo", style_h2))
        counts = {"crítico": 0, "alto": 0, "médio": 0, "baixo": 0}
        for e in employees_data:
            counts[e.get("risk_level", "baixo")] = counts.get(e.get("risk_level", "baixo"), 0) + 1
        avg_prob = sum(e.get("attrition_probability", 0) for e in employees_data) / len(employees_data)

        summary_data = [
            ["Métrica", "Valor"],
            ["Total analisados", str(len(employees_data))],
            ["Probabilidade média de saída", f"{avg_prob:.1%}"],
            ["Risco crítico", str(counts["crítico"])],
            ["Risco alto", str(counts["alto"])],
            ["Risco médio", str(counts["médio"])],
            ["Risco baixo", str(counts["baixo"])],
        ]
        tbl = Table(summary_data, colWidths=[8 * cm, 8 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#00BCD4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(tbl)
        story.append(PageBreak())

    # ── SEÇÃO POR COLABORADOR ──
    for idx, emp in enumerate(employees_data):
        emp_id = emp.get("employee_id", "—")
        prob = emp.get("attrition_probability", 0)
        risk_level = emp.get("risk_level", "—")
        risk_color = RISK_COLOR_MAP.get(risk_level, "#6B7280")

        story.append(Paragraph(f"Colaborador #{emp_id}", style_h2))

        # Dados básicos
        id_data = [
            ["Cargo", emp.get("job_role", "—")],
            ["Departamento", emp.get("department", "—")],
            ["Salário Mensal", f"R$ {emp.get('monthly_income', 0):,}"],
            ["Anos na Empresa", str(emp.get("years_at_company", "—"))],
        ]
        id_tbl = Table(id_data, colWidths=[5 * cm, 12 * cm])
        id_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), rl_colors.HexColor("#F1F5F9")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(id_tbl)
        story.append(Spacer(1, 0.4 * cm))

        # Badge de risco
        risk_badge = ParagraphStyle(
            name=f"Risk{idx}", parent=styles["Normal"],
            textColor=rl_colors.white,
            fontSize=13, alignment=TA_CENTER,
            backColor=rl_colors.HexColor(risk_color),
            borderPadding=10, spaceAfter=10,
        )
        story.append(Paragraph(
            f"<b>RISCO: {risk_level.upper()} — {prob:.1%}</b>",
            risk_badge,
        ))

        # Fatores SHAP
        factors = emp.get("top_factors", [])
        if factors:
            story.append(Paragraph("Fatores Principais", style_h3))
            shap_rows = [["Fator", "Impacto"]]
            for f in factors:
                fname = f.get("feature", "").split("__")[-1].replace("_", " ").title()
                direction = "↑ Aumenta risco" if f.get("shap_value", 0) > 0 else "↓ Diminui risco"
                shap_rows.append([fname, direction])
            shap_tbl = Table(shap_rows, colWidths=[11 * cm, 6 * cm])
            shap_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#00BCD4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [rl_colors.white, rl_colors.HexColor("#F8FAFC")]),
            ]))
            story.append(shap_tbl)
            story.append(Spacer(1, 0.5 * cm))

        # Análise IA (se tiver)
        ai_report = emp.get("ai_report", "")
        if ai_report:
            story.append(Paragraph("Análise IA", style_h3))
            for line in ai_report.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("### "):
                    story.append(Paragraph(_md_to_rl(line[4:]), style_h3))
                elif line.startswith("## "):
                    story.append(Paragraph(_md_to_rl(line[3:]), style_h3))
                elif line.startswith(("- ", "* ")):
                    story.append(Paragraph("• " + _md_to_rl(line[2:]), style_bullet))
                elif set(line) <= set("-*= "):
                    continue
                else:
                    story.append(Paragraph(_md_to_rl(line), style_body))

        # Page break entre colaboradores (exceto último)
        if idx < len(employees_data) - 1:
            story.append(PageBreak())

    # Rodapé
    story.append(Spacer(1, 0.8 * cm))
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
    return buffer.getvalue()
