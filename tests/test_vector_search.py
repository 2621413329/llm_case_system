"""Unit tests for backend/services/vector_search.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest
from backend.services.vector_search import cosine_search


def _make_candidate(key: str, vec: list[float]) -> dict:
    return {"unit_key": key, "unit_type": "page", "embedding": vec, "content": key, "metadata": {}}


class TestCosineSearch:
    def test_empty_candidates(self):
        assert cosine_search([1.0, 0.0, 0.0], []) == []

    def test_empty_query(self):
        c = _make_candidate("a", [1.0, 0.0, 0.0])
        assert cosine_search([], [c]) == []

    def test_single_exact_match(self):
        q = [1.0, 0.0, 0.0]
        c = _make_candidate("a", [1.0, 0.0, 0.0])
        results = cosine_search(q, [c], top_k=1)
        assert len(results) == 1
        assert results[0]["unit_key"] == "a"
        assert abs(results[0]["score"] - 1.0) < 1e-5

    def test_ranking_order(self):
        q = [1.0, 0.0, 0.0]
        candidates = [
            _make_candidate("low", [0.0, 1.0, 0.0]),
            _make_candidate("high", [0.9, 0.1, 0.0]),
            _make_candidate("mid", [0.5, 0.5, 0.0]),
        ]
        results = cosine_search(q, candidates, top_k=3)
        assert results[0]["unit_key"] == "high"
        assert results[1]["unit_key"] == "mid"
        assert results[2]["unit_key"] == "low"

    def test_top_k_limits(self):
        q = [1.0, 0.0]
        candidates = [_make_candidate(f"c{i}", [float(i), 1.0]) for i in range(10)]
        results = cosine_search(q, candidates, top_k=3)
        assert len(results) == 3

    def test_dimension_mismatch_skipped(self):
        q = [1.0, 0.0, 0.0]
        candidates = [
            _make_candidate("wrong_dim", [1.0, 0.0]),
            _make_candidate("right_dim", [0.5, 0.5, 0.0]),
        ]
        results = cosine_search(q, candidates, top_k=5)
        assert len(results) == 1
        assert results[0]["unit_key"] == "right_dim"

    def test_missing_embedding_skipped(self):
        q = [1.0, 0.0]
        candidates = [
            {"unit_key": "no_emb", "unit_type": "page", "content": "x", "metadata": {}},
            _make_candidate("has_emb", [0.5, 0.5]),
        ]
        results = cosine_search(q, candidates, top_k=5)
        assert len(results) == 1

    def test_large_batch_performance(self):
        dim = 384
        rng = np.random.default_rng(42)
        q = rng.standard_normal(dim).astype(np.float32).tolist()
        candidates = []
        for i in range(500):
            v = rng.standard_normal(dim).astype(np.float32)
            v = v / np.linalg.norm(v)
            candidates.append(_make_candidate(f"c{i}", v.tolist()))
        results = cosine_search(q, candidates, top_k=10)
        assert len(results) == 10
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
