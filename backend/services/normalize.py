"""
Record / Case normalization and filename utility helpers.

Extracted from simple_server.py to reduce file size and enable unit testing.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

try:
    from backend.manual_elements import (
        normalize_page_element,
        manual_from_legacy_fields_buttons,
        legacy_buttons_fields_from_elements,
    )
except Exception:
    from manual_elements import (  # type: ignore
        normalize_page_element,
        manual_from_legacy_fields_buttons,
        legacy_buttons_fields_from_elements,
    )


def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def parse_menu_from_filename(filename: str) -> tuple[str, list[dict[str, Any]]]:
    name_without_ext = os.path.splitext(filename)[0]
    parts = [p for p in name_without_ext.split("_") if p != ""]
    system_name = "默认系统"
    menu_structure = [{"level": i + 1, "name": item} for i, item in enumerate(parts)]
    return system_name, menu_structure


def is_valid_filename(name: str) -> bool:
    if not name or name.strip() != name:
        return False
    forbidden = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    if any(ch in name for ch in forbidden):
        return False
    if ".." in name:
        return False
    return True


def extract_upload_stored_name(file_url: Any) -> str:
    """从 /uploads/<stored_name> 中提取实际存储文件名。"""
    u = str(file_url or "").strip()
    if not u:
        return ""
    if u.startswith("/uploads/"):
        return unquote(u[len("/uploads/"):]).strip()
    return ""


def build_storage_filename(original_name: str) -> str:
    """生成 uploads 实际落盘文件名（与展示文件名解耦）。"""
    ext = Path(str(original_name or "").strip()).suffix or ""
    return f"{uuid.uuid4().hex}{ext.lower()}"


def style_table_rows_have_content(rows: list[Any]) -> bool:
    """样式表是否至少有一行在「元素」「补充需求」或（非默认的）「属性」上有实质内容。"""
    for r in rows:
        if not isinstance(r, dict):
            continue
        if str(r.get("element") or "").strip() or str(r.get("requirement") or "").strip():
            return True
        attr = str(r.get("attribute") or "").strip()
        if attr and attr != "文本":
            return True
    return False


def style_table_from_saved_analysis_style(style_text: str) -> list[dict[str, Any]]:
    """从已保存的 analysis_style 文本拆行生成表格（与前端 stripStyleOcrPrefix 规则一致）。"""
    t = (style_text or "").strip()
    if not t:
        return []
    m = re.match(r"^OCR识别原文（来自[^，]+，摘要）：\s*\n?", t)
    if m:
        t = t[m.end():].strip()
    elif t.startswith("OCR识别失败："):
        t = t[len("OCR识别失败："):].strip()
        if t:
            return [{"element": t[:2048], "attribute": "文本", "requirement": ""}]
        return []
    rows: list[dict[str, Any]] = []
    for line in t.splitlines():
        s = line.strip()
        if s:
            rows.append({"element": s, "attribute": "文本", "requirement": ""})
    if not rows and t:
        rows.append({"element": t, "attribute": "文本", "requirement": ""})
    return rows


def normalize_case_priority(raw: Any) -> str:
    """用例优先级：P0（最高）~ P3（最低），默认 P2。"""
    s = str(raw or "").strip().upper()
    if s in ("P0", "P1", "P2", "P3"):
        return s
    if raw is not None:
        try:
            n = int(raw)
            if n == 0:
                return "P0"
            if n == 1:
                return "P1"
            if n == 2:
                return "P2"
            if n == 3:
                return "P3"
        except (TypeError, ValueError):
            pass
    return "P2"


def align_step_expected_to_steps(case: dict[str, Any]) -> None:
    """使 step_expected 与 steps 等长（按索引对应每步预期）。"""
    steps_list = case.get("steps")
    if not isinstance(steps_list, list):
        steps_list = []
    se = case.get("step_expected")
    if not isinstance(se, list):
        se = []
    out: list[str] = [str(x) if x is not None else "" for x in se]
    while len(out) < len(steps_list):
        out.append("")
    if len(out) > len(steps_list):
        out = out[: len(steps_list)]
    case["step_expected"] = out


def normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    if "id" not in case:
        case["id"] = 0
    if "title" not in case:
        case["title"] = ""
    if "preconditions" not in case:
        case["preconditions"] = ""
    if not isinstance(case.get("steps"), list):
        case["steps"] = []
    if "step_expected" not in case or not isinstance(case.get("step_expected"), list):
        case["step_expected"] = []
    if "expected" not in case:
        case["expected"] = ""
    if "history_id" not in case:
        case["history_id"] = None
    if "status" not in case:
        case["status"] = "draft"
    if "last_run_at" not in case:
        case["last_run_at"] = ""
    if "run_notes" not in case:
        case["run_notes"] = ""
    if "run_attachments" not in case:
        case["run_attachments"] = []
    if "run_records" not in case or not isinstance(case.get("run_records"), list):
        case["run_records"] = []
    if "created_at" not in case:
        case["created_at"] = now_iso()
    if "updated_at" not in case:
        case["updated_at"] = case.get("created_at") or now_iso()
    if "system_id" not in case:
        case["system_id"] = None
    if "executor_id" not in case:
        case["executor_id"] = None
    if "executor_name" not in case:
        case["executor_name"] = ""
    case["priority"] = normalize_case_priority(case.get("priority"))
    align_step_expected_to_steps(case)
    return case


def merge_case_executor_from_payload(case: dict[str, Any], payload: dict[str, Any]) -> None:
    """将 payload 中的 executor_id / executor_name 合并到 case（执行记录）。"""
    if "executor_name" in payload:
        v = payload["executor_name"]
        if isinstance(v, str):
            case["executor_name"] = v.strip()[:128]
    if "executor_id" in payload:
        raw = payload["executor_id"]
        if raw is None or raw == "":
            case["executor_id"] = None
        else:
            try:
                case["executor_id"] = int(raw)
            except (ValueError, TypeError):
                pass


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    file_name = record.get("file_name")
    if isinstance(file_name, str) and file_name:
        system_name, menu_structure = parse_menu_from_filename(file_name)
        record["system_name"] = system_name
        record["menu_structure"] = menu_structure
        if not (isinstance(record.get("file_url"), str) and str(record.get("file_url") or "").strip()):
            record["file_url"] = f"/uploads/{file_name}"
    if not record.get("created_at"):
        record["created_at"] = now_iso()
    if not record.get("updated_at"):
        record["updated_at"] = record.get("created_at") or now_iso()
    if "analysis" not in record:
        record["analysis"] = ""
    if "analysis_style" not in record:
        record["analysis_style"] = ""
    if "analysis_content" not in record:
        record["analysis_content"] = ""
    if "analysis_interaction" not in record:
        record["analysis_interaction"] = ""
    if "analysis_data" not in record:
        record["analysis_data"] = None
    if "analysis_generated_at" not in record:
        record["analysis_generated_at"] = ""
    if "vector_analysis_text" not in record:
        record["vector_analysis_text"] = ""
    if "vector_build_summary" not in record:
        record["vector_build_summary"] = ""
    if "vector_built_at" not in record:
        record["vector_built_at"] = ""
    if "analysis_style_table" not in record or not isinstance(record.get("analysis_style_table"), list):
        record["analysis_style_table"] = []
    _atable = record.get("analysis_style_table")
    if isinstance(_atable, list) and not style_table_rows_have_content(_atable):
        _style_txt = str(record.get("analysis_style") or "").strip()
        if _style_txt:
            _filled = style_table_from_saved_analysis_style(_style_txt)
            if _filled:
                record["analysis_style_table"] = _filled
    if "manual" not in record or not isinstance(record.get("manual"), dict):
        record["manual"] = {
            "page_type": "",
            "page_elements": [],
            "buttons": [],
            "fields": [],
            "text_requirements": "",
            "control_logic": "",
            "ocr_raw_text": "",
            "ocr_refs": {"button_candidates": [], "field_candidates": []},
        }
    else:
        m = manual_from_legacy_fields_buttons(record["manual"])
        b, f = legacy_buttons_fields_from_elements(m)
        m["buttons"] = b
        m["fields"] = f
        if not isinstance(m.get("text_requirements"), str):
            m["text_requirements"] = ""
        if not isinstance(m.get("control_logic"), str):
            m["control_logic"] = ""
        if not isinstance(m.get("ocr_raw_text"), str):
            m["ocr_raw_text"] = ""
        if not isinstance(m.get("ocr_refs"), dict):
            m["ocr_refs"] = {"button_candidates": [], "field_candidates": []}
        record["manual"] = m
    if "system_id" not in record:
        record["system_id"] = None
    return record
