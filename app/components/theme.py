"""Tema visual centralizado do app Streamlit.

Uso:
    from components.theme import apply_theme
    apply_theme()                       # tema padrão
    apply_theme(extra_css=CHAT_EXTRA)   # com CSS específico da página

Constantes de cor exportadas pra uso em componentes Python (Plotly, HTML inline):
    COLOR_BG_OUTER, COLOR_BG_INNER, COLOR_BORDER_OUTER, COLOR_BORDER_INNER,
    COLOR_PRIMARY, COLOR_HOVER, COLOR_LOW, COLOR_MED, COLOR_HIGH, COLOR_CRITICAL
"""

import streamlit as st

# ═══════════════════════════════════════════════════════════════
# Paleta — única fonte de verdade para cores do app
# ═══════════════════════════════════════════════════════════════

# Fundos (2 camadas: externa + interna)
COLOR_BG_OUTER = "#1E2538"
COLOR_BG_INNER = "#0F1420"
COLOR_BG_HOVER = "#252D44"

# Bordas
COLOR_BORDER_OUTER = "#3A4660"
COLOR_BORDER_INNER = "#2D3748"
COLOR_BORDER_HOVER = "#5C6A85"

# Texto
COLOR_TEXT = "#FAFAFA"
COLOR_TEXT_MUTED = "#94A3B8"

# Cor primária (ciano — accent do tema)
COLOR_PRIMARY = "#00BCD4"

# Cores por nível de risco (consistentes em todo o app)
COLOR_LOW = "#10B981"       # verde
COLOR_MED = "#3B82F6"       # azul
COLOR_HIGH = "#F59E0B"      # âmbar
COLOR_CRITICAL = "#DC2626"  # vermelho


# ═══════════════════════════════════════════════════════════════
# CSS core — aplicado em todas as páginas
# ═══════════════════════════════════════════════════════════════

_CORE_CSS = f"""
    /* Caixa externa: container(border=True) — stVerticalBlock dentro do stLayoutWrapper
       Padding top=1rem, bottom=1.4rem (respiro extra embaixo onde cai o conteúdo) */
    [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{
        background-color: {COLOR_BG_OUTER} !important;
        border: 1px solid {COLOR_BORDER_OUTER} !important;
        border-radius: 10px !important;
        padding: 1rem 1.1rem 2rem 1.1rem !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4) !important;
    }}
    /* Caixa interna: Plotly charts + DataFrames */
    [data-testid="stPlotlyChart"],
    [data-testid="stDataFrame"] {{
        background-color: {COLOR_BG_INNER} !important;
        border: 1px solid {COLOR_BORDER_INNER} !important;
        border-radius: 6px !important;
        padding: 0.6rem !important;
    }}
    /* Expander — mesma paleta das caixas */
    [data-testid="stExpander"] {{
        background-color: {COLOR_BG_OUTER} !important;
        border: 1px solid {COLOR_BORDER_OUTER} !important;
        border-radius: 8px !important;
    }}
    [data-testid="stExpander"] > details > summary {{
        background-color: {COLOR_BG_OUTER} !important;
        color: {COLOR_TEXT} !important;
        font-weight: 600 !important;
    }}
    [data-testid="stExpander"] > details > summary:hover {{
        background-color: {COLOR_BG_HOVER} !important;
    }}
    [data-testid="stExpander"] > details > div {{
        background-color: {COLOR_BG_INNER} !important;
        border-top: 1px solid {COLOR_BORDER_INNER} !important;
    }}
    /* Botões primary + download + form submit — mata o azul claro padrão do Streamlit */
    [data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stDownloadButton"] > button {{
        background-color: {COLOR_BG_OUTER} !important;
        color: {COLOR_TEXT} !important;
        border: 1px solid {COLOR_BORDER_OUTER} !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stBaseButton-primary"]:hover,
    [data-testid="stFormSubmitButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover {{
        background-color: {COLOR_BG_HOVER} !important;
        border-color: {COLOR_BORDER_HOVER} !important;
        color: {COLOR_TEXT} !important;
    }}
"""


# ═══════════════════════════════════════════════════════════════
# CSS extras por página — trechos opcionais passados via extra_css
# ═══════════════════════════════════════════════════════════════

# Colunas com altura igual — útil em páginas com cards lado a lado
# (Colaborador, Cadastro form, Comparador)
EXTRA_EQUAL_HEIGHT_COLUMNS = f"""
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
        display: flex;
        flex-direction: column;
    }}
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{
        flex: 1;
    }}
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] [data-testid="stLayoutWrapper"] {{
        height: 100%;
    }}
"""

# Caixa externa com altura 100% (usada no Colaborador pra cards de perfil)
EXTRA_OUTER_FULL_HEIGHT = f"""
    [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{
        height: 100% !important;
    }}
"""

# Expander com padding maior (pra seções grandes como Análise Detalhada)
EXTRA_EXPANDER_LARGE_PADDING = f"""
    [data-testid="stExpander"] > details > summary {{
        padding: 0.9rem 1.1rem !important;
    }}
    [data-testid="stExpander"] > details > div {{
        padding: 1rem 1.1rem !important;
    }}
    [data-testid="stExpander"] {{
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4) !important;
        border-radius: 10px !important;
    }}
"""

# Tema para mensagens do chat (avatars neutros, container escuro)
EXTRA_CHAT = f"""
    [data-testid="stChatMessage"] {{
        background-color: {COLOR_BG_OUTER} !important;
        border: 1px solid {COLOR_BORDER_OUTER} !important;
        border-radius: 10px !important;
        padding: 0.6rem 0.8rem !important;
        margin-bottom: 0.6rem !important;
    }}
    /* Avatar do usuário — ciano do tema (não vermelho) */
    [data-testid="stChatMessageAvatarUser"] {{
        background-color: {COLOR_PRIMARY} !important;
        color: {COLOR_TEXT} !important;
    }}
    /* Avatar da IA — roxo suave (não laranja) */
    [data-testid="stChatMessageAvatarAssistant"] {{
        background-color: #8B5CF6 !important;
        color: {COLOR_TEXT} !important;
    }}
    /* Botões da sidebar (exemplos clicáveis) */
    section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
        background-color: {COLOR_BG_OUTER} !important;
        color: {COLOR_TEXT} !important;
        border: 1px solid {COLOR_BORDER_OUTER} !important;
        border-radius: 8px !important;
        text-align: left !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
        background-color: {COLOR_BG_HOVER} !important;
        border-color: {COLOR_BORDER_HOVER} !important;
    }}
"""

# Tabs estilizadas com accent ciano (usado em Cadastro)
EXTRA_TABS = f"""
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 0.4rem;
        background-color: transparent;
        border-bottom: 1px solid {COLOR_BORDER_OUTER};
    }}
    [data-testid="stTabs"] [data-baseweb="tab"] {{
        color: {COLOR_TEXT_MUTED} !important;
        background-color: transparent !important;
        padding: 0.5rem 1rem !important;
    }}
    [data-testid="stTabs"] [aria-selected="true"] {{
        color: {COLOR_PRIMARY} !important;
        border-bottom: 2px solid {COLOR_PRIMARY} !important;
    }}
"""

# Caixa interna aninhada (2 níveis — usado em Cadastro form)
EXTRA_NESTED_INNER_BOX = f"""
    [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{
        background-color: {COLOR_BG_INNER} !important;
        border: 1px solid {COLOR_BORDER_INNER} !important;
        border-radius: 6px !important;
        padding: 0.8rem 0.9rem !important;
        box-shadow: none !important;
    }}
"""


def apply_theme(extra_css: str | None = None) -> None:
    """Aplica o CSS do tema na página atual.

    Args:
        extra_css: trecho(s) adicional(is) de CSS específicos da página.
            Use as constantes `EXTRA_*` deste módulo ou uma string própria.
            Para combinar vários, basta concatenar: `EXTRA_CHAT + EXTRA_TABS`.

    Exemplo:
        apply_theme()                                # base
        apply_theme(extra_css=EXTRA_CHAT)            # + chat
        apply_theme(extra_css=EXTRA_TABS + EXTRA_NESTED_INNER_BOX)  # múltiplos
    """
    css = _CORE_CSS
    if extra_css:
        css += extra_css
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
