"""Helpers Plotly para gráficos do dashboard."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def risk_gauge(probability: float, title: str = "Risco de Saída") -> go.Figure:
    """Cria gauge de risco (velocímetro)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=probability * 100,
        number={"suffix": "%"},
        title={"text": title},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkred" if probability > 0.7 else "orange" if probability > 0.4 else "green"},
            "steps": [
                {"range": [0, 20], "color": "#d4edda"},
                {"range": [20, 40], "color": "#fff3cd"},
                {"range": [40, 70], "color": "#ffeaa7"},
                {"range": [70, 100], "color": "#f8d7da"},
            ],
            "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 70},
        },
    ))
    fig.update_layout(height=250, margin=dict(t=50, b=0, l=20, r=20))
    return fig


def risk_by_department(df: pd.DataFrame) -> go.Figure:
    """Gráfico de barras: risco médio por departamento."""
    dept_risk = df.groupby("department")["risk_score"].agg(["mean", "count"]).reset_index()
    dept_risk.columns = ["Departamento", "Risco Médio", "Colaboradores"]

    fig = px.bar(
        dept_risk.sort_values("Risco Médio", ascending=False),
        x="Departamento",
        y="Risco Médio",
        color="Risco Médio",
        color_continuous_scale=["green", "yellow", "red"],
        text="Colaboradores",
        title="Risco Médio por Departamento",
    )
    fig.update_layout(height=400)
    return fig


def risk_distribution(df: pd.DataFrame) -> go.Figure:
    """Histograma da distribuição de scores de risco."""
    fig = px.histogram(
        df,
        x="risk_score",
        nbins=30,
        title="Distribuição de Scores de Risco",
        labels={"risk_score": "Probabilidade de Attrition"},
        color_discrete_sequence=["#3498db"],
    )
    fig.add_vline(x=0.2, line_dash="dash", line_color="green", annotation_text="Baixo")
    fig.add_vline(x=0.4, line_dash="dash", line_color="orange", annotation_text="Médio")
    fig.add_vline(x=0.7, line_dash="dash", line_color="red", annotation_text="Alto")
    fig.update_layout(height=350)
    return fig


def psi_bar_chart(feature_psi: dict[str, float]) -> go.Figure:
    """Gráfico de barras do PSI por feature."""
    df = pd.DataFrame(list(feature_psi.items()), columns=["Feature", "PSI"])
    df = df.sort_values("PSI", ascending=False).head(20)

    colors = ["red" if v > 0.2 else "orange" if v > 0.1 else "green" for v in df["PSI"]]

    fig = go.Figure(go.Bar(
        x=df["PSI"],
        y=df["Feature"],
        orientation="h",
        marker_color=colors,
    ))
    fig.add_vline(x=0.1, line_dash="dash", line_color="orange")
    fig.add_vline(x=0.2, line_dash="dash", line_color="red")
    fig.update_layout(
        title="PSI por Feature (Top 20)",
        xaxis_title="PSI",
        height=500,
        yaxis=dict(autorange="reversed"),
    )
    return fig
