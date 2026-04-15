"""
向量检索调试：解释一次 query 的 topK 命中及异常低分标记。
"""

from __future__ import annotations

from typing import Any

try:
    from backend.services.vector_search import cosine_search
except Exception:  # pragma: no cover
    from services.vector_search import cosine_search  # type: ignore


def debug_vector_query(
    query_text: str,
    query_vec: list[float],
    candidates: list[dict[str, Any]],
    *,
    top_k: int = 12,
    low_score_threshold: float = 0.5,
) -> dict[str, Any]:
    """
    返回结构化调试结果，便于前端表格展示。
    """
    q = str(query_text or "").strip()
    results = cosine_search(query_vec, candidates, top_k=max(1, int(top_k)))
    rows: list[dict[str, Any]] = []
    for r in results:
        sim = float(r.get("score") or 0.0)
        rows.append(
            {
                "unit_key": r.get("unit_key"),
                "unit_type": r.get("unit_type"),
                "content": r.get("content"),
                "similarity": round(sim, 6),
                "anomaly_low_score": sim < float(low_score_threshold),
                "metadata": r.get("metadata"),
            }
        )
    return {
        "query": q,
        "top_k": int(top_k),
        "low_score_threshold": float(low_score_threshold),
        "hits": rows,
        "hit_count": len(rows),
    }
