"""
Vector similarity search with numpy matrix acceleration.

Extracted from simple_server.py; replaces per-element Python loops with
numpy batch dot product for ~10-50x speedup on large candidate sets.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def cosine_search(
    query_vec: list[float],
    candidates: list[dict[str, Any]],
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """
    Return the *top_k* most similar candidates (descending) given a
    normalized query vector and a list of candidate dicts each carrying
    an ``embedding`` field.

    The embeddings are assumed to be L2-normalized (or near-normalized) so
    that ``dot(q, c)`` approximates cosine similarity.
    """
    if not query_vec or not candidates:
        return []

    qdim = len(query_vec)
    q_arr = np.asarray(query_vec, dtype=np.float32)

    valid_indices: list[int] = []
    emb_rows: list[list[float]] = []
    for i, c in enumerate(candidates):
        emb = c.get("embedding") if isinstance(c.get("embedding"), list) else []
        if not emb or len(emb) != qdim:
            continue
        valid_indices.append(i)
        emb_rows.append(emb)

    if not emb_rows:
        return []

    mat = np.asarray(emb_rows, dtype=np.float32)  # (N, dim)
    scores = mat @ q_arr                            # (N,)

    if top_k >= len(valid_indices):
        top_idx = np.argsort(-scores)
    else:
        top_idx = np.argpartition(-scores, top_k)[:top_k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]

    results: list[dict[str, Any]] = []
    for idx in top_idx:
        c = candidates[valid_indices[int(idx)]]
        results.append({
            "unit_key": c.get("unit_key"),
            "unit_type": c.get("unit_type"),
            "score": float(scores[idx]),
            "content": c.get("content"),
            "metadata": c.get("metadata"),
        })
    return results
