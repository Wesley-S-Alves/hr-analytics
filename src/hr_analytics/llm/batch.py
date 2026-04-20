"""Processamento de insights LLM em batch.

Usa async + semaphore + multi-item prompts para economia de tokens
e throughput.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from hr_analytics.config import settings
from hr_analytics.llm.client import GeminiClient
from hr_analytics.llm.prompts import SYSTEM_PROMPT, build_multi_item_prompt
from hr_analytics.monitoring.observability import MetricType, RequestMetrics, tracker

logger = logging.getLogger(__name__)


@dataclass
class LLMStats:
    """Estatísticas de uso do LLM."""

    total_requests: int = 0
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_s: float = 0.0
    latencies: list = field(default_factory=list)

    @property
    def avg_latency_s(self) -> float:
        return self.total_latency_s / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def tokens_saved_estimate(self) -> int:
        """Tokens economizados pelo batching vs 1 item por request."""
        if self.total_requests == 0:
            return 0
        avg_items = self.total_items / self.total_requests
        system_prompt_tokens = 400  # estimativa
        return int(system_prompt_tokens * (avg_items - 1) * self.total_requests)

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "total_items": self.total_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "tokens_saved_estimate": self.tokens_saved_estimate,
            "avg_latency_s": round(self.avg_latency_s, 3),
        }


def _parse_multi_response(response_text: str, employee_ids: list[int]) -> list[dict]:
    """Parseia resposta JSON array do LLM, fazendo match por employee_id."""
    raw = json.loads(response_text)

    if isinstance(raw, dict):
        raw = [raw]

    results_by_id = {}
    for entry in raw:
        eid = entry.get("id", 0)
        results_by_id[eid] = {
            "employee_id": eid,
            "risk_level": entry.get("risk_level", "desconhecido"),
            "main_factors": entry.get("main_factors", []),
            "recommended_actions": entry.get("recommended_actions", []),
            "summary": entry.get("summary", ""),
        }

    results = []
    for eid in employee_ids:
        if eid in results_by_id:
            results.append(results_by_id[eid])
        else:
            results.append(
                {
                    "employee_id": eid,
                    "risk_level": "erro",
                    "main_factors": [],
                    "recommended_actions": [],
                    "summary": "LLM não retornou análise para este colaborador",
                }
            )

    return results


async def _classify_chunk_async(
    client: GeminiClient,
    items: list[dict],
    semaphore: asyncio.Semaphore,
    stats: LLMStats,
    timeout: float = 120.0,
) -> list[dict]:
    """Processa um chunk de colaboradores via LLM async.

    Args:
        client: Cliente Gemini.
        items: Lista de colaboradores do chunk.
        semaphore: Semaphore para rate limiting.
        stats: Estatísticas acumuladas.
        timeout: Timeout por chunk em segundos.

    Returns:
        Lista de insights gerados.
    """
    async with semaphore:
        prompt = build_multi_item_prompt(items)
        employee_ids = [item["employee_id"] for item in items]

        max_retries = settings.llm_max_retries
        for attempt in range(max_retries):
            metrics = RequestMetrics(
                metric_type=MetricType.LLM_BATCH,
                endpoint="/insights/batch",
            )
            try:
                start = time.time()
                response_text, input_tokens, output_tokens = await asyncio.wait_for(
                    client.generate_async(prompt, SYSTEM_PROMPT),
                    timeout=timeout,
                )
                latency = time.time() - start

                results = _parse_multi_response(response_text, employee_ids)

                # Atualizar estatísticas
                stats.total_requests += 1
                stats.total_input_tokens += input_tokens
                stats.total_output_tokens += output_tokens
                stats.total_latency_s += latency
                stats.latencies.append(latency)
                for r in results:
                    stats.total_items += 1
                    if r["risk_level"] != "erro":
                        stats.successful_items += 1
                    else:
                        stats.failed_items += 1

                # Observabilidade
                metrics.input_tokens = input_tokens
                metrics.output_tokens = output_tokens
                metrics.items_processed = len(results)
                tracker.record(metrics)

                return results

            except asyncio.TimeoutError:
                logger.warning("Timeout LLM (tentativa %d/%d, %.0fs)", attempt + 1, max_retries, timeout)
                await asyncio.sleep(5 * (attempt + 1))

            except json.JSONDecodeError:
                logger.warning("JSON inválido na resposta (tentativa %d/%d)", attempt + 1, max_retries)
                await asyncio.sleep(2)

            except Exception as e:
                logger.warning("Erro Gemini (tentativa %d/%d): %s", attempt + 1, max_retries, e)
                if "429" in str(e) or "quota" in str(e).lower():
                    await asyncio.sleep(60 * (attempt + 1))
                else:
                    await asyncio.sleep(2**attempt)

        # Todas as tentativas falharam
        stats.total_requests += 1
        failed_results = []
        for eid in employee_ids:
            stats.total_items += 1
            stats.failed_items += 1
            failed_results.append(
                {
                    "employee_id": eid,
                    "risk_level": "erro",
                    "main_factors": [],
                    "recommended_actions": [],
                    "summary": "Falha na geração de insight — necessita revisão humana",
                }
            )

        metrics.success = False
        metrics.error_message = "Todas as tentativas falharam"
        tracker.record(metrics)

        return failed_results


async def generate_insights_batch_async(
    items: list[dict],
    concurrency: int | None = None,
    items_per_request: int | None = None,
) -> tuple[list[dict], LLMStats]:
    """Gera insights em batch com concorrência async.

    Args:
        items: Lista de dicionários com dados dos colaboradores.
        concurrency: Máximo de requests simultâneos.
        items_per_request: Colaboradores por request.

    Returns:
        Tupla (lista de insights, estatísticas).
    """
    concurrency = concurrency or settings.llm_concurrency
    items_per_request = items_per_request or settings.llm_items_per_request

    client = GeminiClient()
    semaphore = asyncio.Semaphore(concurrency)
    stats = LLMStats()

    # Dividir em chunks
    chunks = [items[i : i + items_per_request] for i in range(0, len(items), items_per_request)]

    total_chunks = len(chunks)
    completed = 0

    async def _process_and_track(chunk, chunk_idx):
        nonlocal completed
        result = await _classify_chunk_async(client, chunk, semaphore, stats, timeout=settings.llm_timeout)
        completed += 1
        if completed % 5 == 0 or completed == total_chunks:
            logger.info(
                "  LLM batch: %d/%d chunks (%.0f%%)",
                completed,
                total_chunks,
                100 * completed / total_chunks,
            )
        return result

    tasks = [_process_and_track(chunk, i) for i, chunk in enumerate(chunks)]
    chunk_results = await asyncio.gather(*tasks)

    # Flatten
    results = []
    for chunk in chunk_results:
        results.extend(chunk)

    logger.info(
        "Batch LLM concluído: %d itens, %d tokens, %.1fs",
        stats.total_items,
        stats.total_tokens,
        stats.total_latency_s,
    )

    return results, stats


async def generate_insights_batch(items: list[dict]) -> list[dict]:
    """Wrapper simplificado que retorna apenas os insights."""
    results, _ = await generate_insights_batch_async(items)
    return results
