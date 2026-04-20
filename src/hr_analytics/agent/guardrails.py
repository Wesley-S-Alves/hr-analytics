"""Guardrails do agente: validação de tópico e filtros de I/O.

Três camadas de proteção para manter o agente restrito ao domínio
de People Analytics e retenção de talentos.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Palavras-chave permitidas no domínio de People Analytics
ALLOWED_KEYWORDS = {
    # RH e colaboradores
    "risco",
    "attrition",
    "saída",
    "turnover",
    "colaborador",
    "colaboradores",
    "funcionário",
    "funcionários",
    "empregado",
    "equipe",
    "time",
    "retenção",
    "demissão",
    "desligamento",
    "rotatividade",
    # Fatores de risco
    "salário",
    "salario",
    "remuneração",
    "promoção",
    "promocao",
    "cargo",
    "departamento",
    "satisfação",
    "satisfacao",
    "hora extra",
    "overtime",
    "distância",
    "distancia",
    "treinamento",
    "carreira",
    "estagnação",
    # Modelo e métricas
    "modelo",
    "predição",
    "predicao",
    "previsão",
    "shap",
    "feature",
    "métrica",
    "metrica",
    "roc",
    "auc",
    "precision",
    "recall",
    "f1",
    "probabilidade",
    "score",
    "threshold",
    # MLflow e experimentos
    "mlflow",
    "experimento",
    "treino",
    "treinamento",
    "acurácia",
    # Conceitos de People Analytics e RH (perguntas teóricas)
    "people",
    "analytics",
    "rh",
    "recursos",
    "humanos",
    "gestão",
    "talent",
    "talento",
    "talentos",
    "engajamento",
    "clima",
    "cultura",
    "organizacional",
    "liderança",
    "lider",
    "onboarding",
    "offboarding",
    "headcount",
    "absenteísmo",
    "produtividade",
    "desempenho",
    "avaliação",
    "feedback",
    "práticas",
    "praticas",
    "estratégia",
    "estrategia",
    "melhores",
    # Ações
    "ação",
    "acao",
    "recomendar",
    "sugerir",
    "insight",
    "análise",
    "analise",
    "relatório",
    "relatorio",
    "monitoramento",
    "drift",
    # Visualização e gráficos
    "gráfico",
    "grafico",
    "chart",
    "plotar",
    "plot",
    "visualizar",
    "comparar",
    "comparação",
    "comparacao",
    "distribuição",
    "distribuicao",
    "histograma",
    "barra",
    "pizza",
    "tabela",
    "mostrar",
    "exibir",
    # Dados demográficos e agrupamentos
    "sexo",
    "gênero",
    "genero",
    "idade",
    "setor",
    "área",
    "area",
    "média",
    "media",
    "total",
    "quantidade",
    "percentual",
    "porcentagem",
    # Consultas genéricas válidas
    "quem",
    "qual",
    "quais",
    "quanto",
    "quantos",
    "quantas",
    "por que",
    "porque",
    "como",
    "onde",
    "maior",
    "menor",
    "alto",
    "baixo",
    "crítico",
    "lista",
    "listar",
    "todos",
    "top",
    "ranking",
    "por",
    # Follow-ups contextuais (mantém conversa natural sobre o mesmo assunto)
    "fazer",
    "faço",
    "faz",
    "faria",
    "fazendo",
    "posso",
    "pode",
    "podemos",
    "podem",
    "poderia",
    "devo",
    "deve",
    "devemos",
    "deveria",
    "ajudar",
    "ajuda",
    "ajudo",
    "falar",
    "falo",
    "conversar",
    "conversa",
    "dar",
    "dou",
    "dá",
    "damos",
    "evitar",
    "evito",
    "prevenir",
    "mitigar",
    "reduzir",
    "melhorar",
    "mudar",
    "mudo",
    "mude",
    "alterar",
    "ajustar",
    "ajuste",
    "agir",
    "intervir",
    "abordar",
    "tratar",
    "há",
    "houve",  # "tem/têm/existe" removidos — genéricos demais, viravam false positives
    "algo",
    "alguma",
    "algum",
    "alguém",
    "nada",
    "ele",
    "ela",
    "eles",
    "elas",
    "dele",
    "dela",
    "deles",
    "delas",
    "isso",
    "esse",
    "essa",
    "esta",
    "este",
    "aqueles",
    "aquilo",
    "caso",
    "situação",
    "cenário",
    "contexto",
    "motivo",
    "razão",
    "opção",
    "opções",
    "alternativa",
    "alternativas",
    "imediatamente",
    "agora",
    "futuro",
    "próximo",
    "médio",
    "curto",
    "longo",
    "prazo",
}

# Padrões explicitamente proibidos
BLOCKED_PATTERNS = [
    r"receita\s+(de\s+)?",
    r"piada",
    r"conte\s+(uma|um)",
    r"escreva\s+(um\s+)?(código|programa|script)",
    r"traduza?\s+(o\s+|a\s+|isso|este|para\s+(o\s+)?(ingl|espanh|franc|alem|itali|japon|chin))",
    r"(faça|faz)\s+(um\s+)?(poema|música|letra|história)",
    r"(qual|quem)\s+(é|foi)\s+(o|a)\s+(presidente|rei|rainha)",
    r"me\s+ajud[ae]\s+com\s+(matemática|física|química|biologia)",
]


def validate_input(message: str) -> tuple[bool, str]:
    """Valida se a mensagem do usuário está dentro do domínio permitido.

    Estratégia em 2 etapas:
    1. Checa se há padrões explicitamente bloqueados
    2. Checa se há pelo menos uma keyword do domínio

    Args:
        message: Mensagem do usuário.

    Returns:
        Tupla (is_valid, rejection_message).
        Se válido: (True, "").
        Se inválido: (False, "mensagem de rejeição educada").
    """
    msg_lower = message.lower().strip()

    # Etapa 1: Checar padrões bloqueados
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, msg_lower):
            logger.info("Guardrail: mensagem bloqueada por padrão '%s'", pattern)
            return False, (
                "Desculpe, só posso ajudar com questões de People Analytics "
                "e retenção de talentos. Tente perguntar sobre risco de saída "
                "de colaboradores, fatores de attrition ou ações de retenção."
            )

    # Etapa 2: Checar se há keywords do domínio
    words = set(re.findall(r"\w+", msg_lower))
    has_domain_keyword = bool(words & ALLOWED_KEYWORDS)

    # Mensagens curtas (≤ 5 palavras) são aceitas — saudações, IDs, follow-ups curtos
    if len(words) <= 5:
        return True, ""

    # Perguntas contextuais (terminam com "?") com pelo menos 1 palavra de follow-up
    # são aceitas como continuação natural da conversa
    if msg_lower.endswith("?") and has_domain_keyword:
        return True, ""

    if not has_domain_keyword:
        logger.info("Guardrail: mensagem sem keywords de domínio: %s", msg_lower[:100])
        return False, (
            "Desculpe, só posso ajudar com questões de People Analytics "
            "e retenção de talentos. Exemplos de perguntas:\n"
            "- Qual colaborador tem maior risco de saída?\n"
            "- Por que o colaborador 42 está em risco?\n"
            "- Quais ações de retenção são recomendadas?"
        )

    return True, ""


def validate_output(response: str | list) -> tuple[bool, str]:
    """Valida se a resposta do agente está dentro do domínio.

    Checa se a resposta não contém conteúdo claramente fora do escopo.

    Args:
        response: Resposta gerada pelo agente (pode ser str ou list).

    Returns:
        Tupla (is_valid, sanitized_response).
    """
    # Gemini pode retornar lista de parts — converter para string
    if isinstance(response, list):
        response = " ".join(str(part) for part in response)
    if not isinstance(response, str):
        response = str(response)

    resp_lower = response.lower()

    # Padrões que indicam que o LLM saiu do escopo
    off_topic_indicators = [
        "como fazer um bolo",
        "ingredientes:",
        "modo de preparo:",
        "def main():",
        "import os\n",
        "once upon a time",
        "era uma vez",
    ]

    for indicator in off_topic_indicators:
        if indicator in resp_lower:
            logger.warning("Guardrail output: resposta contém conteúdo off-topic")
            return False, (
                "Desculpe, não consigo responder a essa pergunta. "
                "Posso ajudar com análises de People Analytics e retenção de talentos."
            )

    return True, response
