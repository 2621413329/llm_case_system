from __future__ import annotations

import hashlib
import re
from typing import Any

try:
    from backend.services.semantic_unit_splitter import expand_semantic_units as _expand_semantic_units
except Exception:  # pragma: no cover
    from services.semantic_unit_splitter import expand_semantic_units as _expand_semantic_units  # type: ignore

# 单条 unit 写入与 embedding 输入的上限（避免粗暴 1200 截断；极端长度再截断）
MAX_UNIT_CONTENT_CHARS = 8000


def _clamp_unit_content(text: Any, max_len: int = MAX_UNIT_CONTENT_CHARS) -> str:
    s = str(text or "").strip()
    if len(s) <= max_len:
        return s
    return s[:max_len]


def _sha1(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()


def _unit_key(prefix: str, raw: str) -> str:
    raw = str(raw or "").strip() or "empty"
    return f"{prefix}:{_sha1(raw)[:10]}"


def _append_edge(
    edges: list[dict[str, Any]],
    history_id: int,
    from_key: str,
    to_key: str,
    relation_type: str,
) -> None:
    fk = str(from_key or "").strip()
    tk = str(to_key or "").strip()
    if not fk or not tk or fk == tk:
        return
    edges.append(
        {
            "from_unit_key": fk,
            "to_unit_key": tk,
            "relation_type": relation_type,
            "metadata": {"history_id": history_id},
        }
    )


_SPLIT_RE = re.compile(r"[；;。\n]+")
_SPACE_RE = re.compile(r"\s+")
# 结构化文档小节标题（单独一行，不参与拆句）
_SECTION_HEADER_ONLY = re.compile(
    r"^(上游输入|核心处理逻辑|下游输出影响|下游输出|业务范围|当前功能概述)[:：]\s*$"
)

_REQUIREMENT_HINTS = (
    "必须",
    "应当",
    "需要",
    "需",
    "校验",
    "限制",
    "必填",
    "不能为空",
    "不能",
    "仅支持",
    "只允许",
    "required",
    "validate",
    "validation",
)

_INTERACTION_HINTS = (
    "点击",
    "选择",
    "打开",
    "关闭",
    "弹窗",
    "跳转",
    "提交",
    "保存",
    "查询",
    "刷新",
    "click",
    "open",
    "submit",
    "save",
    "search",
)

_DATA_HINTS = (
    "数据",
    "字段",
    "返回",
    "结果",
    "列表",
    "明细",
    "来源",
    "依赖",
    "关联",
    "database",
    "query",
    "result",
    "field",
)


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _SPACE_RE.sub(" ", text)


def _clean_text_keep_lines(value: Any) -> str:
    """折叠行内空白，保留换行；建库联动/业务检索句需按行拆分为原子规则。"""
    text = str(value or "").strip()
    if not text:
        return ""
    lines: list[str] = []
    for ln in text.splitlines():
        t = _SPACE_RE.sub(" ", ln.strip())
        if t:
            lines.append(t)
    return "\n".join(lines)


def _stringify_list(values: Any, limit: int = 8) -> str:
    if not isinstance(values, list):
        return ""
    out: list[str] = []
    for item in values:
        text = _clean_text(item)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return ", ".join(out)


def _normalize_word(value: str) -> str:
    text = _clean_text(value).lower()
    aliases = {
        "btn": "button",
        "按钮": "button",
        "button": "button",
        "input": "input",
        "输入框": "input",
        "text": "text",
        "文本": "text",
        "select": "select",
        "下拉": "select",
        "dropdown": "select",
        "table": "table",
        "列表": "table",
        "grid": "table",
        "dialog": "modal",
        "modal": "modal",
        "弹窗": "modal",
        "form": "form",
        "表单": "form",
        "page": "page",
        "页面": "page",
        "submit": "submit",
        "保存": "save",
        "save": "save",
        "search": "search",
        "查询": "search",
        "新增": "create",
        "create": "create",
        "edit": "edit",
        "编辑": "edit",
        "delete": "delete",
        "删除": "delete",
    }
    return aliases.get(text, text or "unknown")


def _bool_text(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _menu_path(record: dict[str, Any]) -> str:
    items = record.get("menu_structure")
    if not isinstance(items, list):
        return ""
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = _clean_text(item.get("name"))
            if name:
                names.append(name)
    return " > ".join(names)


def _system_name(record: dict[str, Any]) -> str:
    return _clean_text(record.get("system_name")) or "unknown"


def _page_type(record: dict[str, Any]) -> str:
    manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
    page_type = _clean_text(manual.get("page_type"))
    if page_type:
        return _normalize_word(page_type)
    data = record.get("analysis_data") if isinstance(record.get("analysis_data"), dict) else {}
    current_function = data.get("current_function") if isinstance(data.get("current_function"), dict) else {}
    return _normalize_word(current_function.get("page_type") or "page")


def _base_context(record: dict[str, Any]) -> list[str]:
    return [
        f"system={_system_name(record)}",
        f"menu={_menu_path(record) or 'unknown'}",
        f"page={_page_type(record)}",
        f"file={_clean_text(record.get('file_name')) or 'unknown'}",
    ]


def _compose_content(record: dict[str, Any], **fields: Any) -> str:
    parts = _base_context(record)
    for key, value in fields.items():
        text = _clean_text(value)
        if text:
            parts.append(f"{key}={text}")
    return "; ".join(parts)


def split_into_atomic_rules(content: str) -> list[str]:
    """
    拆成可入库的原子规则。
    - 若行为「页面=…；操作=…」这类结构化业务句，整行保留一条，避免按分号切碎。
    - 否则按句读标点拆分（兼容旧文本）。
    """
    raw = str(content or "").strip()
    if not raw:
        return []

    def _line_clean(s: str) -> str:
        """仅折叠行内空白，保留换行边界（全篇 _clean_text 会把 \\n 压成空格）。"""
        return _SPACE_RE.sub(" ", (s or "").strip()).strip()

    def _dedupe(parts: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for part in parts:
            p = _line_clean(part)
            if len(p) < 6:
                continue
            key = p.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    line_parts: list[str] = []
    for raw_line in raw.splitlines():
        line = _line_clean(raw_line)
        if len(line) < 6:
            continue
        # 章节标题，不参与拆句
        if line.startswith("【") and "】" in line and "=" not in line:
            continue
        if _SECTION_HEADER_ONLY.match(line):
            continue
        stripped = line.lstrip()
        # 去掉列表符号后仍按模板键识别，便于「- 页面=…」入库为整句
        strip_bullet = stripped[1:].lstrip() if stripped.startswith(("-", "•", "·", "*")) else stripped
        _tpl_prefixes = (
            "页面=",
            "页面＝",
            "菜单=",
            "菜单＝",
            "功能=",
            "功能＝",
            "功能场景=",
            "功能场景＝",
            "权限=",
            "权限＝",
            "权限与数据=",
            "权限与数据＝",
            "数据=",
            "数据＝",
            "规则=",
            "规则＝",
            "场景=",
            "场景＝",
            "模块=",
            "模块＝",
        )
        if strip_bullet.startswith(_tpl_prefixes):
            line_parts.append(line)
            continue
        if stripped.startswith(_tpl_prefixes):
            line_parts.append(line)
            continue
        # 「页面=…；操作=…；条件=…；结果=…」业务检索句（整行保留，避免按分号切碎）
        if (
            "页面=" in strip_bullet
            and "操作=" in strip_bullet
            and "条件=" in strip_bullet
            and "结果=" in strip_bullet
            and "；" in strip_bullet
        ):
            line_parts.append(line)
            continue
        # 样式表回写的「元素=…；属性=…」整行保留
        if strip_bullet.startswith("元素=") or strip_bullet.startswith("元素＝"):
            line_parts.append(line)
            continue
        # 「主功能/列表或详情」类路径，整行作为一条可检索规则（避免被分号拆碎）
        if (
            "/" in strip_bullet
            and "://" not in strip_bullet
            and strip_bullet.count("/") == 1
            and 8 <= len(strip_bullet) <= 200
            and not strip_bullet.startswith("http")
        ):
            line_parts.append(line)
            continue
        # 结构化 KV 串（compose_content 输出）：分号是字段分隔符，不做断句拆分
        lower = stripped.lower()
        if (
            ";" in stripped
            and "system=" in lower
            and "menu=" in lower
            and "file=" in lower
            and any(k in lower for k in ("source=", "summary=", "rule=", "requirement=", "content=", "detail=", "action="))
        ):
            line_parts.append(line)
            continue
        subs = [_line_clean(p) for p in _SPLIT_RE.split(line)]
        subs = [p for p in subs if len(p) >= 6]
        line_parts.extend(subs if subs else [line])

    if line_parts:
        merged = _dedupe(line_parts)
        try:
            expanded = _expand_semantic_units(merged)
        except Exception:
            expanded = merged
        return _dedupe(expanded) if expanded else merged
    whole = _line_clean(raw)
    if len(whole) >= 6:
        try:
            ex = _expand_semantic_units([whole])
            return _dedupe(ex) if ex else _dedupe([whole])
        except Exception:
            return _dedupe([whole])
    return []


def _rule_label(rule: str) -> str:
    text = _clean_text(rule).lower()
    if not text:
        return "general"
    if any(token in text for token in _REQUIREMENT_HINTS):
        return "requirement"
    if any(token in text for token in _INTERACTION_HINTS):
        return "interaction"
    if any(token in text for token in _DATA_HINTS):
        return "data"
    return "general"


def _iter_units_by_type(units: list[dict[str, Any]], unit_type: str) -> list[dict[str, Any]]:
    return [unit for unit in units if unit.get("unit_type") == unit_type]


def _content_has_name(text: str, name: str) -> bool:
    base = _clean_text(text)
    key = _clean_text(name)
    if not base or not key:
        return False
    return key in base


def build_atomic_units_and_edges(record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    history_id = int(record.get("id") or 0)
    manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
    elements = manual.get("page_elements") if isinstance(manual.get("page_elements"), list) else []

    style_row_units: list[tuple[str, str]] = []
    data_element_units: list[tuple[str, str]] = []
    content_unit_keys: list[str] = []
    interaction_unit_keys: list[str] = []
    vector_analysis_unit_keys: list[str] = []

    for element in elements:
        if not isinstance(element, dict):
            continue
        name = _clean_text(element.get("name"))
        if not name:
            continue
        element_type = _normalize_word(str(element.get("element_type") or "other"))
        ui_pattern = _clean_text(element.get("ui_pattern"))
        action = _normalize_word(str(element.get("action") or ""))
        validation = _clean_text(element.get("validation"))
        options = _stringify_list(element.get("options"), limit=6)
        raw = f"{element_type}|{name}|{action}|{validation}|{ui_pattern}|{options}"
        unit_key = _unit_key("element", raw)
        content = _compose_content(
            record,
            source="element",
            element_type=element_type,
            name=name,
            action=action or "none",
            ui_pattern=ui_pattern or "none",
            required=_bool_text(element.get("required")),
            queryable=_bool_text(element.get("queryable")),
            opens_modal=_bool_text(element.get("opens_modal")),
            requires_confirm=_bool_text(element.get("requires_confirm")),
            validation=validation or "none",
            options=options or "none",
        )
        metadata = {
            "history_id": history_id,
            "element_type": element_type,
            "name": name,
            "ui_pattern": ui_pattern,
            "action": action,
            "required": bool(element.get("required")),
            "queryable": bool(element.get("queryable")),
            "opens_modal": bool(element.get("opens_modal")),
            "requires_confirm": bool(element.get("requires_confirm")),
            "validation": validation,
            "min_len": element.get("min_len", ""),
            "max_len": element.get("max_len", ""),
            "options": element.get("options") if isinstance(element.get("options"), list) else [],
            "source": element.get("source") or "",
            "source_text": element.get("source_text") or "",
        }
        units.append(
            {
                "unit_key": unit_key,
                "unit_type": "element",
                "content": _clamp_unit_content(content),
                "metadata": metadata,
            }
        )

    rows = record.get("analysis_style_table")
    if isinstance(rows, list) and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            element_name = _clean_text(row.get("element"))
            attribute = _clean_text(row.get("attribute"))
            if not attribute and isinstance(row.get("attributes"), list) and row["attributes"]:
                attribute = _clean_text(row["attributes"][0])
            requirement = _clean_text(row.get("requirement"))
            if not any([element_name, attribute, requirement]):
                continue
            raw = f"{element_name}|{attribute}|{requirement}"
            unit_key = _unit_key("style", raw)
            content = _compose_content(
                record,
                source="style_rule",
                element=element_name or "unknown",
                attribute=attribute or "default",
                requirement=requirement or "none",
            )
            units.append(
                {
                    "unit_key": unit_key,
                    "unit_type": "style_row",
                    "content": _clamp_unit_content(content),
                    "metadata": {
                        "history_id": history_id,
                        "attribute": attribute,
                        "element": element_name,
                        "requirement_extra": requirement,
                    },
                }
            )
            if element_name:
                style_row_units.append((unit_key, element_name))
    else:
        style_text = _clean_text(record.get("analysis_style"))
        for index, part in enumerate(split_into_atomic_rules(style_text)[:60]):
            unit_key = _unit_key("style_text", part)
            units.append(
                {
                    "unit_key": unit_key,
                    "unit_type": "style_row",
                    "content": _clamp_unit_content(
                        _compose_content(
                            record,
                            source="style_summary",
                            part_index=str(index),
                            rule=part,
                        )
                    ),
                    "metadata": {"history_id": history_id},
                }
            )

    analysis_content = _clean_text(record.get("analysis_content"))
    for index, rule in enumerate(split_into_atomic_rules(analysis_content)[:120]):
        label = _rule_label(rule)
        raw = f"{label}|{rule}"
        unit_key = _unit_key("content_rule", raw)
        content_unit_keys.append(unit_key)
        units.append(
            {
                "unit_key": unit_key,
                "unit_type": "requirement_rule",
                "content": _clamp_unit_content(
                    _compose_content(
                        record,
                        source="content_rule",
                        label=label,
                        part_index=str(index),
                        rule=rule,
                    )
                ),
                "metadata": {"history_id": history_id, "rule_index": index, "label": label},
            }
        )

    analysis_data = record.get("analysis_data")
    if isinstance(analysis_data, str):
        for index, part in enumerate(split_into_atomic_rules(analysis_data)[:80]):
            unit_key = _unit_key("data_text", part)
            units.append(
                {
                    "unit_key": unit_key,
                    "unit_type": "data_analysis_text",
                    "content": _clamp_unit_content(
                        _compose_content(
                            record,
                            source="data_summary",
                            part_index=str(index),
                            rule=part,
                        )
                    ),
                    "metadata": {"history_id": history_id},
                }
            )

    if isinstance(analysis_data, dict):
        current_function = analysis_data.get("current_function")
        if isinstance(current_function, dict):
            menu_path = _clean_text(current_function.get("menu_path"))
            page_type = _normalize_word(str(current_function.get("page_type") or ""))
            core_actions = _stringify_list(current_function.get("core_actions"), limit=10)
            key_fields = _stringify_list(current_function.get("key_fields"), limit=12)
            result_views = _stringify_list(current_function.get("result_views"), limit=8)
            summary_text = _compose_content(
                record,
                source="data_current_function",
                function_menu=menu_path or "unknown",
                function_page=page_type or "unknown",
                core_actions=core_actions or "none",
                key_fields=key_fields or "none",
                result_views=result_views or "none",
            )
            unit_key = _unit_key("data_current_function", summary_text)
            units.append(
                {
                    "unit_key": unit_key,
                    "unit_type": "data_current_function",
                    "content": _clamp_unit_content(summary_text),
                    "metadata": {
                        "history_id": history_id,
                        "menu_path": menu_path,
                        "page_type": page_type,
                    },
                }
            )

        upstream = analysis_data.get("upstream_dependencies")
        if isinstance(upstream, list):
            for index, item in enumerate(upstream[:80]):
                if not isinstance(item, dict):
                    continue
                source = _clean_text(item.get("source"))
                data_object = _clean_text(item.get("data_object"))
                trigger = _clean_text(item.get("trigger"))
                rule = _clean_text(item.get("rule"))
                if not any([source, data_object, trigger, rule]):
                    continue
                raw = f"{source}|{data_object}|{trigger}|{rule}"
                unit_key = _unit_key("data_upstream", raw)
                units.append(
                    {
                        "unit_key": unit_key,
                        "unit_type": "data_upstream",
                        "content": _clamp_unit_content(
                            _compose_content(
                                record,
                                source="data_upstream",
                                part_index=str(index),
                                upstream_source=source or "unknown",
                                data_object=data_object or "unknown",
                                trigger=trigger or "unknown",
                                rule=rule or "none",
                            )
                        ),
                        "metadata": {
                            "history_id": history_id,
                            "source": source,
                            "data_object": data_object,
                            "trigger": trigger,
                        },
                    }
                )

        downstream = analysis_data.get("downstream_impacts")
        if isinstance(downstream, list):
            for index, item in enumerate(downstream[:80]):
                if not isinstance(item, dict):
                    continue
                target = _clean_text(item.get("target"))
                action = _clean_text(item.get("action"))
                impact = _clean_text(item.get("impact"))
                if not any([target, action, impact]):
                    continue
                raw = f"{target}|{action}|{impact}"
                unit_key = _unit_key("data_downstream", raw)
                units.append(
                    {
                        "unit_key": unit_key,
                        "unit_type": "data_downstream",
                        "content": _clamp_unit_content(
                            _compose_content(
                                record,
                                source="data_downstream",
                                part_index=str(index),
                                target=target or "unknown",
                                action=action or "unknown",
                                impact=impact or "none",
                            )
                        ),
                        "metadata": {
                            "history_id": history_id,
                            "target": target,
                            "action": action,
                        },
                    }
                )

        relations = analysis_data.get("data_logic_relations")
        if isinstance(relations, list):
            for index, item in enumerate(relations[:120]):
                if not isinstance(item, dict):
                    continue
                src = _clean_text(item.get("from"))
                dst = _clean_text(item.get("to"))
                relation = _clean_text(item.get("relation"))
                detail = _clean_text(item.get("detail"))
                if not any([src, dst, relation, detail]):
                    continue
                raw = f"{src}|{dst}|{relation}|{detail}"
                unit_key = _unit_key("data_relation", raw)
                units.append(
                    {
                        "unit_key": unit_key,
                        "unit_type": "data_logic_relation",
                        "content": _clamp_unit_content(
                            _compose_content(
                                record,
                                source="data_relation",
                                part_index=str(index),
                                from_field=src or "unknown",
                                to_field=dst or "unknown",
                                relation=relation or "unknown",
                                detail=detail or "none",
                            )
                        ),
                        "metadata": {
                            "history_id": history_id,
                            "from": src,
                            "to": dst,
                            "relation": relation,
                        },
                    }
                )

        excerpt = _clean_text(analysis_data.get("ocr_raw_excerpt"))
        for index, part in enumerate(split_into_atomic_rules(excerpt)[:20]):
            unit_key = _unit_key("ocr_excerpt", part)
            units.append(
                {
                    "unit_key": unit_key,
                    "unit_type": "data_ocr_excerpt",
                    "content": _clamp_unit_content(
                        _compose_content(
                            record,
                            source="ocr_excerpt",
                            part_index=str(index),
                            excerpt=part,
                        )
                    ),
                    "metadata": {"history_id": history_id},
                }
            )

        elements_overview = analysis_data.get("elements_overview")
        if isinstance(elements_overview, list):
            for item in elements_overview:
                if not isinstance(item, dict):
                    continue
                name = _clean_text(item.get("name"))
                if not name:
                    continue
                element_type = _normalize_word(str(item.get("element_type") or "other"))
                validation = _clean_text(item.get("validation"))
                raw = f"{element_type}|{name}|{validation}"
                unit_key = _unit_key("data_element", raw)
                units.append(
                    {
                        "unit_key": unit_key,
                        "unit_type": "data_element",
                        "content": _clamp_unit_content(
                            _compose_content(
                                record,
                                source="data_element",
                                element_type=element_type,
                                name=name,
                                validation=validation or "none",
                            )
                        ),
                        "metadata": {
                            "history_id": history_id,
                            "element_type": element_type,
                            "name": name,
                        },
                    }
                )
                data_element_units.append((unit_key, name))

    vector_analysis_text = _clean_text_keep_lines(record.get("_vector_analysis_text"))
    if vector_analysis_text:
        summary_key = _unit_key("vector_summary", _clamp_unit_content(vector_analysis_text, 300))
        units.append(
            {
                "unit_key": summary_key,
                "unit_type": "vector_analysis",
                "content": _clamp_unit_content(
                    _compose_content(
                        record,
                        source="vector_summary",
                        summary=_clamp_unit_content(vector_analysis_text, 2000),
                    )
                ),
                "metadata": {"history_id": history_id},
            }
        )
        vector_analysis_unit_keys.append(summary_key)
        for index, rule in enumerate(split_into_atomic_rules(vector_analysis_text)[:120]):
            label = _rule_label(rule)
            raw = f"{label}|{rule}"
            unit_key = _unit_key("vector_rule", raw)
            vector_analysis_unit_keys.append(unit_key)
            units.append(
                {
                    "unit_key": unit_key,
                    "unit_type": "vector_analysis_rule",
                    "content": _clamp_unit_content(
                        _compose_content(
                            record,
                            source="vector_rule",
                            label=label,
                            part_index=str(index),
                            rule=rule,
                        )
                    ),
                    "metadata": {"history_id": history_id, "rule_index": index, "label": label},
                }
            )

    interaction_text = _clean_text(record.get("analysis_interaction"))
    for index, rule in enumerate(split_into_atomic_rules(interaction_text)[:160]):
        label = _rule_label(rule)
        raw = f"{label}|{rule}"
        unit_key = _unit_key("interaction_rule", raw)
        interaction_unit_keys.append(unit_key)
        units.append(
            {
                "unit_key": unit_key,
                "unit_type": "interaction_rule",
                "content": _clamp_unit_content(
                    _compose_content(
                        record,
                        source="interaction_rule",
                        label=label,
                        part_index=str(index),
                        rule=rule,
                    )
                ),
                "metadata": {"history_id": history_id, "rule_index": index, "label": label},
            }
        )

    interaction_blob = " ".join(unit["content"] for unit in _iter_units_by_type(units, "interaction_rule"))
    content_blob = " ".join(unit["content"] for unit in _iter_units_by_type(units, "requirement_rule"))

    for unit in _iter_units_by_type(units, "element"):
        metadata = unit.get("metadata") if isinstance(unit.get("metadata"), dict) else {}
        name = _clean_text(metadata.get("name"))
        unit_key = _clean_text(unit.get("unit_key"))
        if not name or not unit_key:
            continue
        if _content_has_name(interaction_blob, name):
            for interaction_key in interaction_unit_keys:
                _append_edge(edges, history_id, unit_key, interaction_key, "element_interaction_link")
        if _content_has_name(content_blob, name):
            for content_key in content_unit_keys:
                _append_edge(edges, history_id, unit_key, content_key, "element_requirement_link")

    for data_key, data_name in data_element_units:
        for style_key, style_name in style_row_units:
            if _content_has_name(style_name, data_name) or _content_has_name(data_name, style_name):
                _append_edge(edges, history_id, data_key, style_key, "data_style_link")
        if _content_has_name(content_blob, data_name):
            for content_key in content_unit_keys:
                _append_edge(edges, history_id, data_key, content_key, "data_requirement_link")
        if _content_has_name(interaction_blob, data_name):
            for interaction_key in interaction_unit_keys:
                _append_edge(edges, history_id, data_key, interaction_key, "data_interaction_link")

    style_blob = " ".join(unit["content"] for unit in _iter_units_by_type(units, "style_row"))
    if style_blob and interaction_unit_keys:
        for style_key, style_name in style_row_units:
            if _content_has_name(interaction_blob, style_name):
                for interaction_key in interaction_unit_keys:
                    _append_edge(edges, history_id, style_key, interaction_key, "style_interaction_link")

    for vector_key in vector_analysis_unit_keys:
        for content_key in content_unit_keys[:60]:
            _append_edge(edges, history_id, vector_key, content_key, "vector_content_link")
        for interaction_key in interaction_unit_keys[:60]:
            _append_edge(edges, history_id, vector_key, interaction_key, "vector_interaction_link")

    if style_blob and content_blob:
        for style_key, _ in style_row_units[:40]:
            for content_key in content_unit_keys[:40]:
                _append_edge(edges, history_id, style_key, content_key, "style_requirement_link")

    return units, edges
