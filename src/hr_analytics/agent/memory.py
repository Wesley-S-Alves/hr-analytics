"""Gerenciamento de memória/histórico de conversação do agente."""

from collections import defaultdict

from langchain_core.messages import AIMessage, HumanMessage


class ConversationMemory:
    """Armazena histórico de conversações por conversation_id.

    Mantém as últimas N mensagens para cada conversa.
    """

    def __init__(self, max_messages: int = 20):
        self._histories: dict[str, list] = defaultdict(list)
        self._max_messages = max_messages

    def add_human_message(self, conversation_id: str, message: str) -> None:
        """Adiciona mensagem do usuário ao histórico."""
        self._histories[conversation_id].append(HumanMessage(content=message))
        self._trim(conversation_id)

    def add_ai_message(self, conversation_id: str, message: str) -> None:
        """Adiciona resposta do agente ao histórico."""
        self._histories[conversation_id].append(AIMessage(content=message))
        self._trim(conversation_id)

    def get_history(self, conversation_id: str) -> list:
        """Retorna o histórico de uma conversação."""
        return self._histories.get(conversation_id, [])

    def clear(self, conversation_id: str) -> None:
        """Limpa o histórico de uma conversação."""
        self._histories.pop(conversation_id, None)

    def _trim(self, conversation_id: str) -> None:
        """Mantém apenas as últimas N mensagens."""
        history = self._histories[conversation_id]
        if len(history) > self._max_messages:
            self._histories[conversation_id] = history[-self._max_messages :]


# Instância global
conversation_memory = ConversationMemory()
