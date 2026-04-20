"""Rota do agente conversacional."""

import uuid

from fastapi import APIRouter

from hr_analytics.inference.schemas import AgentChatRequest, AgentChatResponse, ChartData

router = APIRouter(prefix="/agent", tags=["Agente"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest):
    """Conversa com o agente de People Analytics.

    O agente decide quais tools acionar (predição, explicação, consulta)
    e gera a resposta final com apoio do LLM.
    """
    from hr_analytics.agent.orchestrator import process_message

    conversation_id = request.conversation_id or str(uuid.uuid4())

    result = await process_message(
        message=request.message,
        conversation_id=conversation_id,
    )

    # Construir chart se disponível
    chart = None
    if result.get("chart"):
        chart = ChartData(**result["chart"])

    return AgentChatResponse(
        response=result["response"],
        structured_data=result.get("structured_data"),
        chart=chart,
        conversation_id=conversation_id,
        tools_used=result.get("tools_used", []),
    )
