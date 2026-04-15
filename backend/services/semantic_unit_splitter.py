"""
将长句拆成可独立检索的语义最小单元（单一动作 / 规则 / 约束）。
与 requirement_network.split_into_atomic_rules 配合：先按行与标点拆句，再按本模块细化。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_SPACE_RE = re.compile(r"\s+")
_CLAUSE_SPLIT_RE = re.compile(r"[；;]")
_CONNECTOR_SPLIT_RE = re.compile(r"(?:同时|并且|以及|而且|此外|另外|随后|接着|然后)")
_MIN_LEN = 5
_SOFT_MAX = 80  # 单条建议上限，超出再按逗号切


def _clean_line(s: str) -> str:
    return _SPACE_RE.sub(" ", (s or "").strip()).strip()


def _looks_like_kv_blob(raw: str) -> bool:
    """
    识别 requirement_network._compose_content() 生成的 KV 串（system/menu/page/file/source/...）。
    这类文本的分号是字段分隔符，不应作为“断句”来拆分。
    """
    s = str(raw or "").strip()
    if not s or ";" not in s:
        return False
    lower = s.lower()
    # base context keys
    if "system=" not in lower or "menu=" not in lower or "file=" not in lower:
        return False
    # at least one semantic payload key
    payload_keys = ("source=", "summary=", "rule=", "requirement=", "content=", "detail=", "action=")
    return any(k in lower for k in payload_keys)


def _semantic_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def split_to_semantic_units(text: str) -> list[dict[str, Any]]:
    """
    输出 [{ "content": str, "semantic_id": str, "parent_unit_key": "" }].
    结构化行（页面=…）保持为单条，避免切碎。
    """
    raw = _clean_line(text)
    if not raw:
        return []
    if len(raw) < _MIN_LEN:
        return []

    stripped = raw.lstrip()
    if stripped.startswith("页面=") or stripped.startswith("页面＝"):
        return [{"content": raw, "semantic_id": _semantic_hash(raw), "parent_unit_key": ""}]
    if _looks_like_kv_blob(raw):
        return [{"content": raw, "semantic_id": _semantic_hash(raw), "parent_unit_key": ""}]

    # 先按分号拆
    segments: list[str] = []
    for part in _CLAUSE_SPLIT_RE.split(raw):
        p = _clean_line(part)
        if len(p) >= _MIN_LEN:
            segments.append(p)

    if not segments:
        segments = [raw]

    out: list[dict[str, Any]] = []
    for seg in segments:
        sub = _split_segment_by_connectors(seg)
        for piece in sub:
            p = _clean_line(piece)
            if len(p) < _MIN_LEN:
                continue
            if len(p) > _SOFT_MAX:
                out.extend(_split_long_by_commas(p))
            else:
                out.append({"content": p, "semantic_id": _semantic_hash(p), "parent_unit_key": ""})
    return _dedupe_units(out)


def _split_segment_by_connectors(seg: str) -> list[str]:
    """按「同时/并且/…」拆成多段（不含过短碎片）。"""
    parts = _CONNECTOR_SPLIT_RE.split(seg)
    cleaned = [_clean_line(p) for p in parts if _clean_line(p) and len(_clean_line(p)) >= _MIN_LEN]
    return cleaned if len(cleaned) > 1 else [seg]


def _split_long_by_commas(text: str) -> list[dict[str, Any]]:
    pieces = re.split(r"[，,、]", text)
    out: list[dict[str, Any]] = []
    for p in pieces:
        p = _clean_line(p)
        if len(p) < _MIN_LEN:
            continue
        out.append({"content": p, "semantic_id": _semantic_hash(p), "parent_unit_key": ""})
    if not out:
        return [{"content": text[:500], "semantic_id": _semantic_hash(text), "parent_unit_key": ""}]
    return out


def _dedupe_units(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        c = str(it.get("content") or "").strip()
        if not c:
            continue
        k = c.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append({**it, "content": c})
    return out


def expand_semantic_units(parts: list[str]) -> list[str]:
    """对已有分句列表再按语义拆分并去重。"""
    out: list[str] = []
    for part in parts:
        units = split_to_semantic_units(part)
        if not units:
            p = _clean_line(part)
            if len(p) >= _MIN_LEN:
                out.append(p)
            continue
        for u in units:
            c = str(u.get("content") or "").strip()
            if len(c) >= _MIN_LEN:
                out.append(c)
    # 去重保序
    seen: set[str] = set()
    deduped: list[str] = []
    for c in out:
        k = c.casefold()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    return deduped
