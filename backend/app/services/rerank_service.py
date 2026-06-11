"""Rerank candidate chunks using the configured SiliconFlow rerank model."""

from __future__ import annotations

import logging
import time
from typing import List, Tuple

import requests

from app.services.model_config import get_model_config

logger = logging.getLogger(__name__)


class RerankService:
    """Second-stage ranker for TopN rulebook chunks."""

    def __init__(self):
        config = get_model_config()
        self.embedding_config = config["embedding"]
        self.rerank_config = config["rerank"]
        self.api_key = self.embedding_config["api_key"]
        self.api_base = self.embedding_config["api_base"].rstrip("/")
        self.model = self.rerank_config["model"]
        self.url = f"{self.api_base}/rerank"
        self.last_timing = {}

    def enabled(self) -> bool:
        return bool(self.rerank_config["enabled"] and self.api_key and self.model)

    def candidate_count(self, fallback: int) -> int:
        if not self.enabled():
            return fallback
        return max(int(self.rerank_config["candidates"]), fallback)

    def top_n(self, fallback: int) -> int:
        if not self.enabled():
            return fallback
        return min(max(int(self.rerank_config["top_n"]), fallback), int(self.rerank_config["candidates"]))

    def rerank(self, query: str, results: List[Tuple[str, float]], top_n: int) -> List[Tuple[str, float]]:
        self.last_timing = {
            "enabled": self.enabled(),
            "candidate_count": len(results),
            "top_n": top_n,
            "rerank_ms": 0,
            "fallback": False,
        }
        if not self.enabled() or not results:
            return results[:top_n]

        documents = [doc for doc, _score in results]
        try:
            started = time.perf_counter()
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "return_documents": False,
                    "top_n": min(top_n, len(documents)),
                },
                timeout=60,
            )
            self.last_timing["rerank_ms"] = round((time.perf_counter() - started) * 1000)
            response.raise_for_status()
            payload = response.json()
            external_scores = {}
            for item in payload.get("results", []):
                index = item.get("index")
                if not isinstance(index, int) or index < 0 or index >= len(results):
                    continue
                score = item.get("relevance_score", item.get("score", results[index][1]))
                external_scores[index] = float(score)
            if external_scores:
                self.last_timing["external_returned"] = len(external_scores)
                self.last_timing["fusion"] = "external_local"
                return self._fuse_rankings(results, external_scores, top_n)
        except Exception as error:
            self.last_timing["fallback"] = True
            logger.warning(f"Rerank failed; falling back to local ranking: {error}")

        return results[:top_n]

    def _fuse_rankings(
        self,
        results: List[Tuple[str, float]],
        external_scores: dict[int, float],
        top_n: int,
    ) -> List[Tuple[str, float]]:
        """Blend external rerank scores with local evidence scores.

        Board-game PDFs often have OCR noise. The local ranker can recognize
        strong rule evidence from keywords and section metadata even when the
        external reranker finds a cleaner but more generic paragraph. Treat the
        external model as a strong signal, not as a full replacement.
        """
        local_scores = [score for _doc, score in results]
        local_norm = self._normalize_scores(local_scores)
        external_norm = self._normalize_score_map(external_scores)
        max_rank = max(len(results) - 1, 1)

        fused = []
        for index, (doc, _score) in enumerate(results):
            local_rank_prior = 1.0 - (index / max_rank)
            score = (
                external_norm.get(index, 0.0) * 0.45
                + local_norm[index] * 0.45
                + local_rank_prior * 0.10
            )
            if index not in external_scores:
                score -= 0.08
            fused.append((doc, score))

        return sorted(fused, key=lambda item: item[1], reverse=True)[:top_n]

    @staticmethod
    def _normalize_scores(scores: List[float]) -> List[float]:
        if not scores:
            return []
        minimum = min(scores)
        maximum = max(scores)
        if maximum == minimum:
            return [1.0 for _score in scores]
        return [(score - minimum) / (maximum - minimum) for score in scores]

    @classmethod
    def _normalize_score_map(cls, scores: dict[int, float]) -> dict[int, float]:
        if not scores:
            return {}
        keys = list(scores.keys())
        normalized = cls._normalize_scores([scores[key] for key in keys])
        return dict(zip(keys, normalized))
