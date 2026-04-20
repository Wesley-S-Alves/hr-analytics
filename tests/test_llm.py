"""Testes do LLM (client + batch). Mocka Gemini — nunca chama rede."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================
# GeminiClient
# ============================================================


class TestGeminiClient:
    def test_init_explicit_key(self):
        from hr_analytics.llm.client import GeminiClient

        client = GeminiClient(api_key="explicit")
        assert client.api_key == "explicit"

    def test_reset_client(self):
        from hr_analytics.llm.client import GeminiClient

        client = GeminiClient(api_key="x")
        client._client = MagicMock()
        client.reset_client()
        assert client._client is None

    def test_make_config(self):
        from hr_analytics.llm.client import GeminiClient

        config = GeminiClient(api_key="x")._make_config("sys")
        assert config["system_instruction"] == "sys"
        assert config["temperature"] == 0
        assert "json" in config["response_mime_type"]

    def test_generate_sync_mocked(self):
        from hr_analytics.llm.client import GeminiClient

        fake_response = MagicMock()
        fake_response.text = '{"r": "ok"}'
        fake_response.usage_metadata.prompt_token_count = 100
        fake_response.usage_metadata.candidates_token_count = 50

        client = GeminiClient(api_key="x")
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = fake_response
        client._client = fake_client

        text, in_tok, out_tok = client.generate_sync("prompt", "sys")
        assert text == '{"r": "ok"}'
        assert in_tok == 100
        assert out_tok == 50


# ============================================================
# _parse_multi_response
# ============================================================


class TestParseMultiResponse:
    def test_parses_valid_array(self):
        from hr_analytics.llm.batch import _parse_multi_response

        raw = json.dumps(
            [
                {"id": 1, "risk_level": "alto", "main_factors": ["a"], "recommended_actions": ["x"], "summary": "s"},
                {"id": 2, "risk_level": "baixo", "main_factors": [], "recommended_actions": [], "summary": ""},
            ]
        )
        result = _parse_multi_response(raw, [1, 2])
        assert len(result) == 2
        assert result[0]["employee_id"] == 1
        assert result[0]["risk_level"] == "alto"
        assert result[1]["risk_level"] == "baixo"

    def test_fills_missing_ids_with_error(self):
        from hr_analytics.llm.batch import _parse_multi_response

        raw = json.dumps(
            [{"id": 1, "risk_level": "alto", "main_factors": [], "recommended_actions": [], "summary": ""}]
        )
        result = _parse_multi_response(raw, [1, 2, 3])
        assert len(result) == 3
        assert result[0]["risk_level"] == "alto"
        assert result[1]["risk_level"] == "erro"
        assert result[2]["risk_level"] == "erro"

    def test_accepts_single_dict_as_list(self):
        from hr_analytics.llm.batch import _parse_multi_response

        raw = json.dumps({"id": 1, "risk_level": "alto", "main_factors": [], "recommended_actions": [], "summary": ""})
        result = _parse_multi_response(raw, [1])
        assert len(result) == 1
        assert result[0]["risk_level"] == "alto"


# ============================================================
# LLMStats
# ============================================================


class TestLLMStats:
    def test_avg_latency_zero_when_empty(self):
        from hr_analytics.llm.batch import LLMStats

        stats = LLMStats()
        assert stats.avg_latency_s == 0

    def test_avg_latency(self):
        from hr_analytics.llm.batch import LLMStats

        stats = LLMStats(total_requests=2, total_latency_s=10.0)
        assert stats.avg_latency_s == 5.0

    def test_tokens_saved_estimate_with_data(self):
        from hr_analytics.llm.batch import LLMStats

        # 2 requests com 10 items cada → 20 total
        stats = LLMStats(total_requests=2, total_items=20)
        saved = stats.tokens_saved_estimate
        assert saved > 0  # economia > 0 quando há batching

    def test_tokens_saved_zero_without_batching(self):
        from hr_analytics.llm.batch import LLMStats

        # 5 requests com 1 item cada → sem batching, economia = 0
        stats = LLMStats(total_requests=5, total_items=5)
        assert stats.tokens_saved_estimate == 0

    def test_to_dict_has_expected_keys(self):
        from hr_analytics.llm.batch import LLMStats

        d = LLMStats(total_requests=1, total_items=5, successful_items=4, failed_items=1).to_dict()
        assert d["total_requests"] == 1
        assert d["successful_items"] == 4
        assert "avg_latency_s" in d


# ============================================================
# _classify_chunk_async — retry e success path
# ============================================================


class TestClassifyChunkAsync:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        from hr_analytics.llm.batch import LLMStats, _classify_chunk_async

        fake_response = json.dumps(
            [
                {"id": 1, "risk_level": "alto", "main_factors": [], "recommended_actions": [], "summary": "s"},
            ]
        )

        client = MagicMock()
        client.generate_async = AsyncMock(return_value=(fake_response, 100, 50))

        stats = LLMStats()
        semaphore = asyncio.Semaphore(1)
        items = [
            {
                "employee_id": 1,
                "department": "Sales",
                "job_role": "X",
                "monthly_income": 5000,
                "years_at_company": 2,
                "attrition_probability": 0.7,
                "risk_level": "alto",
                "top_factors": [],
            }
        ]

        results = await _classify_chunk_async(client, items, semaphore, stats)
        assert len(results) == 1
        assert results[0]["risk_level"] == "alto"
        assert stats.total_input_tokens == 100
        assert stats.total_output_tokens == 50

    @pytest.mark.asyncio
    async def test_timeout_returns_error_entries(self, monkeypatch):
        from hr_analytics.config import settings
        from hr_analytics.llm.batch import LLMStats, _classify_chunk_async

        # Diminui retries pra teste rodar rápido
        monkeypatch.setattr(settings, "llm_max_retries", 1)

        client = MagicMock()
        client.generate_async = AsyncMock(side_effect=asyncio.TimeoutError())

        stats = LLMStats()
        semaphore = asyncio.Semaphore(1)
        items = [
            {
                "employee_id": 1,
                "department": "X",
                "job_role": "Y",
                "monthly_income": 1,
                "years_at_company": 1,
                "attrition_probability": 0.1,
                "risk_level": "baixo",
                "top_factors": [],
            }
        ]

        # Monkey patch do asyncio.sleep pra não esperar 5s
        async def fast_sleep(_):
            return

        monkeypatch.setattr(asyncio, "sleep", fast_sleep)

        results = await _classify_chunk_async(client, items, semaphore, stats, timeout=0.01)
        # Após max_retries, retorna erros
        assert len(results) == 1
        assert results[0]["risk_level"] == "erro"
        assert stats.failed_items == 1


# ============================================================
# generate_insights_batch_async — fluxo completo mockado
# ============================================================


class TestGenerateInsightsBatchAsync:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        from hr_analytics.llm.batch import generate_insights_batch_async

        # Mockando para não instanciar GeminiClient real
        results, stats = await generate_insights_batch_async([])
        assert results == []
        assert stats.total_requests == 0

    @pytest.mark.asyncio
    async def test_chunks_multiple_items(self, monkeypatch):
        from hr_analytics.llm import batch as batch_module
        from hr_analytics.llm.batch import generate_insights_batch_async

        # Mock de _classify_chunk_async — retorna 1 resultado por item
        async def fake_classify(client, items, semaphore, stats, timeout=120.0):
            return [
                {
                    "employee_id": i["employee_id"],
                    "risk_level": "alto",
                    "main_factors": [],
                    "recommended_actions": [],
                    "summary": "ok",
                }
                for i in items
            ]

        monkeypatch.setattr(batch_module, "_classify_chunk_async", fake_classify)

        items = [
            {
                "employee_id": i,
                "department": "X",
                "job_role": "Y",
                "monthly_income": 1000,
                "years_at_company": 1,
                "attrition_probability": 0.5,
                "risk_level": "médio",
                "top_factors": [],
            }
            for i in range(5)
        ]

        results, stats = await generate_insights_batch_async(
            items,
            concurrency=2,
            items_per_request=2,
        )
        assert len(results) == 5
        assert all(r["risk_level"] == "alto" for r in results)
