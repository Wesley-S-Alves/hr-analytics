"""Orquestrador do agente LangChain com Gemini + guardrails.

Fluxo:
1. Input guardrail (valida tópico)
2. LangChain ReAct agent com tools
3. Output guardrail (valida resposta)
"""

import json
import logging

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from hr_analytics.agent.guardrails import validate_input, validate_output
from hr_analytics.agent.memory import conversation_memory
from hr_analytics.agent.tools import ALL_TOOLS
from hr_analytics.config import settings
from hr_analytics.monitoring.observability import MetricType, RequestMetrics, tracker

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = SystemMessage(
    content="""\
Você é um assistente especializado em People Analytics e retenção de talentos.

## REGRA CRÍTICA — SEJA PROATIVO
NUNCA pergunte ao usuário se pode prosseguir. NUNCA peça confirmação.
SEMPRE execute os tools imediatamente e responda com os dados.

ERRADO: "Posso listar os colaboradores com maior risco? Quantos deseja ver?"
CERTO: [executa list_high_risk_employees] "Aqui estão os 10 colaboradores com maior risco..."

ERRADO: "Você gostaria de ver por departamento?"
CERTO: [executa query_employees_analytics] "Aqui está a análise por departamento..."

Se o usuário pedir algo, FAÇA. Não pergunte se pode fazer.

## Seu papel
- Responder perguntas analíticas sobre colaboradores (quantidades, percentuais, médias, distribuições)
- Analisar risco de saída de colaboradores usando o modelo preditivo
- Explicar fatores de risco com base em SHAP values
- Sugerir ações de retenção baseadas em dados

## Quando usar cada tool
- Perguntas analíticas (quantos, percentual, média, por departamento/time/cargo, distribuição, taxa de attrition, headcount): use **query_employees_analytics** com SQL
- IMPORTANTE: Use sempre os termos "attrition" ou "saída de colaboradores". NUNCA use "churn" — esse termo é usado para clientes, não para colaboradores.
- Risco de um colaborador específico: use **predict_employee**
- Ranking de risco / quem tem mais risco: use **query_employees_analytics** com ORDER BY risk_score DESC
- "Por que o colaborador X está em risco?": use **explain_risk_factors**
- Detalhes completos de um colaborador: use **get_employee_details**
- Combinar análises: use MÚLTIPLOS tools na mesma resposta

## Limites de resposta
- Quando listar colaboradores, mostre no MÁXIMO 5 por departamento/grupo (os de maior risco).
- Se o usuário quiser mais, ele vai pedir. Não despeje todos os dados de uma vez.
- Para queries SQL, sempre use LIMIT (ex: LIMIT 5 por grupo).

## Quando usar query_employees_analytics
Esta é a tool mais versátil. Use para QUALQUER pergunta que precise de dados agregados.
Exemplos de queries:
- Colaboradores por departamento: SELECT department, COUNT(*) as total FROM employees WHERE is_active=1 GROUP BY department
- Attrition por departamento: SELECT department, COUNT(*) as total, SUM(CASE WHEN attrition='Yes' THEN 1 ELSE 0 END) as saidas, ROUND(100.0*SUM(CASE WHEN attrition='Yes' THEN 1 ELSE 0 END)/COUNT(*),1) as attrition_pct FROM employees GROUP BY department
- Top risco por time: SELECT department, id, job_role, monthly_income, risk_score, risk_level FROM employees WHERE risk_score IS NOT NULL ORDER BY department, risk_score DESC
- Média salarial: SELECT job_role, ROUND(AVG(monthly_income)) as media_salario FROM employees GROUP BY job_role ORDER BY media_salario DESC

## Formato da resposta
- Responda em português brasileiro, profissional e empático.
- Formate salários como R$ X.XXX.
- Formate percentuais com 1 casa decimal (ex: 16.1%).
- Quando listar dados, use tabelas ou listas organizadas.
- Sempre inclua o nível de risco quando relevante.
- NUNCA termine a resposta com perguntas como "Quer que eu analise...", "Gostaria de ver...", "Deseja que eu...". Apenas apresente os dados de forma completa e encerre.

## Tom da resposta conforme o risco
- Risco BAIXO: tom positivo e tranquilizador. Destaque os pontos fortes do colaborador. Exemplo: "O colaborador apresenta perfil estável com baixo risco de saída. Os indicadores de satisfação e permanência são favoráveis."
- Risco MÉDIO: tom neutro e preventivo. Sugira ações de acompanhamento. Exemplo: "Recomenda-se acompanhamento preventivo nos pontos identificados."
- Risco ALTO/CRÍTICO: tom de alerta construtivo. Foque em ações urgentes. Exemplo: "É necessário atenção imediata nos fatores identificados."

## GUARDRAIL — Restrição de domínio
Você é ESTRITAMENTE restrito ao domínio de People Analytics e Recursos Humanos.

PERMITIDO: risco de saída, attrition, turnover, retenção, dados de colaboradores,
métricas de RH, SHAP, feature importance, ações de retenção, métricas do modelo.

PROIBIDO: receitas, piadas, código, matemática, assuntos fora de RH.
Se pedirem algo proibido, responda EXATAMENTE:
"Desculpe, só posso ajudar com questões de People Analytics e retenção de talentos."
"""
)


def _create_agent():
    """Cria o agente LangChain ReAct com Gemini."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )

    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
    )

    return agent


# Agent singleton
_agent = None


def _get_agent():
    """Retorna o agent singleton, criando se necessário."""
    global _agent
    if _agent is None:
        _agent = _create_agent()
    return _agent


def _extract_response_text(result: dict) -> str:
    """Extrai a resposta textual do agente (content pode ser str ou list de parts)."""
    ai_messages = [m for m in result["messages"] if hasattr(m, "content") and m.content]
    if not ai_messages:
        return "Sem resposta"
    content = ai_messages[-1].content
    if isinstance(content, list):
        return " ".join(part.get("text", str(part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _extract_tools_and_tokens(result: dict) -> tuple[list[str], int, int]:
    """Extrai tools usados e soma input/output tokens das mensagens do agente."""
    tools_used: list[str] = []
    total_input = total_output = 0
    for m in result["messages"]:
        if hasattr(m, "tool_calls") and m.tool_calls:
            for tc in m.tool_calls:
                tools_used.append(tc["name"])
        usage = getattr(m, "usage_metadata", None)
        if usage:
            if isinstance(usage, dict):
                total_input += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)
            else:
                total_input += getattr(usage, "input_tokens", 0) or 0
                total_output += getattr(usage, "output_tokens", 0) or 0
    return tools_used, total_input, total_output


def _extract_structured_and_chart(result: dict) -> tuple[dict | None, dict | None]:
    """Procura JSON de `query_employees_analytics` nos tool messages e gera chart hint."""
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for m in messages:
        if hasattr(m, "content") and isinstance(m.content, str):
            try:
                parsed = json.loads(m.content)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict) and "data" in parsed and "columns" in parsed:
                return parsed, _auto_chart(parsed)
    return None, None


def _rejection_response(metrics: RequestMetrics, rejection_message: str) -> dict:
    """Retorno padrão quando o guardrail rejeita a entrada."""
    metrics.success = True
    tracker.record(metrics)
    return {
        "response": rejection_message,
        "structured_data": None,
        "tools_used": [],
    }


async def process_message(message: str, conversation_id: str) -> dict:
    """Processa uma mensagem do usuário com guardrails.

    Fluxo:
        1. Input guardrail → rejeita se fora do domínio
        2. Adiciona à memória da conversa
        3. Invoca o agente LangChain (ReAct + tools)
        4. Extrai resposta + tokens + tools usados
        5. Output guardrail → sanitiza se necessário
        6. Detecta gráfico a partir dos tool results

    Args:
        message: Mensagem do usuário.
        conversation_id: ID da conversação para manter contexto.

    Returns:
        Dicionário com resposta, dados estruturados, chart e tools usados.
    """
    metrics = RequestMetrics(metric_type=MetricType.AGENT_CALL, endpoint="/agent/chat")

    # 1. Input guardrail
    is_valid, rejection_message = validate_input(message)
    if not is_valid:
        return _rejection_response(metrics, rejection_message)

    # 2. Memória
    conversation_memory.add_human_message(conversation_id, message)
    history = conversation_memory.get_history(conversation_id)

    # 3. Invocar agente
    agent = _get_agent()
    result: dict = {"messages": []}
    tools_used: list[str] = []
    response_text = "Sem resposta"
    try:
        messages = [SYSTEM_MESSAGE] + history
        result = agent.invoke({"messages": messages})
        response_text = _extract_response_text(result)
        tools_used, in_tokens, out_tokens = _extract_tools_and_tokens(result)
        metrics.input_tokens = in_tokens
        metrics.output_tokens = out_tokens
        logger.info(
            "Agente tokens: input=%d, output=%d, tools=%s",
            in_tokens,
            out_tokens,
            tools_used,
        )
    except Exception as e:
        logger.exception("Erro no agente")
        response_text = "Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente ou reformule a pergunta."
        metrics.success = False
        metrics.error_message = str(e)[:500]

    # 4. Output guardrail
    is_valid_output, sanitized_response = validate_output(response_text)
    if not is_valid_output:
        response_text = sanitized_response

    # 5. Memória da resposta
    conversation_memory.add_ai_message(conversation_id, response_text)

    # 6. Dados estruturados + chart
    structured_data, chart_data = _extract_structured_and_chart(result)

    tracker.record(metrics)

    return {
        "response": response_text,
        "structured_data": structured_data,
        "chart": chart_data,
        "tools_used": tools_used,
    }


def _auto_chart(query_result: dict) -> dict | None:
    """Detecta automaticamente o tipo de gráfico adequado para os dados.

    Analisa as colunas e dados retornados pela query SQL e decide:
    - bar: quando há uma coluna categórica + uma numérica
    - pie: quando há poucos grupos (≤6) e uma coluna de contagem/percentual
    - horizontal_bar: quando há muitos grupos (>6)

    Args:
        query_result: Resultado da query com {"data": [...], "columns": [...]}.

    Returns:
        Dicionário com chart_type, title, data ou None se não for plotável.
    """
    data = query_result.get("data", [])
    columns = query_result.get("columns", [])

    if not data or len(columns) < 2:
        return None

    # Identificar colunas categóricas e numéricas
    cat_cols = []
    value_cols = []

    for col in columns:
        sample_val = data[0].get(col)
        if isinstance(sample_val, str):
            cat_cols.append(col)
        elif isinstance(sample_val, (int, float)):
            value_cols.append(col)

    label_col = cat_cols[0] if cat_cols else None
    group_col = cat_cols[1] if len(cat_cols) >= 2 else None  # Segunda dimensão

    if not label_col or not value_cols:
        return None

    # Preferir colunas com "pct", "percent", "media", "avg", "mean", "rate" no nome
    priority_keywords = ["pct", "percent", "media", "avg", "mean", "rate", "attrition", "risk"]
    priority_col = None
    for vc in value_cols:
        if any(kw in vc.lower() for kw in priority_keywords):
            priority_col = vc
            break

    if priority_col:
        # Mover a coluna prioritária para o início
        value_cols.remove(priority_col)
        value_cols.insert(0, priority_col)

    n_groups = len(data)

    # Decidir tipo de gráfico
    if n_groups <= 6:
        # Poucas categorias → verificar se tem percentual → pie, senão bar
        has_pct = any("pct" in c.lower() or "percent" in c.lower() for c in value_cols)
        chart_type = "pie" if has_pct else "bar"
    else:
        chart_type = "horizontal_bar"

    # Usar a primeira coluna numérica como valor principal
    main_value_col = value_cols[0]

    # Construir título baseado nas colunas
    title = f"{main_value_col.replace('_', ' ').title()} por {label_col.replace('_', ' ').title()}"

    # Se tem 2 colunas categóricas → gráfico agrupado (grouped bar)
    if group_col:
        chart_items = []
        for row in data:
            chart_items.append(
                {
                    "label": str(row.get(label_col, "")),
                    "group": str(row.get(group_col, "")),
                    "value": row.get(main_value_col, 0) or 0,
                }
            )

        title = f"{main_value_col.replace('_', ' ').title()} por {label_col.replace('_', ' ').title()} e {group_col.replace('_', ' ').title()}"

        return {
            "chart_type": "grouped_bar",
            "title": title,
            "x_label": label_col.replace("_", " ").title(),
            "y_label": main_value_col.replace("_", " ").title(),
            "group_label": group_col.replace("_", " ").title(),
            "data": chart_items,
        }

    # Coluna única categórica → agregar dados por label
    from collections import defaultdict

    agg = defaultdict(list)
    for row in data:
        label = str(row.get(label_col, ""))
        value = row.get(main_value_col, 0)
        if value is not None:
            agg[label].append(float(value))

    chart_items = []
    for label, values in agg.items():
        if len(set(values)) == 1:
            final_value = values[0]
        else:
            final_value = round(sum(values) / len(values), 2)
        chart_items.append({"label": label, "value": final_value})

    chart_items.sort(key=lambda x: x["value"], reverse=True)

    n_groups = len(chart_items)
    if n_groups <= 6:
        has_pct = any("pct" in c.lower() or "percent" in c.lower() for c in value_cols)
        chart_type = "pie" if has_pct else "bar"
    else:
        chart_type = "horizontal_bar"

    return {
        "chart_type": chart_type,
        "title": title,
        "x_label": label_col.replace("_", " ").title(),
        "y_label": main_value_col.replace("_", " ").title(),
        "data": chart_items,
    }
