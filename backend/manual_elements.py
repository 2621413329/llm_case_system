from __future__ import annotations

from typing import Any


def normalize_page_element(x: Any) -> dict[str, Any] | None:
    if not isinstance(x, dict):
        return None
    name = str(x.get("name") or "").strip()
    if not name:
        return None
    etype = str(x.get("element_type") or "").strip().lower() or "other"
    ui_pattern = str(x.get("ui_pattern") or "").strip()
    out = {
        "name": name,
        "element_type": etype,  # button | field | list_column | filter | text | status | link | card | tab | other
        "ui_pattern": ui_pattern,
        "required": bool(x.get("required")),
        "queryable": bool(x.get("queryable")),
        "validation": str(x.get("validation") or "").strip(),
        "min_len": x.get("min_len") if x.get("min_len") is not None else "",
        "max_len": x.get("max_len") if x.get("max_len") is not None else "",
        "options": x.get("options") if isinstance(x.get("options"), list) else [],
        "action": str(x.get("action") or "").strip(),
        "opens_modal": bool(x.get("opens_modal")),
        "requires_confirm": bool(x.get("requires_confirm")),
        "source": str(x.get("source") or "").strip(),
        "source_text": str(x.get("source_text") or "").strip(),
        "raw_text": str(x.get("raw_text") or "").strip(),
        "notes": str(x.get("notes") or "").strip(),
    }
    return out


def manual_from_legacy_fields_buttons(manual: dict[str, Any]) -> dict[str, Any]:
    out = dict(manual if isinstance(manual, dict) else {})
    elements: list[dict[str, Any]] = []
    existed = out.get("page_elements")
    if isinstance(existed, list):
        for it in existed:
            n = normalize_page_element(it)
            if n:
                elements.append(n)
    if not elements:
        buttons = out.get("buttons") if isinstance(out.get("buttons"), list) else []
        fields = out.get("fields") if isinstance(out.get("fields"), list) else []
        for b in buttons:
            if not isinstance(b, dict):
                continue
            n = normalize_page_element(
                {
                    "name": b.get("name"),
                    "element_type": "button",
                    "ui_pattern": "按钮",
                    "action": b.get("action"),
                    "opens_modal": b.get("opens_modal"),
                    "requires_confirm": b.get("requires_confirm"),
                    "source": b.get("source"),
                    "source_text": b.get("source_text"),
                }
            )
            if n:
                elements.append(n)
        for f in fields:
            if not isinstance(f, dict):
                continue
            n = normalize_page_element(
                {
                    "name": f.get("name"),
                    "element_type": "field",
                    "ui_pattern": "可填写内容",
                    "required": f.get("required"),
                    "queryable": f.get("queryable"),
                    "validation": f.get("validation"),
                    "min_len": f.get("min_len"),
                    "max_len": f.get("max_len"),
                    "options": f.get("options") if isinstance(f.get("options"), list) else [],
                }
            )
            if n:
                elements.append(n)
    out["page_elements"] = elements[:300]
    return out


def legacy_buttons_fields_from_elements(manual: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    m = manual_from_legacy_fields_buttons(manual)
    elements = m.get("page_elements") if isinstance(m.get("page_elements"), list) else []
    buttons: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    for e in elements:
        if not isinstance(e, dict):
            continue
        et = str(e.get("element_type") or "").lower()
        if et == "button":
            buttons.append(
                {
                    "name": str(e.get("name") or "").strip(),
                    "action": str(e.get("action") or "").strip(),
                    "opens_modal": bool(e.get("opens_modal")),
                    "requires_confirm": bool(e.get("requires_confirm")),
                    "source": str(e.get("source") or "").strip(),
                    "source_text": str(e.get("source_text") or "").strip(),
                }
            )
        if et in ["field", "filter"]:
            fields.append(
                {
                    "name": str(e.get("name") or "").strip(),
                    "type": "text",
                    "required": bool(e.get("required")),
                    "queryable": bool(e.get("queryable")),
                    "validation": str(e.get("validation") or "").strip(),
                    "min_len": e.get("min_len") if e.get("min_len") is not None else "",
                    "max_len": e.get("max_len") if e.get("max_len") is not None else "",
                    "options": e.get("options") if isinstance(e.get("options"), list) else [],
                }
            )
    if not any(str(x.get("name") or "") == "取消" for x in buttons):
        buttons.append({"name": "取消", "action": "open", "opens_modal": False, "requires_confirm": False, "source": "default", "source_text": "保底动作"})
    if not any(str(x.get("name") or "") == "保存" for x in buttons):
        buttons.append({"name": "保存", "action": "edit", "opens_modal": False, "requires_confirm": False, "source": "default", "source_text": "保底动作"})
    return buttons[:80], fields[:200]


def extract_ocr_references(ocr_text: str) -> dict[str, Any]:
    text = str(ocr_text or "")
    t = "".join(text.split())
    button_keywords = [
        "查询", "搜索", "筛选", "重置", "清空", "新增", "添加", "新建", "编辑", "修改", "删除", "保存", "提交", "确定", "取消", "关闭", "返回", "导出", "打印",
    ]
    field_keywords = [
        "姓名", "手机号", "电话", "邮箱", "用户名", "账号", "密码", "证件号", "身份证", "学号", "工号", "编号", "备注", "说明",
        "金额", "数量", "日期", "时间", "区域", "区域名称", "区域代码",
    ]
    buttons = [k for k in button_keywords if k in t]
    fields = [k for k in field_keywords if k in t]

    def _uniq(seq: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for x in seq:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    return {
        "button_candidates": _uniq(buttons)[:20],
        "field_candidates": _uniq(fields)[:30],
        "ocr_raw_text": text,
    }


def build_page_elements_from_ocr_refs(refs: dict[str, Any]) -> list[dict[str, Any]]:
    button_candidates = refs.get("button_candidates") if isinstance(refs.get("button_candidates"), list) else []
    field_candidates = refs.get("field_candidates") if isinstance(refs.get("field_candidates"), list) else []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for b in button_candidates:
        name = str(b or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        x = normalize_page_element(
            {
                "name": name,
                "element_type": "button",
                "ui_pattern": "按钮",
                "source": "ocr",
                "source_text": name,
                "raw_text": refs.get("ocr_raw_text") or "",
            }
        )
        if x:
            out.append(x)
    for f in field_candidates:
        name = str(f or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        x = normalize_page_element(
            {
                "name": name,
                "element_type": "field",
                "ui_pattern": "可填写内容",
                "source": "ocr",
                "source_text": name,
                "raw_text": refs.get("ocr_raw_text") or "",
            }
        )
        if x:
            out.append(x)
    return out[:300]
