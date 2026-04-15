"""Lightweight business-aware reranking for requirement network search results."""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
_ACTION_TOKENS = {"保存", "提交", "查询", "新增", "删除", "编辑", "save", "submit", "search", "delete", "edit"}

_UNIT_TYPE_BONUS = {
    "element": 0.06,
    "requirement_rule": 0.1,
    "interaction_rule": 0.08,
    "vector_analysis_rule": 0.06,
    "data_element": 0.05,
    "style_row": 0.03,
}


def _tokens(text: str) -> list[str]:
    raw = [m.group(0) for m in _TOKEN_RE.finditer(str(text or ""))]
    seen: set[str] = set()
    out: list[str] = []
    for token in raw:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def _metadata_blob(metadata: Any) -> str:
    if not isinstance(metadata, dict):
        return ""
    values: list[str] = []
    for key in ("name", "element", "menu_path", "action", "validation", "target", "data_object", "trigger"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return " ".join(values)


def rerank_results(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tokens = _tokens(query)
    if not tokens or not results:
        return results

    reranked: list[dict[str, Any]] = []
    for item in results:
        content = str(item.get("content") or "")
        metadata_blob = _metadata_blob(item.get("metadata"))
        unit_type = str(item.get("unit_type") or "")
        score = float(item.get("score") or 0.0)

        bonus = _UNIT_TYPE_BONUS.get(unit_type, 0.0)
        for token in tokens:
            token_cf = token.casefold()
            content_cf = content.casefold()
            metadata_cf = metadata_blob.casefold()
            if token_cf in content_cf:
                bonus += 0.08
            if token_cf in metadata_cf:
                bonus += 0.12
            if (
                (len(token_cf) >= 2 and any(part in token_cf for part in _ACTION_TOKENS))
                or any(token_cf in action.casefold() for action in _ACTION_TOKENS)
            ) and token_cf in content_cf:
                bonus += 0.04
            for part in _tokens(content) + _tokens(metadata_blob):
                part_cf = part.casefold()
                if len(part_cf) < 2:
                    continue
                if token_cf in part_cf or part_cf in token_cf:
                    bonus += 0.06 if part_cf in metadata_cf else 0.04

        reranked_item = dict(item)
        reranked_item["score"] = score + bonus
        reranked.append(reranked_item)

    reranked.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return reranked
