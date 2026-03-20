from __future__ import annotations

import hashlib
from typing import Any


def _sha1(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()


def _unit_key(prefix: str, raw: str) -> str:
    """
    unit_key 需要稳定且尽量短：避免把超长 title 直接塞进去。
    """
    raw = str(raw or "").strip()
    if not raw:
        raw = "empty"
    h = _sha1(raw)[:10]
    return f"{prefix}:{h}"


def build_atomic_units_and_edges(record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    MVP 版本：基于现有结构化产物抽取“原子需求单元”，并用简单文本关联建立关系边。
    后续可替换为 bbox/布局解析的更精确抽取逻辑。
    """
    units: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
    elements = manual.get("page_elements") if isinstance(manual.get("page_elements"), list) else []
    history_id = record.get("id")
    history_id = int(history_id) if history_id is not None else 0

    # 1) 页面元素（字段/按钮等）
    element_unit_keys: dict[str, str] = {}  # element_key -> unit_key
    for e in elements:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        if not name:
            continue
        element_type = str(e.get("element_type") or "other").strip().lower() or "other"
        ui_pattern = str(e.get("ui_pattern") or "").strip()
        action = str(e.get("action") or "").strip()
        required = bool(e.get("required"))
        queryable = bool(e.get("queryable"))
        opens_modal = bool(e.get("opens_modal"))
        requires_confirm = bool(e.get("requires_confirm"))
        validation = str(e.get("validation") or "").strip()
        min_len = e.get("min_len", "")
        max_len = e.get("max_len", "")

        # unit_key 用“类型+名称+验证摘要”来保证稳定
        element_key = f"{element_type}::{name}::{validation}::{action}".strip()
        uk = _unit_key("el", element_key)
        element_unit_keys[element_key] = uk

        content_parts: list[str] = []
        if element_type == "button":
            content_parts.append(f"按钮[{name}]")
            if action:
                content_parts.append(f"action={action}")
            if opens_modal:
                content_parts.append("opens_modal=true")
            if requires_confirm:
                content_parts.append("requires_confirm=true")
        else:
            content_parts.append(f"字段/元素[{name}]")
            content_parts.append(f"type={element_type}")
            if ui_pattern:
                content_parts.append(f"ui_pattern={ui_pattern}")
            if required:
                content_parts.append("required=true")
            if queryable:
                content_parts.append("queryable=true")
            if validation:
                content_parts.append(f"validation={validation}")
            if min_len not in [None, ""]:
                content_parts.append(f"min_len={min_len}")
            if max_len not in [None, ""]:
                content_parts.append(f"max_len={max_len}")

        content = "，".join(content_parts)
        metadata = {
            "history_id": history_id,
            "element_type": element_type,
            "name": name,
            "ui_pattern": ui_pattern,
            "action": action,
            "required": required,
            "queryable": queryable,
            "opens_modal": opens_modal,
            "requires_confirm": requires_confirm,
            "validation": validation,
            "min_len": min_len if min_len is not None else "",
            "max_len": max_len if max_len is not None else "",
            "options": e.get("options") if isinstance(e.get("options"), list) else [],
            # 给前端保留，可用于展示/调试
            "source": e.get("source") or "",
            "source_text": e.get("source_text") or "",
        }

        units.append(
            {
                "unit_key": uk,
                "unit_type": "element",
                "content": content,
                "metadata": metadata,
            }
        )

    # 2) 交互分析整体（作为补充单元）
    interaction = record.get("analysis_interaction") or ""
    interaction_unit_key = ""
    if isinstance(interaction, str) and interaction.strip():
        interaction_unit_key = _unit_key("interaction", interaction[:2000])
        units.append(
            {
                "unit_key": interaction_unit_key,
                "unit_type": "interaction",
                "content": interaction.strip(),
                "metadata": {"history_id": history_id},
            }
        )

    # 3) 建边：元素 -> 交互分析（简单字符串命中）
    if interaction_unit_key:
        element_names: list[tuple[str, str]] = []
        for u in units:
            if u.get("unit_type") != "element":
                continue
            md = u.get("metadata") if isinstance(u.get("metadata"), dict) else {}
            element_names.append((str(u.get("unit_key") or ""), str(md.get("name") or "").strip()))

        t_content = str(interaction or "")
        for ek, ename in element_names:
            if not ek or not ename:
                continue
            if ename in t_content:
                edges.append(
                    {
                        "from_unit_key": ek,
                        "to_unit_key": interaction_unit_key,
                        "relation_type": "mentions",
                        "metadata": {"history_id": history_id},
                    }
                )

    return units, edges

