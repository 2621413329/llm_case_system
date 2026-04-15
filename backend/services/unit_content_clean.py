"""
Semantic cleanup for requirement network units before vector indexing.

Drops noise / ID-like / placeholder-heavy content so low-information units are
not embedded into the searchable network.
"""

from __future__ import annotations

import re
from typing import Any

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^;]+)")
_MEANINGFUL_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")

_MIN_CONTENT_LEN = 2
_PLACEHOLDER_VALUES = {"unknown", "none", "null", "n/a", "na", "empty"}
_LOW_INFO_KEYS = {"file", "page", "source", "label", "part_index"}
_CONTEXT_KEYS = {"system", "menu", "page", "file", "source", "label", "part_index"}


def _compact_menu_to_leaf(menu_value: str) -> str:
    """
    将 menu 路径压缩成页面签名，保留末两级以提供“页面层面”区分度。
    例如：A > B > C > D  ->  C/D
    """
    raw = str(menu_value or "").strip()
    if not raw:
        return ""
    # 兼容 " > "、">"、"/" 等分隔符
    parts = [p.strip() for p in re.split(r"\s*>\s*|/|\\\\|\|", raw) if p.strip()]
    if not parts:
        return ""
    tail = parts[-2:] if len(parts) >= 2 else parts[-1:]
    return "/".join(tail)


def _compact_file_to_leaf(file_value: str) -> str:
    raw = str(file_value or "").strip()
    if not raw:
        return ""
    # 去扩展名
    raw = re.sub(r"\.(png|jpe?g|gif|webp|bmp|svg)$", "", raw, flags=re.I).strip()
    if not raw:
        return ""
    # 有些文件名会用 "_" 拼路径：取末两段
    parts = [p.strip() for p in re.split(r"_+|/|\\\\", raw) if p.strip()]
    if not parts:
        return ""
    tail = parts[-2:] if len(parts) >= 2 else parts[-1:]
    return "/".join(tail)
_STRONG_KEYS = {
    "system",
    "menu",
    "name",
    "rule",
    "element",
    "attribute",
    "validation",
    "action",
    "target",
    "impact",
    "detail",
    "summary",
    "excerpt",
    "data_object",
    "trigger",
    "core_actions",
    "key_fields",
}


def is_noise(content: str) -> bool:
    s = (content or "").strip()
    if not s:
        return True
    if len(s) >= 3 and len(set(s)) == 1:
        return True
    if not _MEANINGFUL_RE.search(s):
        return True
    return False


def is_id_like(content: str) -> bool:
    s = (content or "").strip()
    if not s:
        return True
    if s.isdigit():
        return True
    if _UUID_RE.fullmatch(s):
        return True
    if re.fullmatch(r"[0-9a-fA-F]{8,}", s):
        return True
    if re.fullmatch(r"[\d\s\-+]+", s):
        return True
    return False


def _extract_kv_pairs(content: str) -> list[tuple[str, str]]:
    return [(key.strip().lower(), value.strip()) for key, value in _KV_RE.findall(content or "")]


def _strip_context_kv(content: str) -> str:
    """
    将 requirement_network._compose_content() 产出的上下文 KV（system/menu/page/file/source/part_index 等）
    从用于 embedding 的文本中剥离，避免“模板化前缀”主导向量相似度，导致跨页面都接近 1.0。

    说明：
    - 这些上下文信息仍可通过 source_context/metadata 用于溯源与 UI 展示；
    - embedding 侧更需要区分性的“业务语义片段”（rule/action/target/impact 等）。
    """
    s = (content or "").strip()
    if not s or ";" not in s or "=" not in s:
        return s
    parts = [p.strip() for p in s.split(";") if p.strip()]
    kept: list[str] = []
    menu_raw = ""
    file_raw = ""
    for p in parts:
        if "=" not in p:
            kept.append(p)
            continue
        k, v = p.split("=", 1)
        kk = k.strip().lower()
        vv = v.strip()
        if kk == "menu":
            menu_raw = vv
            continue
        if kk == "file":
            file_raw = vv
            continue
        if kk in _CONTEXT_KEYS:
            continue
        kept.append(f"{k.strip()}={vv}" if kk else p)

    # 关键：保留轻量 page_leaf，避免“纯动作/规则语义”丢失页面层面区分
    leaf = _compact_menu_to_leaf(menu_raw) or _compact_file_to_leaf(file_raw)
    if leaf:
        kept.insert(0, f"page_leaf={leaf}")

    out = "; ".join([x for x in kept if x]).strip()
    return out


def is_low_information_structured_content(content: str) -> bool:
    pairs = _extract_kv_pairs(content)
    if not pairs:
        return False

    meaningful_values = 0
    strong_values = 0
    for key, value in pairs:
        normalized = value.strip().lower()
        if normalized in _PLACEHOLDER_VALUES:
            continue
        if len(value.strip()) < 2:
            continue
        if not _MEANINGFUL_RE.search(value):
            continue
        if key not in _LOW_INFO_KEYS:
            meaningful_values += 1
        if key in _STRONG_KEYS:
            strong_values += 1

    return strong_values == 0 and meaningful_values <= 1


def normalize_unit_content(unit: dict[str, Any]) -> str | None:
    content = str(unit.get("content") or "").strip()
    if not content:
        return None
    # 关键：先剥离上下文 KV，避免结构化模板导致向量高度相似
    content = _strip_context_kv(content).strip()
    if not content:
        return None
    if len(content) < _MIN_CONTENT_LEN:
        return None
    if is_noise(content):
        return None
    if is_id_like(content):
        return None
    if is_low_information_structured_content(content):
        return None
    return content


def filter_units_and_edges(
    units: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Remove units that fail semantic cleanup; drop edges that reference removed keys."""
    new_units: list[dict[str, Any]] = []
    for u in units:
        if not isinstance(u, dict):
            continue
        cleaned = normalize_unit_content(u)
        if cleaned is None:
            continue
        u2 = dict(u)
        u2["content"] = cleaned
        new_units.append(u2)

    kept = {
        str(x.get("unit_key") or "").strip()
        for x in new_units
        if str(x.get("unit_key") or "").strip()
    }
    new_edges: list[dict[str, Any]] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        fk = str(e.get("from_unit_key") or "").strip()
        tk = str(e.get("to_unit_key") or "").strip()
        if fk in kept and tk in kept:
            new_edges.append(e)
    return new_units, new_edges
