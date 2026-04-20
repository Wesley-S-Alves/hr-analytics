"""Wrapper do Google Gemini com suporte sync e async.

lazy init, config centralizada,
JSON mode com temperature=0.
"""

import logging
import os

from hr_analytics.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Cliente Gemini com lazy initialization e configuração centralizada."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-flash-latest",
    ):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model
        self._client = None

    @property
    def client(self):
        """Lazy init do client Gemini."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def reset_client(self):
        """Reseta o client (necessário antes de asyncio.run)."""
        self._client = None

    def _make_config(self, system_instruction: str) -> dict:
        """Cria configuração padrão para chamadas."""
        return {
            "system_instruction": system_instruction,
            "temperature": 0,
            "response_mime_type": "application/json",
        }

    def generate_sync(self, prompt: str, system_instruction: str) -> tuple[str, int, int]:
        """Chamada síncrona ao Gemini.

        Args:
            prompt: Texto do prompt.
            system_instruction: Instrução de sistema.

        Returns:
            Tupla (response_text, input_tokens, output_tokens).
        """
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self._make_config(system_instruction),
        )
        input_tokens, output_tokens = self._extract_tokens(response)
        return response.text, input_tokens, output_tokens

    async def generate_async(self, prompt: str, system_instruction: str) -> tuple[str, int, int]:
        """Chamada assíncrona ao Gemini.

        Args:
            prompt: Texto do prompt.
            system_instruction: Instrução de sistema.

        Returns:
            Tupla (response_text, input_tokens, output_tokens).
        """
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self._make_config(system_instruction),
        )
        input_tokens, output_tokens = self._extract_tokens(response)
        return response.text, input_tokens, output_tokens

    @staticmethod
    def _extract_tokens(response) -> tuple[int, int]:
        """Extrai contagem de tokens da resposta."""
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        return input_tokens, output_tokens


# Instância global
gemini_client = GeminiClient()
