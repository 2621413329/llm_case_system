#!/usr/bin/env python3

"""
简单的HTTP服务器（仅标准库），提供：
- GET  /                 健康检查
- POST /api/upload       文件上传（multipart/form-data: file）
- GET  /api/history      模拟历史记录
- DELETE /api/history/:id 模拟删除
- GET  /uploads/:name    访问上传文件
"""

from __future__ import annotations

import http.server
import json
import mimetypes
import os
import socketserver
import base64
import hashlib
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse, urlencode
from typing import Any

try:
    from backend.manual_elements import (
        normalize_page_element as _normalize_page_element,
        manual_from_legacy_fields_buttons as _manual_from_legacy_fields_buttons,
        legacy_buttons_fields_from_elements as _legacy_buttons_fields_from_elements,
        extract_ocr_references as _extract_ocr_references,
        build_page_elements_from_ocr_refs as _build_page_elements_from_ocr_refs,
    )
except Exception:
    from manual_elements import (  # type: ignore
        normalize_page_element as _normalize_page_element,
        manual_from_legacy_fields_buttons as _manual_from_legacy_fields_buttons,
        legacy_buttons_fields_from_elements as _legacy_buttons_fields_from_elements,
        extract_ocr_references as _extract_ocr_references,
        build_page_elements_from_ocr_refs as _build_page_elements_from_ocr_refs,
    )

try:
    from backend.services.case_generation import generate_cases_from_history as _svc_generate_cases_from_history
except Exception:
    from services.case_generation import generate_cases_from_history as _svc_generate_cases_from_history  # type: ignore

try:
    from backend.services.analysis_service import (
        menu_names as _svc_menu_names,
        breadcrumb_for_record as _svc_breadcrumb_for_record,
        contextual_hints_from_menu as _svc_contextual_hints_from_menu,
        build_analysis as _svc_build_analysis,
    )
except Exception:
    from services.analysis_service import (  # type: ignore
        menu_names as _svc_menu_names,
        breadcrumb_for_record as _svc_breadcrumb_for_record,
        contextual_hints_from_menu as _svc_contextual_hints_from_menu,
        build_analysis as _svc_build_analysis,
    )


try:
    from backend.llm_vision import try_visual_analysis_for_screenshot, try_extract_manual_from_screenshot
except Exception:
    try:
        from llm_vision import try_visual_analysis_for_screenshot, try_extract_manual_from_screenshot
    except Exception:

        def try_visual_analysis_for_screenshot(*_a: Any, **_k: Any) -> tuple[bool, str]:
            return False, "无法加载 llm_vision 模块"

        def try_extract_manual_from_screenshot(*_a: Any, **_k: Any) -> tuple[bool, dict[str, Any] | str]:
            return False, "无法加载 llm_vision 模块"


PORT = 5000
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_PATH = DATA_DIR / "history.json"
CASES_PATH = DATA_DIR / "cases.json"
CONFIG_PATH = PROJECT_ROOT / "config.local.json"


def _parse_json_body(handler: http.server.BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length > 0:
        raw = handler.rfile.read(content_length)
    else:
        # 兼容部分客户端未正确设置 Content-Length 的情况
        try:
            raw = handler.rfile.read()  # read remaining
        except Exception:
            raw = b""
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")

def _read_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _now_iso() -> str:
    # Avoid external deps; good enough for test-case generation metadata
    import datetime as _dt

    return _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _read_history() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        raw = HISTORY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _write_history(items: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(items: list[dict[str, Any]]) -> int:
    max_id = 0
    for it in items:
        try:
            max_id = max(max_id, int(it.get("id", 0)))
        except Exception:
            continue
    return max_id + 1


# MySQL 持久化：若 config.local.json 中配置了 mysql 且可连接，则创建库表并改用 MySQL
_db_mysql = None
_storage = "file"

def _mysql_configured() -> bool:
    cfg = _read_config()
    mysql = cfg.get("mysql")
    if not isinstance(mysql, dict):
        return False
    return bool(mysql.get("host")) and bool(mysql.get("user"))


def _use_mysql() -> bool:
    global _db_mysql, _storage
    if _db_mysql is not None:
        return _storage == "mysql"
    try:
        from backend import db_mysql as m
        _db_mysql = m
    except Exception:
        try:
            import db_mysql as m
            _db_mysql = m
        except Exception:
            _db_mysql = False
    mysql_cfg_present = _mysql_configured()
    if _db_mysql and getattr(_db_mysql, "is_available", lambda: False)():
        ok, msg = getattr(_db_mysql, "init_database", lambda: (False, ""))()
        if ok:
            global _read_history, _write_history, _read_cases, _write_cases
            _read_history = _db_mysql.read_history
            _write_history = _db_mysql.write_history
            _read_cases = _db_mysql.read_cases
            _write_cases = _db_mysql.write_cases
            _storage = "mysql"
        elif mysql_cfg_present:
            # MySQL 已配置但建库/建表失败时，禁止静默回退到 JSON，避免出现“双写/错存储”。
            raise RuntimeError(f"MySQL init failed: {msg}")
    elif mysql_cfg_present:
        # MySQL 已配置但不可用时，禁止静默回退到 JSON。
        raise RuntimeError("MySQL is configured but unavailable; refusing JSON fallback.")
    return _storage == "mysql"


def _next_history_id() -> int:
    if _use_mysql() and _db_mysql:
        return _db_mysql.next_history_id()
    return _next_id(_read_history())


def _next_case_id() -> int:
    if _use_mysql() and _db_mysql:
        return _db_mysql.next_case_id()
    return _next_id(_read_cases())


def _read_cases() -> list[dict[str, Any]]:
    if not CASES_PATH.exists():
        return []
    try:
        raw = CASES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _write_cases(items: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CASES_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# 启动时尝试挂载 MySQL，若配置且可连接则创建 llm_case_system 及表
_use_mysql()


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    if "id" not in case:
        case["id"] = 0
    if "title" not in case:
        case["title"] = ""
    if "preconditions" not in case:
        case["preconditions"] = ""
    if "steps" not in case:
        case["steps"] = []
    if "expected" not in case:
        case["expected"] = ""
    if "history_id" not in case:
        case["history_id"] = None
    if "status" not in case:
        case["status"] = "draft"  # draft | pass | fail | blocked
    if "last_run_at" not in case:
        case["last_run_at"] = ""
    if "run_notes" not in case:
        case["run_notes"] = ""
    if "created_at" not in case:
        case["created_at"] = _now_iso()
    if "updated_at" not in case:
        case["updated_at"] = case.get("created_at") or _now_iso()
    return case


def _generate_cases_from_history(record: dict[str, Any]) -> list[dict[str, Any]]:
    return _svc_generate_cases_from_history(
        record=record,
        normalize_record=_normalize_record,
        normalize_case=_normalize_case,
        now_iso=_now_iso,
        manual_from_legacy_fields_buttons=_manual_from_legacy_fields_buttons,
        legacy_buttons_fields_from_elements=_legacy_buttons_fields_from_elements,
        read_config=_read_config,
        get_llm_vision_runtime=_get_llm_vision_runtime,
    )


def _parse_menu_from_filename(filename: str) -> tuple[str, list[dict[str, Any]]]:
    name_without_ext = os.path.splitext(filename)[0]
    parts = [p for p in name_without_ext.split("_") if p != ""]
    # 当前项目约定：文件名即菜单路径（一级_二级_三级_按钮...）
    # 为后续兼容多系统保留 system_name 字段，但当前固定为同一个系统。
    system_name = "默认系统"
    menu_structure = [{"level": i + 1, "name": item} for i, item in enumerate(parts)]
    return system_name, menu_structure


def _is_valid_filename(name: str) -> bool:
    if not name or name.strip() != name:
        return False
    # Basic hardening for Windows paths
    forbidden = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    if any(ch in name for ch in forbidden):
        return False
    if ".." in name:
        return False
    return True


def _rename_upload(old_name: str, new_name: str) -> tuple[bool, str]:
    if old_name == new_name:
        return True, ""
    if not _is_valid_filename(new_name):
        return False, "Invalid file name"
    old_path = UPLOAD_DIR / old_name
    new_path = UPLOAD_DIR / new_name
    if not old_path.exists():
        return False, "Original file missing"
    if new_path.exists():
        return False, "File name already exists"
    try:
        if old_path.is_file():
            old_path.rename(new_path)
            return True, ""
        return False, "Original file missing"
    except Exception:
        return False, "Rename failed"


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    file_name = record.get("file_name")
    if isinstance(file_name, str) and file_name:
        system_name, menu_structure = _parse_menu_from_filename(file_name)
        record["system_name"] = system_name
        record["menu_structure"] = menu_structure
        record["file_url"] = f"/uploads/{file_name}"
    # Ensure timestamps exist
    if not record.get("created_at"):
        record["created_at"] = _now_iso()
    if not record.get("updated_at"):
        record["updated_at"] = record.get("created_at") or _now_iso()
    if "analysis" not in record:
        record["analysis"] = ""
    # 系统需求分析库：四类分析结果（覆盖式保存）
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
    if "manual" not in record or not isinstance(record.get("manual"), dict):
        record["manual"] = {
            "page_type": "",  # list | form | detail | modal | unknown
            "page_elements": [],
            "buttons": [],  # legacy mirror
            "fields": [],  # legacy mirror
            "text_requirements": "",
            "control_logic": "",
            "ocr_raw_text": "",
            "ocr_refs": {"button_candidates": [], "field_candidates": []},
        }
    else:
        m = _manual_from_legacy_fields_buttons(record["manual"])
        # 兼容旧逻辑：继续提供 buttons/fields 镜像
        b, f = _legacy_buttons_fields_from_elements(m)
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
    return record


def _menu_names(record: dict[str, Any]) -> list[str]:
    return _svc_menu_names(record)


def _breadcrumb_for_record(record: dict[str, Any]) -> str:
    return _svc_breadcrumb_for_record(record)


def _contextual_hints_from_menu(names: list[str]) -> list[str]:
    return _svc_contextual_hints_from_menu(names)


def _build_analysis(record: dict[str, Any]) -> str:
    return _svc_build_analysis(record)


def _infer_container(record: dict[str, Any], ocr_text: str) -> str:
    manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
    page_type = manual.get("page_type") if isinstance(manual.get("page_type"), str) else ""
    if page_type == "modal":
        return "弹窗"
    if page_type == "form":
        return "表单"

    # Fallback: infer by common UI words
    t = "".join((ocr_text or "").split())
    if any(x in t for x in ["取消", "确定", "关闭", "返回"]):
        return "弹窗"
    return "页面"


def _build_tested_items_from_ocr(record: dict[str, Any], ocr_text: str) -> tuple[list[dict[str, Any]], str]:
    """
    From OCR text, build structured tested-items suggestions.
    Example: if OCR contains '姓名', create an expected tested item for the 姓名 input.
    """
    container = _infer_container(record, ocr_text)
    t_raw = ocr_text or ""
    # OCR 结果可能包含空格/换行/奇怪分隔符；用去空白版本做关键词匹配更稳
    t = "".join(t_raw.split())

    field_map: list[tuple[list[str], str, list[str]]] = [
        (["姓名"], "姓名", ["必填性校验（空值不可提交/有明确提示）", "长度边界校验（最小/最大长度按规则）", "特殊字符/空格规则校验（提示清晰、禁止非法提交）", "正确输入后允许提交且数据回显一致"]),
        (["手机号", "电话", "手机"], "手机号", ["必填性校验", "格式校验（仅数字/允许前缀规则按产品约定）", "长度边界校验", "输入非法值时提示文案准确且禁止提交"]),
        (["邮箱"], "邮箱", ["必填性校验", "邮箱格式校验（如需包含@与域名）", "长度边界校验", "输入非法值时提示文案准确且禁止提交"]),
        (["用户名", "账号", "登录名"], "用户名/账号", ["必填性校验", "字符集/长度校验（去除首尾空格/非法字符提示）", "输入非法值禁止提交", "正确输入后提交成功提示与回显正确"]),
        (["密码"], "密码", ["必填性校验", "长度边界校验（最小/最大长度）", "错误/弱密码规则提示（如有强度要求）", "正确输入后提交成功且不会出现异常"]),
        (["证件号", "身份证"], "证件号码", ["必填性校验", "格式/长度校验（按证件类型）", "非法字符与空格处理", "错误输入时提示准确且禁止提交"]),
        (["学号", "工号", "编号"], "编号类字段", ["唯一性校验（如有）", "格式/长度校验", "非法字符拦截", "提交后回显正确"]),
        (["备注", "说明"], "备注", ["非必填/必填规则校验（按产品约定）", "长度边界校验", "含特殊字符/空格处理符合预期", "输入非法超长时提示行为正确"]),
        (["金额", "收款金额", "金额(元)"], "金额", ["数字范围/正负校验（不允许负数/超过上限）", "小数位规则（如仅允许两位）", "输入非法值提示清晰且禁止提交", "正确金额提交后结果计算/展示正确"]),
        (["数量", "数量(件)", "件数"], "数量", ["数字范围校验（不允许0/负数/超上限）", "只能输入整数/符合产品约束", "输入非法值提示清晰且禁止提交", "正确输入后提交成功且数量展示正确"]),
        (["日期", "时间", "出生日期"], "日期时间", ["日期范围校验（起止/历史/未来）", "格式校验", "手输与选择器一致性", "非法值拦截与提示"]),
        (["区域", "区域名称", "区域代码"], "区域信息", ["下拉枚举/联动正确", "无效组合拦截", "查询与展示一致", "切换后统计数据正确"]),
    ]

    tested_items: list[dict[str, Any]] = []

    def _push(title: str, direction: list[str]) -> None:
        if any(x.get("title") == title for x in tested_items):
            return
        tested_items.append({"title": title, "direction": "\n".join(direction)})

    # Detect fields
    for keys, display_name, directions in field_map:
        if any(k in t for k in keys):
            title = f"{container}内填写处 - {display_name}"
            _push(title, directions)

    # Detect actions
    action_checks: list[tuple[list[str], str, list[str]]] = [
        (["保存", "提交", "确定"], "保存/提交按钮", ["校验触发：必填/格式/长度不通过时禁止提交", "loading/禁用态：连续点击不应重复提交", "成功后提示文案正确、数据刷新正确", "失败/接口异常时错误提示可读且可重试"]),
        (["取消", "关闭", "返回"], "取消/关闭按钮", ["取消后不产生数据变更", "弹窗关闭后界面状态符合预期", "再次打开弹窗：默认值/数据回到上次状态或初始状态（按产品约定）"]),
        (["删除"], "删除按钮/删除确认", ["删除前二次确认：取消不删除、确认才删除", "删除成功提示与列表刷新正确", "接口失败时错误提示清晰且数据不丢失"]),
        (["查询", "搜索", "筛选"], "查询/筛选", ["不填条件返回默认/全量结果", "填入关键字段后命中正确", "重置/清空后结果回到初始状态", "异常条件（空数据/接口失败）有明确提示"]),
        (["重置", "清空"], "重置/清空", ["重置后查询条件回到初始状态", "重置不触发非预期提交", "重置后列表/统计表现正确"]),
        (["新增", "添加", "新建"], "新增", ["入口可打开新增表单/弹窗", "新增校验触发正确", "新增成功后列表/详情联动"]),
        (["编辑", "修改"], "编辑/修改", ["进入编辑时数据回填正确", "修改后保存成功并更新展示", "并发更新/失效版本提示清晰"]),
        (["打印"], "打印", ["打印入口可用", "打印内容与筛选条件一致", "空数据打印提示清晰"]),
        (["导出", "导出数据"], "导出", ["导出触发时参数正确（基于当前筛选条件）", "导出成功提示与文件内容正确", "无数据时提示明确且不生成错误文件", "接口失败时错误提示清晰"]),
    ]
    for keys, title, direction in action_checks:
        if any(k in t for k in keys):
            _push(f"{container}操作 - {title}", direction)

    # Always provide at least one item
    if not tested_items:
        _push(f"{container}通用验证", ["验证关键区域可见且无明显报错", "按钮交互：可点/loading/禁用态正确", "接口失败时错误提示清晰", "异常/边界值行为符合预期"])

    # Build analysis suffix
    bullet_lines = []
    for it in tested_items[:12]:
        dir_text = str(it.get("direction") or "")
        bullet_lines.append(f"- {it.get('title')}\n  {dir_text.replace(chr(10), chr(10) + '  ')}")

    suffix = "\n\nOCR识别修正后的被测项建议：\n" + "\n".join(bullet_lines)
    return tested_items[:12], suffix


def _build_manual_draft_from_ocr(record: dict[str, Any], ocr_text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Build structured `manual` from OCR text.
    Used by the OCR analysis modal to pre-fill fillable fields + action buttons.
    Returns: (manual_draft, field_hints)
    """
    container = _infer_container(record, ocr_text)
    t_raw = ocr_text or ""
    t_norm = "".join(t_raw.split())

    page_type = "list"
    if container == "弹窗":
        page_type = "modal"
    elif container == "表单":
        page_type = "form"

    field_map: list[tuple[list[str], str, list[str], bool]] = [
        (["姓名"], "姓名", ["必填性校验（空值不可提交/有明确提示）", "长度边界校验（最小/最大长度按规则）", "特殊字符/空格规则校验（提示清晰、禁止非法提交）", "正确输入后允许提交且数据回显一致"], True),
        (["手机号", "电话", "手机"], "手机号", ["必填性校验", "格式校验（仅数字/允许前缀规则按产品约定）", "长度边界校验", "输入非法值时提示文案准确且禁止提交"], True),
        (["邮箱"], "邮箱", ["必填性校验", "邮箱格式校验（如需包含@与域名）", "长度边界校验", "输入非法值时提示文案准确且禁止提交"], True),
        (["用户名", "账号", "登录名"], "用户名/账号", ["必填性校验", "字符集/长度校验（去除首尾空格/非法字符提示）", "输入非法值禁止提交", "正确输入后提交成功提示与回显正确"], True),
        (["密码"], "密码", ["必填性校验", "长度边界校验（最小/最大长度）", "错误/弱密码规则提示（如有强度要求）", "正确输入后提交成功且不会出现异常"], True),
        (["备注", "说明"], "备注", ["非必填/必填规则校验（按产品约定）", "长度边界校验", "含特殊字符/空格处理符合预期", "输入非法超长时提示行为正确"], False),
        (["金额", "收款金额", "金额(元)"], "金额", ["数字范围/正负校验（不允许负数/超过上限）", "小数位规则（如仅允许两位）", "输入非法值提示清晰且禁止提交", "正确金额提交后结果计算/展示正确"], True),
        (["数量", "数量(件)", "件数"], "数量", ["数字范围校验（不允许0/负数/超上限）", "只能输入整数/符合产品约束", "输入非法值提示清晰且禁止提交", "正确输入后提交成功且数量展示正确"], True),
    ]

    def _keys_match(keys: list[str]) -> bool:
        for k in keys:
            k_norm = "".join(k.split())
            if k in t_raw or k_norm in t_norm:
                return True
        return False

    def _guess_type(field_display_name: str) -> str:
        n = field_display_name
        if any(x in n for x in ["手机号", "电话", "手机"]):
            return "phone"
        if "邮箱" in n:
            return "email"
        if any(x in n for x in ["金额", "数量"]):
            return "number"
        return "text"

    def _field_defaults(field_display_name: str, field_type: str) -> dict[str, Any]:
        # Defaults are meant to help case generation seeds.
        if field_display_name == "姓名":
            return {"validation": "2-20位中文", "min_len": 2, "max_len": 20}
        if field_display_name == "手机号":
            return {"validation": "11位数字", "min_len": 11, "max_len": 11}
        if field_display_name == "邮箱":
            return {"validation": "", "min_len": 5, "max_len": 50}
        if field_display_name in ["用户名/账号", "用户名/账号", "用户名/账号"]:
            return {"validation": "3-20位字符", "min_len": 3, "max_len": 20}
        if field_display_name == "用户名/账号":
            return {"validation": "3-20位字符", "min_len": 3, "max_len": 20}
        if field_display_name == "密码":
            return {"validation": "6-20位", "min_len": 6, "max_len": 20}
        if field_display_name == "备注":
            return {"validation": "", "min_len": "", "max_len": 200}
        if field_display_name == "金额":
            return {"validation": "非负数（允许两位小数）", "min_len": "", "max_len": ""}
        if field_display_name == "数量":
            return {"validation": "正整数（>=1）", "min_len": "", "max_len": ""}
        # Generic fallback
        return {"validation": "", "min_len": "", "max_len": ""}

    fields: list[dict[str, Any]] = []
    field_hints: list[dict[str, Any]] = []

    for keys, display_name, directions, required in field_map:
        if _keys_match(keys):
            ftype = _guess_type(display_name)
            defaults = _field_defaults(display_name, ftype)
            hint_text = "\n".join([f"- {d}" for d in directions])
            fields.append(
                {
                    "name": display_name,
                    "type": ftype,
                    "required": bool(required),
                    "queryable": False,
                    "validation": defaults.get("validation", ""),
                    "min_len": defaults.get("min_len", ""),
                    "max_len": defaults.get("max_len", ""),
                    "options": [],
                    "hint": hint_text,
                }
            )
            field_hints.append({"name": display_name, "direction": hint_text})

    # 按用户要求：不自动生成“可填写字段/被测方向”，仅保留按钮与页面类型，字段由人工补录。
    fields = []
    field_hints = []

    # Buttons
    buttons: list[dict[str, Any]] = []

    def _push_btn(
        name: str,
        action: str,
        opens_modal: bool = False,
        requires_confirm: bool = False,
        matched_by: str = "",
    ) -> None:
        if any(b.get("name") == name for b in buttons):
            return
        buttons.append(
            {
                "name": name,
                "action": action,
                "opens_modal": opens_modal,
                "requires_confirm": requires_confirm,
                "source": "ocr",
                "source_text": matched_by or name,
            }
        )

    # Always include Cancel + Save so your modal actions are consistent across pages.
    _push_btn("取消", "open", False, False, "默认保底按钮")
    _push_btn("保存", "edit", False, False, "默认保底按钮")

    action_checks: list[tuple[list[str], str, str, bool, bool]] = [
        (["查询", "搜索", "筛选"], "查询", "query", False, False),
        (["新增", "添加", "新建"], "新增", "create", True, False),
        (["编辑", "修改", "更新"], "修改", "edit", True, False),
        (["删除"], "删除", "delete", False, True),
    ]
    for keys, name, action, opens_modal, requires_confirm in action_checks:
        matched = ""
        for k in keys:
            if k in t_raw or "".join(k.split()) in t_norm:
                matched = k
                break
        if matched:
            _push_btn(name, action, opens_modal, requires_confirm, matched)

    page_elements: list[dict[str, Any]] = []
    for b in buttons:
        if not isinstance(b, dict):
            continue
        n = _normalize_page_element(
            {
                "name": b.get("name"),
                "element_type": "button",
                "ui_pattern": "按钮",
                "action": b.get("action"),
                "opens_modal": b.get("opens_modal"),
                "requires_confirm": b.get("requires_confirm"),
                "source": b.get("source") or "ocr",
                "source_text": b.get("source_text") or "",
            }
        )
        if n:
            page_elements.append(n)
    manual_draft = {"page_type": page_type, "buttons": buttons, "fields": fields, "page_elements": page_elements, "control_logic": "", "text_requirements": ""}
    return manual_draft, field_hints


def _merge_manual_draft(base: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    """
    用 LLM 视觉提取结果修正 OCR 规则草稿，优先提升按钮准确率。
    """
    out = dict(base if isinstance(base, dict) else {})
    base_buttons = out.get("buttons") if isinstance(out.get("buttons"), list) else []
    base_fields = out.get("fields") if isinstance(out.get("fields"), list) else []
    llm_buttons = llm.get("buttons") if isinstance(llm.get("buttons"), list) else []
    llm_fields = llm.get("fields") if isinstance(llm.get("fields"), list) else []

    def _name(v: Any) -> str:
        return v.get("name").strip() if isinstance(v, dict) and isinstance(v.get("name"), str) else ""

    # 按钮：优先采用 LLM 识别（更贴近视觉），再补 OCR 规则中的缺失按钮。
    merged_buttons: list[dict[str, Any]] = []
    seen_btn: set[str] = set()
    for arr in [llm_buttons, base_buttons]:
        for b in arr:
            n = _name(b)
            if not n or n in seen_btn:
                continue
            seen_btn.add(n)
            merged_buttons.append(
                {
                    "name": n,
                    "action": b.get("action") if isinstance(b.get("action"), str) else "open",
                    "opens_modal": bool(b.get("opens_modal")),
                    "requires_confirm": bool(b.get("requires_confirm")),
                    "source": b.get("source") if isinstance(b.get("source"), str) else "",
                    "source_text": b.get("source_text") if isinstance(b.get("source_text"), str) else "",
                }
            )

    # 字段：按用户要求不自动生成，保持为空，后续由“数据需求补充”人工维护。
    merged_fields: list[dict[str, Any]] = []

    # 保底按钮，避免编辑器无法操作
    if not any(_name(x) == "取消" for x in merged_buttons):
        merged_buttons.append({"name": "取消", "action": "open", "opens_modal": False, "requires_confirm": False, "source": "default", "source_text": "保底动作"})
    if not any(_name(x) == "保存" for x in merged_buttons):
        merged_buttons.append({"name": "保存", "action": "edit", "opens_modal": False, "requires_confirm": False, "source": "default", "source_text": "保底动作"})

    out["buttons"] = merged_buttons[:24]
    out["fields"] = merged_fields
    llm_page_type = llm.get("page_type") if isinstance(llm.get("page_type"), str) else ""
    if llm_page_type in ["list", "form", "detail", "modal", "unknown"]:
        out["page_type"] = llm_page_type
    llm_logic = llm.get("control_logic") if isinstance(llm.get("control_logic"), str) else ""
    if llm_logic.strip():
        out["control_logic"] = llm_logic.strip()
    return out


def _get_llm_vision_runtime(cfg: dict[str, Any]) -> tuple[bool, str, str, str]:
    """
    returns: enabled, api_key, base_url, model
    """
    analysis_cfg = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
    lv = analysis_cfg.get("llm_vision") if isinstance(analysis_cfg.get("llm_vision"), dict) else {}
    ocr_cfg = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
    ds_cfg = ocr_cfg.get("dashscope") if isinstance(ocr_cfg.get("dashscope"), dict) else {}
    api_key_lv = lv.get("api_key") if isinstance(lv.get("api_key"), str) else ""
    api_key_ds = ds_cfg.get("api_key") if isinstance(ds_cfg.get("api_key"), str) else ""
    api_key = api_key_lv or api_key_ds or (os.getenv("DASHSCOPE_API_KEY") or "")
    enabled = bool(lv.get("enabled")) and bool(api_key)
    base_url = (
        lv.get("base_url") if isinstance(lv.get("base_url"), str) and lv.get("base_url") else None
    ) or (
        ds_cfg.get("base_url") if isinstance(ds_cfg.get("base_url"), str) and ds_cfg.get("base_url") else None
    ) or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = lv.get("model") if isinstance(lv.get("model"), str) and lv.get("model") else "qwen-vl-plus"
    return enabled, api_key, base_url, model


def _get_llm_text_runtime(cfg: dict[str, Any]) -> tuple[bool, str, str, str]:
    """
    DashScope OpenAI-compatible text completion runtime.
    使用 analysis.llm_vision 的 enabled 和 OCR dashscope 的 api_key/base_url 复用配置。
    """
    enabled, api_key, base_url, _ = _get_llm_vision_runtime(cfg)
    analysis_cfg = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
    case_cfg = {}
    if isinstance(analysis_cfg.get("case_generation"), dict):
        case_cfg = analysis_cfg.get("case_generation")
    model = "qwen-plus"
    if isinstance(case_cfg.get("model"), str) and case_cfg.get("model"):
        model = case_cfg["model"]
    return enabled, api_key, base_url, model


def _dashscope_text_completion(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    timeout: int = 120,
    temperature: float = 0.4,
) -> str:
    import urllib.request
    import urllib.error

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": (system_prompt or "").strip()},
            {"role": "user", "content": (user_prompt or "").strip()},
        ],
        "temperature": temperature,
    }
    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        return str(content).strip()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        return f"LLM 请求失败（HTTP {e.code}）：{detail[:800]}"
    except Exception as e:
        return f"LLM 请求失败：{e}"


def _generate_requirement_library_for_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    为单个 history 记录生成四类“系统需求分析库”内容：
    1) 样式分析（OCR）
    2) 需求内容分析（LLM + 文字补充）
    3) 交互分析（菜单关联）
    4) 数据分析（OCR 内容分批结构化）
    """
    found = _normalize_record(record)
    manual = found.get("manual") if isinstance(found.get("manual"), dict) else {}
    text_req = str(manual.get("text_requirements") or "").strip()
    ctrl_req = str(manual.get("control_logic") or "").strip()
    page_type = str(manual.get("page_type") or "").strip()

    # Breadcrumb/menu-driven metadata
    breadcrumb = _breadcrumb_for_record(found)
    file_name = str(found.get("file_name") or "").strip()

    # 1) 样式分析（基于 OCR）
    ok, provider, ocr_text_or_err = _ocr_extract_text(found)
    ocr_text = ocr_text_or_err if ok else ""
    if not isinstance(ocr_text, str):
        ocr_text = str(ocr_text or "")

    # OCR 过长只取摘要，避免数据库/前端爆炸
    ocr_excerpt = ocr_text.strip()
    if len(ocr_excerpt) > 6000:
        ocr_excerpt = ocr_excerpt[:6000] + "\n...[OCR 摘要截断]"

    if ok:
        analysis_style = f"OCR识别原文（来自 {provider}，摘要）：\n{ocr_excerpt}".strip()
    else:
        analysis_style = f"OCR识别失败：{ocr_text_or_err}".strip()

    # 2/4) 数据分析改为“需求归纳”，不再输出面向测试用例生成的 tested_items/batches 结构
    elts = manual.get("page_elements") if isinstance(manual.get("page_elements"), list) else []
    elements_overview: list[dict[str, Any]] = []
    for e in elts[:200]:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        if not name:
            continue
        elements_overview.append(
            {
                "name": name,
                "element_type": str(e.get("element_type") or "other").strip().lower(),
                "ui_pattern": str(e.get("ui_pattern") or ""),
                "required": bool(e.get("required")),
                "queryable": bool(e.get("queryable")),
                "validation": str(e.get("validation") or ""),
                "action": str(e.get("action") or ""),
                "opens_modal": bool(e.get("opens_modal")),
                "requires_confirm": bool(e.get("requires_confirm")),
            }
        )

    analysis_data = {
        "ocr_provider": provider if ok else "none",
        "ocr_raw_excerpt": ocr_excerpt if ok else "",
        "elements_overview": elements_overview,
        "note": "该模块仅用于需求归纳与后续向量检索；不输出面向测试用例生成的结构化 tested_items。",
    }

    # 3) 交互分析（菜单关联：基于菜单路径的测试关注点）
    interaction = _build_analysis(found)
    elts = manual.get("page_elements") if isinstance(manual.get("page_elements"), list) else []
    btn_names = [e.get("name") for e in elts if isinstance(e, dict) and str(e.get("element_type") or "").lower() == "button" and e.get("name")]
    field_names = [
        e.get("name")
        for e in elts
        if isinstance(e, dict)
        and str(e.get("element_type") or "").lower() in ["field", "filter"]
        and e.get("name")
    ]
    if btn_names or field_names:
        interaction = interaction.strip() + "\n\n【页面元素补录概览】\n" + f"- 按钮：{btn_names[:20]}" + "\n" + f"- 可填写/筛选：{field_names[:20]}"

    analysis_interaction = interaction.strip()

    # 2) 需求内容分析（LLM + 文字补充）
    analysis_content = ""
    # 仅当你提供了“文字需求补充/控制备注”时才调用大模型，避免慢/超时/无意义的输出
    if not (text_req or ctrl_req):
        analysis_content = "文字需求补充与控制备注为空：跳过需求内容分析（待你补录后再一键生成）。"
    else:
        cfg = _read_config()
        llm_enabled, api_key, base_url, model = _get_llm_text_runtime(cfg)
        if llm_enabled and api_key:
            style_block = f"OCR识别原文摘要：\n{ocr_excerpt}"
            text_block = f"文字需求补充：\n{text_req or '（未填写）'}"
            ctrl_block = f"控制/流程备注：\n{ctrl_req or '（未填写）'}"
            user_prompt = (
                f"请基于以下信息输出《系统需求分析库 - 需求内容分析》（中文）。\n\n"
                f"- 菜单路径：{breadcrumb}\n"
                f"- 页面类型：{page_type or '未知'}\n"
                f"- 截图文件：{file_name}\n\n"
                f"{text_block}\n\n"
                f"{ctrl_block}\n\n"
                f"{style_block}\n\n"
                f"输出要求：\n"
                f"1) 结构化分章节（业务目标/范围/关键规则/字段与按钮约束/验收与异常口径/关键验证点）。\n"
                f"2) 尽量不要空泛套话；必须和“文字需求补充”存在的内容相呼应。\n"
                f"3) 若文字需求补充为空，则给出“待补录问题清单”，不要编造。\n"
            )
            system_prompt = "你是资深业务需求拆解与测试分析师。请输出结构化、可落地的需求拆解结果。"
            analysis_content = _dashscope_text_completion(
                api_key=api_key,
                base_url=base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        else:
            analysis_content = "LLM未配置或不可用：请在 config.local.json 的 analysis/ocr 配置 api_key 后重试。"

    return {
        "analysis_style": analysis_style,
        "analysis_content": analysis_content,
        "analysis_interaction": analysis_interaction,
        "analysis_data": analysis_data,
    }


def _ocr_local_tesseract(image_path: Path, lang: str, tesseract_cmd: str | None = None) -> tuple[bool, str]:
    """
    Zero-token OCR option. Requires:
    - tesseract installed on system
    - pip install pytesseract pillow
    """
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return False, "Local OCR not available. Install: pip install pytesseract pillow (and install Tesseract OCR)."

    try:
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        img = Image.open(str(image_path))
        # Basic preprocessing to improve accuracy for UI screenshots
        try:
            from PIL import ImageOps  # type: ignore

            img = ImageOps.exif_transpose(img)
            img = ImageOps.grayscale(img)
            w, h = img.size
            img = img.resize((int(w * 2), int(h * 2)))
        except Exception:
            pass

        text = pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6")
        return True, text
    except Exception as e:
        return False, f"Local OCR failed: {e}"


def _youdao_input(img_b64: str) -> str:
    if len(img_b64) <= 20:
        return img_b64
    return img_b64[:10] + str(len(img_b64)) + img_b64[-10:]


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _ocr_netease_youdao(image_path: Path, app_key: str, app_secret: str, lang_type: str = "zh-CHS") -> tuple[bool, str]:
    """
    NetEase Youdao OCR (通用OCR) via https://openapi.youdao.com/ocrapi
    Doc: https://ai.youdao.com/DOCSIRMA/html/ocr/api/tyocr/index.html
    """
    import urllib.request
    import urllib.error

    img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    salt = str(uuid.uuid4())
    curtime = str(int(time.time()))
    sign = _sha256_hex(app_key + _youdao_input(img_b64) + salt + curtime + app_secret)

    params = {
        "img": img_b64,
        "langType": lang_type,
        "detectType": "10012",
        "imageType": "1",
        "appKey": app_key,
        "salt": salt,
        "sign": sign,
        "docType": "json",
        "signType": "v3",
        "curtime": curtime,
        "angle": "0",
        "column": "onecolumn",
    }

    data = urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url="https://openapi.youdao.com/ocrapi",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        return False, f"NetEase Youdao OCR HTTP {e.code}: {detail}"
    except Exception as e:
        return False, f"NetEase Youdao OCR failed: {e}"

    if str(payload.get("errorCode")) != "0":
        return False, f"NetEase Youdao OCR errorCode={payload.get('errorCode')}"

    # Extract text: Result->regions->lines->text
    result = payload.get("Result") or {}
    regions = result.get("regions") or []
    lines_out: list[str] = []
    if isinstance(regions, list):
        for r in regions:
            if not isinstance(r, dict):
                continue
            lines = r.get("lines") or []
            if not isinstance(lines, list):
                continue
            for ln in lines:
                if isinstance(ln, dict) and isinstance(ln.get("text"), str):
                    txt = ln["text"].strip()
                    if txt:
                        lines_out.append(txt)
    return True, "\n".join(lines_out).strip()

def _ocr_dashscope(image_path: Path, api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """
    DashScope OpenAI-compatible endpoint for Qwen OCR models.
    Uses data URL so no public image hosting needed.
    """
    import urllib.request
    import urllib.error

    mime, _ = mimetypes.guess_type(str(image_path))
    mime = mime or "image/png"
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "请只输出图片中的文字内容，不要添加多余解释。"},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read().decode("utf-8"))
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        return True, str(content)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = ""
        return False, f"DashScope OCR HTTP {e.code}: {detail}"
    except Exception as e:
        return False, f"DashScope OCR failed: {e}"


def _ocr_extract_text(record: dict[str, Any]) -> tuple[bool, str, str]:
    """
    Returns: ok, provider, text_or_error
    provider: 'tesseract' | 'dashscope'
    """
    record = _normalize_record(record)
    file_name = record.get("file_name")
    if not isinstance(file_name, str) or not file_name:
        return False, "none", "Missing file_name"
    image_path = UPLOAD_DIR / file_name
    if not image_path.exists():
        return False, "none", "Image file not found"

    cfg = _read_config()
    ocr_cfg = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
    provider = ocr_cfg.get("provider", "auto")

    # Try local first (0 token)
    tess_cfg = ocr_cfg.get("tesseract") if isinstance(ocr_cfg.get("tesseract"), dict) else {}
    tess_enabled = tess_cfg.get("enabled", True)
    tess_lang = tess_cfg.get("lang", "chi_sim+eng")
    tess_cmd = tess_cfg.get("cmd") if isinstance(tess_cfg.get("cmd"), str) else None
    if provider in ["auto", "tesseract"] and tess_enabled:
        ok, text = _ocr_local_tesseract(image_path, tess_lang, tess_cmd)
        if ok:
            return True, "tesseract", text
        if provider == "tesseract":
            return False, "tesseract", text

    # NetEase Youdao OCR fallback
    yd_cfg = ocr_cfg.get("netease_youdao") if isinstance(ocr_cfg.get("netease_youdao"), dict) else {}
    yd_app_key = yd_cfg.get("app_key") if isinstance(yd_cfg.get("app_key"), str) else ""
    yd_app_secret = yd_cfg.get("app_secret") if isinstance(yd_cfg.get("app_secret"), str) else ""
    yd_lang = yd_cfg.get("lang_type") if isinstance(yd_cfg.get("lang_type"), str) else "zh-CHS"
    if provider in ["auto", "netease"] and yd_app_key and yd_app_secret:
        ok, text = _ocr_netease_youdao(image_path, yd_app_key, yd_app_secret, yd_lang)
        if ok:
            return True, "netease_youdao", text
        if provider == "netease":
            return False, "netease_youdao", text

    # DashScope fallback
    ds_cfg = ocr_cfg.get("dashscope") if isinstance(ocr_cfg.get("dashscope"), dict) else {}
    api_key = ds_cfg.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or ""
    base_url = ds_cfg.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = ds_cfg.get("model") or "qwen-vl-ocr-2025-11-20"
    if provider in ["auto", "dashscope"] and api_key:
        ok, text = _ocr_dashscope(image_path, api_key, base_url, model)
        if ok:
            return True, "dashscope", text
        return False, "dashscope", text

    return False, "none", "No OCR provider configured. Create config.local.json (see config.local.example.json)."


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")

    def _send_json(self, status: int, data: Any) -> None:
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self._send_cors()
        self.end_headers()
        self.wfile.write(_json_bytes(data))

    def _send_text(self, status: int, text: str) -> None:
        self.send_response(status)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self._send_cors()
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_text(200, "LLM Case System Backend")
            return

        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/history":
            items = _read_history()
            changed = False
            normalized = []
            for r in items:
                before = json.dumps(r, ensure_ascii=False, sort_keys=True)
                nr = _normalize_record(r)
                after = json.dumps(nr, ensure_ascii=False, sort_keys=True)
                if before != after:
                    changed = True
                normalized.append(nr)
            if changed:
                _write_history(normalized)
            items = normalized
            self._send_json(200, items)
            return

        if path.startswith("/api/history/"):
            try:
                rid = int(path[len("/api/history/") :])
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            items = _read_history()
            found = next((x for x in items if int(x.get("id", -1)) == rid), None)
            if not found:
                self._send_json(404, {"error": "Not found"})
                return
            found = _normalize_record(found)
            self._send_json(200, found)
            return

        # ---- SSE：需求分析库批量生成（带进度/输出预览）----
        # 用于前端显示“AI 在分析/生成”的过程与结果片段
        if path == "/api/requirement-analysis/generate/sse":
            force = (qs.get("force") or ["1"])[0]
            try:
                records = [_normalize_record(x) for x in _read_history()]
            except Exception as e:
                # SSE 失败直接返回 JSON
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return

            # SSE headers
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self._send_cors()
            self.end_headers()

            def _sse(event: str, data: dict[str, Any]) -> None:
                try:
                    self.wfile.write(f"event: {event}\n".encode("utf-8"))
                    self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    # 客户端断开时不影响服务端其他请求
                    pass

            generated = 0
            errors: list[dict[str, Any]] = []
            total = len(records)
            _sse("log", {"msg": "开始生成系统需求分析库..."})

            for r in records:
                hid = r.get("id")
                if hid is None:
                    continue
                hid_i = int(hid)
                need = str(force) == "1" or not (
                    str(r.get("analysis_style") or "").strip()
                    and str(r.get("analysis_content") or "").strip()
                    and str(r.get("analysis_interaction") or "").strip()
                )
                if not need:
                    _sse("progress", {"history_id": hid_i, "stage": "skip", "generated": generated, "total": total})
                    continue

                _sse("progress", {"history_id": hid_i, "stage": "start", "generated": generated, "total": total})
                try:
                    out = _generate_requirement_library_for_record(r)
                    r["analysis_style"] = out.get("analysis_style") or ""
                    r["analysis_content"] = out.get("analysis_content") or ""
                    r["analysis_interaction"] = out.get("analysis_interaction") or ""
                    r["analysis_data"] = out.get("analysis_data")
                    r["analysis_generated_at"] = _now_iso()
                    r["updated_at"] = _now_iso()
                    generated += 1

                    # 输出预览：截断展示，避免 SSE 包过大
                    style_preview = str(r.get("analysis_style") or "")[:220]
                    content_preview = str(r.get("analysis_content") or "")[:520]
                    interaction_preview = str(r.get("analysis_interaction") or "")[:220]
                    _sse(
                        "log",
                        {
                            "history_id": hid_i,
                            "msg": f"[{hid_i}] 样式/内容/交互已生成（预览）",
                            "previews": {
                                "analysis_style": style_preview,
                                "analysis_content": content_preview,
                                "analysis_interaction": interaction_preview,
                            },
                        },
                    )
                    _sse("progress", {"history_id": hid_i, "stage": "done", "generated": generated, "total": total})
                except Exception as e:
                    err = str(e)
                    errors.append({"history_id": hid_i, "error": err})
                    _sse("log", {"history_id": hid_i, "msg": f"[{hid_i}] 生成失败：{err}"})
                    _sse("progress", {"history_id": hid_i, "stage": "error", "generated": generated, "total": total})

            try:
                _write_history(records)
                _sse("log", {"msg": "已保存需求分析库到数据库/文件。"})
            except Exception as e:
                _sse("log", {"msg": f"保存失败：{e}"})
                errors.append({"history_id": None, "error": str(e)})

            _sse("done", {"ok": True, "total": total, "generated": generated, "errors": errors[:20]})
            return

        if path.startswith("/api/analyze/"):
            try:
                rid = int(path[len("/api/analyze/") :])
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            items = _read_history()
            found = next((x for x in items if int(x.get("id", -1)) == rid), None)
            if not found:
                self._send_json(404, {"error": "Not found"})
                return
            found = _normalize_record(found)
            analysis = _build_analysis(found)
            self._send_json(200, {"id": rid, "analysis": analysis})
            return

        if path == "/api/cases":
            items = [_normalize_case(x) for x in _read_cases()]
            # Optional filter by history_id
            hid = (qs.get("history_id") or [None])[0]
            if hid:
                try:
                    hid_i = int(hid)
                    items = [x for x in items if int(x.get("history_id") or 0) == hid_i]
                except Exception:
                    pass
            self._send_json(200, items)
            return

        if path.startswith("/api/cases/"):
            try:
                cid = int(path[len("/api/cases/") :])
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            items = _read_cases()
            found = next((x for x in items if int(x.get("id", -1)) == cid), None)
            if not found:
                self._send_json(404, {"error": "Not found"})
                return
            self._send_json(200, _normalize_case(found))
            return

        if path.startswith("/uploads/"):
            rel_name = unquote(path[len("/uploads/") :])
            # Basic hardening to avoid path traversal
            rel_name = rel_name.replace("\\", "/")
            if ".." in rel_name or rel_name.startswith("/"):
                self._send_text(400, "Bad filename")
                return

            full_path = UPLOAD_DIR / rel_name
            if not full_path.exists() or not full_path.is_file():
                self._send_text(404, "File not found")
                return

            content_type, _ = mimetypes.guess_type(str(full_path))
            self.send_response(200)
            self.send_header("Content-type", content_type or "application/octet-stream")
            self._send_cors()
            self.end_headers()
            with full_path.open("rb") as f:
                self.wfile.write(f.read())
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/requirement-analysis/generate":
            force = (qs.get("force") or ["1"])[0]
            try:
                records = [_normalize_record(x) for x in _read_history()]
            except Exception as e:
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return

            generated = 0
            errors: list[dict[str, Any]] = []
            cfg = _read_config()

            for r in records:
                hid = r.get("id")
                if hid is None:
                    continue
                hid_i = int(hid)
                need = str(force) == "1" or not (
                    str(r.get("analysis_style") or "").strip()
                    and str(r.get("analysis_content") or "").strip()
                    and str(r.get("analysis_interaction") or "").strip()
                )
                if not need:
                    continue

                try:
                    out = _generate_requirement_library_for_record(r)
                    r["analysis_style"] = out.get("analysis_style") or ""
                    r["analysis_content"] = out.get("analysis_content") or ""
                    r["analysis_interaction"] = out.get("analysis_interaction") or ""
                    r["analysis_data"] = out.get("analysis_data")
                    r["analysis_generated_at"] = _now_iso()
                    r["updated_at"] = _now_iso()
                    generated += 1
                except Exception as e:
                    errors.append({"history_id": hid_i, "error": str(e)})

            try:
                _write_history(records)
            except Exception as e:
                self._send_json(500, {"error": f"保存需求库失败: {e}", "generated": generated, "errors": errors[:10]})
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "total": len(records),
                    "generated": generated,
                    "errors": errors[:20],
                },
            )
            return

        # ---- 需求网络库：构建（覆盖式） ----
        if path == "/api/requirement-network/build":
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            if not _use_mysql() or not _db_mysql:
                self._send_json(500, {"error": "MySQL 未启用或不可用，无法构建需求网络库"})
                return

            history_id = payload.get("history_id")
            force = str(payload.get("force", 1))
            unit_limit = int(payload.get("unit_limit", 0) or 0)  # 0 表示不限制，主要用于调试
            embed_model = str(payload.get("embedding_model") or "").strip()

            try:
                records = [_normalize_record(x) for x in _read_history()]
            except Exception as e:
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return

            if history_id not in [None, "", "all", "ALL"]:
                try:
                    hid_i = int(history_id)
                    records = [r for r in records if int(r.get("id") or -1) == hid_i]
                except Exception:
                    self._send_json(400, {"error": "Invalid history_id"})
                    return

            # lazy import: 避免启动时加载 embedding 模型
            try:
                from backend.requirement_network import build_atomic_units_and_edges
                from backend.embeddings_service import embed_texts
            except Exception:
                # 在部分运行方式下，simple_server.py 所在目录会作为 sys.path 根
                from requirement_network import build_atomic_units_and_edges  # type: ignore
                from embeddings_service import embed_texts  # type: ignore

            generated = 0
            errors: list[dict[str, Any]] = []
            total = len(records)

            for r in records:
                hid = r.get("id")
                if hid is None:
                    continue
                hid_i = int(hid)
                try:
                    # 若未强制覆盖且已有网络数据则跳过
                    if str(force) != "1":
                        existing = _db_mysql.read_requirement_network_for_search(history_id=hid_i)
                        if existing:
                            continue

                    units, edges = build_atomic_units_and_edges(r)
                    if unit_limit and len(units) > unit_limit:
                        units = units[:unit_limit]

                    # embedding 只对 content 做截断，保证向量检索不会被超长文本拖慢
                    texts: list[str] = []
                    unit_keys: list[str] = []
                    for u in units:
                        if not isinstance(u, dict):
                            continue
                        uk = str(u.get("unit_key") or "").strip()
                        c = str(u.get("content") or "").strip()
                        if not uk or not c:
                            continue
                        texts.append(c[:1200])
                        unit_keys.append(uk)

                    embeddings_list, used_model = ([], embed_model)
                    if texts:
                        embeddings_list, used_model = embed_texts(texts, model_name=embed_model or None)

                    embeddings: dict[str, list[float]] = {}
                    for uk, vec in zip(unit_keys, embeddings_list):
                        if isinstance(vec, list) and vec:
                            embeddings[uk] = vec

                    _db_mysql.write_requirement_network(
                        hid_i,
                        units=units,
                        edges=edges,
                        embeddings=embeddings,
                        embedding_model=used_model or embed_model or "",
                    )
                    generated += 1
                except Exception as e:
                    errors.append({"history_id": hid_i, "error": str(e)})

            self._send_json(
                200,
                {
                    "ok": True,
                    "total": total,
                    "built": generated,
                    "errors": errors[:20],
                },
            )
            return

        # ---- 需求网络库：向量检索 ----
        if path == "/api/requirement-network/search":
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}

            # 兼容：部分客户端 JSON body 解析不稳定时，允许从 URL query 参数读取
            query = str(payload.get("query") or (qs.get("query") or [None])[0] or "").strip()
            top_k = int(payload.get("top_k", (qs.get("top_k") or [8])[0]) or 8)
            unit_type = payload.get("unit_type") or (qs.get("unit_type") or [None])[0]
            history_id = payload.get("history_id") or (qs.get("history_id") or [None])[0]

            if not query:
                self._send_json(400, {"error": "query required"})
                return

            if not _use_mysql() or not _db_mysql:
                self._send_json(500, {"error": "MySQL 未启用或不可用，无法检索需求网络库"})
                return

            try:
                from backend.embeddings_service import embed_one
            except Exception:
                from embeddings_service import embed_one  # type: ignore

            # 先取 query embedding（用默认/指定模型）
            try:
                query_vec, used_model = embed_one(query)
            except Exception as e:
                self._send_json(500, {"error": f"embedding failed: {e}"})
                return
            if not query_vec:
                self._send_json(500, {"error": "empty embedding"})
                return

            try:
                hid_filter = None
                if history_id not in [None, "", "all", "ALL"]:
                    hid_filter = int(history_id)
                candidates = _db_mysql.read_requirement_network_for_search(history_id=hid_filter, unit_type=unit_type)
            except Exception as e:
                self._send_json(500, {"error": f"read network failed: {e}"})
                return

            if not candidates:
                self._send_json(200, {"ok": True, "results": [], "note": "network_not_built"})
                return

            # 余弦相似度：embedding 已 normalize（或近似 normalize），直接点积即可
            qdim = len(query_vec)
            scored: list[tuple[float, dict[str, Any]]] = []
            for c in candidates:
                emb = c.get("embedding") if isinstance(c.get("embedding"), list) else []
                if not emb or not isinstance(emb, list):
                    continue
                if len(emb) != qdim:
                    continue
                # brute-force：score = dot(q, emb)
                score = 0.0
                for i in range(qdim):
                    try:
                        score += float(query_vec[i]) * float(emb[i])
                    except Exception:
                        score += 0.0

                scored.append((score, c))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for score, c in scored[:top_k]:
                results.append(
                    {
                        "unit_key": c.get("unit_key"),
                        "unit_type": c.get("unit_type"),
                        "score": score,
                        "content": c.get("content"),
                        "metadata": c.get("metadata"),
                    }
                )
            self._send_json(200, {"ok": True, "results": results, "embedding_model": used_model})
            return

        if path == "/api/cases/generate":
            hid = (qs.get("history_id") or [None])[0]
            if not hid:
                self._send_json(400, {"error": "history_id required"})
                return
            force = (qs.get("force") or ["0"])[0]
            try:
                hid_i = int(hid)
            except Exception:
                self._send_json(400, {"error": "Invalid history_id"})
                return
            history = _read_history()
            record = next((x for x in history if int(x.get("id", -1)) == hid_i), None)
            if not record:
                self._send_json(404, {"error": "History record not found"})
                return

            record = _normalize_record(record)
            manual = record.get("manual") if isinstance(record.get("manual"), dict) else {}
            elements = manual.get("page_elements") if isinstance(manual.get("page_elements"), list) else []
            buttons, fields = _legacy_buttons_fields_from_elements(manual)
            if not elements and not buttons and not fields:
                self._send_json(400, {"error": "补录缺失：请先在“页面元素补充”中补充元素信息后再生成用例"})
                return

            generated = _generate_cases_from_history(record)
            cases = _read_cases()

            existed = [x for x in cases if int(x.get("history_id") or 0) == hid_i]
            if existed and str(force) != "1":
                self._send_json(
                    409,
                    {
                        "error": f"该截图已生成过用例（共 {len(existed)} 条）。是否删除旧用例并重新生成？",
                        "existing_count": len(existed),
                    },
                )
                return
            if existed and str(force) == "1":
                cases = [x for x in cases if int(x.get("history_id") or 0) != hid_i]

            first_id = _next_case_id()
            for i, c in enumerate(generated):
                c["id"] = first_id + i
                cases.insert(0, c)
            _write_cases(cases)
            self._send_json(201, generated)
            return

        if path == "/api/cases":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json(400, {"error": "Invalid JSON"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "Invalid payload"})
                return
            cases = _read_cases()
            cid = _next_case_id()
            case = _normalize_case(
                {
                    "id": cid,
                    "history_id": payload.get("history_id"),
                    "title": payload.get("title", ""),
                    "preconditions": payload.get("preconditions", ""),
                    "steps": payload.get("steps", []),
                    "expected": payload.get("expected", ""),
                    "status": payload.get("status", "draft"),
                    "run_notes": payload.get("run_notes", ""),
                    "last_run_at": payload.get("last_run_at", ""),
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
            )
            cases.insert(0, case)
            _write_cases(cases)
            self._send_json(201, case)
            return

        if path == "/api/upload":
            # fallthrough to existing upload implementation below
            pass
        else:
            self._send_text(404, "Not found")
            return

        # ----- existing upload implementation -----
        self.path = "/api/upload"

        if self.path != "/api/upload":
            self._send_text(404, "Not found")
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type or "boundary=" not in content_type:
            self._send_json(400, {"error": "Invalid Content-Type"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        boundary = content_type.split("boundary=")[1].encode("utf-8")
        body = self.rfile.read(content_length)

        parts = body.split(boundary)
        file_part = None
        for part in parts:
            if b"Content-Disposition" in part and b'filename="' in part:
                file_part = part
                break

        if not file_part:
            self._send_json(400, {"error": "No file part"})
            return

        filename_start = file_part.find(b'filename="') + 10
        filename_end = file_part.find(b'"', filename_start)
        filename = file_part[filename_start:filename_end].decode("utf-8", errors="replace")

        content_start = file_part.find(b"\r\n\r\n") + 4
        content_end = file_part.rfind(b"\r\n")
        file_content = file_part[content_start:content_end]

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            self._send_json(409, {"error": "文件名已存在，请修改文件名后再上传"})
            return
        with file_path.open("wb") as f:
            f.write(file_content)

        system_name, menu_structure = _parse_menu_from_filename(filename)

        items = _read_history()
        rid = _next_history_id()
        record = {
            "id": rid,
            "file_name": filename,
            "file_url": f"/uploads/{filename}",
            "system_name": system_name,
            "menu_structure": menu_structure,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "analysis": "",
        }
        items.insert(0, record)
        _write_history(items)
        self._send_json(201, record)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/cases/"):
            try:
                cid = int(path[len("/api/cases/") :])
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json(400, {"error": "Invalid JSON"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "Invalid payload"})
                return
            cases = _read_cases()
            idx = next((i for i, x in enumerate(cases) if int(x.get("id", -1)) == cid), None)
            if idx is None:
                self._send_json(404, {"error": "Not found"})
                return
            case = _normalize_case(cases[idx])
            for k in ["title", "preconditions", "expected", "status", "run_notes", "last_run_at"]:
                if k in payload and isinstance(payload[k], str):
                    case[k] = payload[k]
            if "steps" in payload and isinstance(payload["steps"], list):
                case["steps"] = [str(x) for x in payload["steps"] if str(x).strip()]
            if "history_id" in payload:
                case["history_id"] = payload["history_id"]
            case["updated_at"] = _now_iso()
            cases[idx] = case
            _write_cases(cases)
            self._send_json(200, case)
            return

        if not path.startswith("/api/history/"):
            self._send_text(404, "Not found")
            return
        try:
            rid = int(path[len("/api/history/") :])
        except Exception:
            self._send_json(400, {"error": "Invalid id"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        items = _read_history()
        idx = next((i for i, x in enumerate(items) if int(x.get("id", -1)) == rid), None)
        if idx is None:
            self._send_json(404, {"error": "Not found"})
            return

        record = items[idx]
        file_name_changed = False
        if isinstance(payload, dict):
            # 允许改文件名（同时会联动更新菜单层级与 file_url）
            if "file_name" in payload and isinstance(payload["file_name"], str):
                new_file_name = payload["file_name"].strip()
                old_file_name = record.get("file_name")
                if isinstance(old_file_name, str) and new_file_name:
                    ok, err = _rename_upload(old_file_name, new_file_name)
                    if not ok:
                        self._send_json(400, {"error": err})
                        return
                    record["file_name"] = new_file_name
                    record["file_url"] = f"/uploads/{new_file_name}"
                    # File name changes imply menu changes (current project convention)
                    record["system_name"], record["menu_structure"] = _parse_menu_from_filename(new_file_name)
                    file_name_changed = True

            # 允许覆盖菜单结构（用于手动修正）
            if "menu_structure" in payload and isinstance(payload["menu_structure"], list):
                # 如果刚改过文件名，则以文件名解析结果为准，避免不一致
                if file_name_changed:
                    pass
                else:
                    cleaned = []
                    for item in payload["menu_structure"]:
                        if not isinstance(item, dict):
                            continue
                        level = item.get("level")
                        name = item.get("name")
                        if isinstance(level, int) and isinstance(name, str):
                            cleaned.append({"level": level, "name": name})
                    record["menu_structure"] = cleaned

            # 允许保存/更新分析结果（用于后续人工编辑）
            if "analysis" in payload and isinstance(payload["analysis"], str):
                record["analysis"] = payload["analysis"]
            # 保存手动补录（结构化，用于动态生成用例）
            if "manual" in payload and isinstance(payload["manual"], dict):
                m = _manual_from_legacy_fields_buttons(payload["manual"])
                lb, lf = _legacy_buttons_fields_from_elements(m)
                m["buttons"] = lb
                m["fields"] = lf
                if not isinstance(m.get("ocr_refs"), dict):
                    m["ocr_refs"] = {"button_candidates": [], "field_candidates": []}
                if not isinstance(m.get("ocr_raw_text"), str):
                    m["ocr_raw_text"] = ""
                if not isinstance(m.get("text_requirements"), str):
                    m["text_requirements"] = ""
                if not isinstance(m.get("control_logic"), str):
                    m["control_logic"] = ""
                record["manual"] = m
        record["updated_at"] = _now_iso()
        items[idx] = record
        _write_history(items)
        self._send_json(200, record)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/cases/"):
            try:
                cid = int(path[len("/api/cases/") :])
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            cases = _read_cases()
            if not any(int(x.get("id", -1)) == cid for x in cases):
                self._send_json(404, {"error": "Not found"})
                return
            cases = [x for x in cases if int(x.get("id", -1)) != cid]
            _write_cases(cases)
            self._send_json(200, {"message": "Case deleted successfully"})
            return

        if not path.startswith("/api/history/"):
            self._send_text(404, "Not found")
            return
        try:
            rid = int(path[len("/api/history/") :])
        except Exception:
            self._send_json(400, {"error": "Invalid id"})
            return

        items = _read_history()
        record = next((x for x in items if int(x.get("id", -1)) == rid), None)
        if not record:
            self._send_json(404, {"error": "Not found"})
            return

        # Remove from history
        items = [x for x in items if int(x.get("id", -1)) != rid]
        _write_history(items)

        # Best-effort: delete uploaded file too
        try:
            file_name = record.get("file_name")
            if isinstance(file_name, str) and file_name:
                p = UPLOAD_DIR / file_name
                if p.exists() and p.is_file():
                    p.unlink()
        except Exception:
            pass

        self._send_json(200, {"message": "History record deleted successfully"})


if __name__ == "__main__":
    print(f"Starting simple HTTP server on port {PORT}...")
    print("Server will be available at http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    with socketserver.TCPServer(("0.0.0.0", PORT), MyHTTPRequestHandler) as httpd:
        httpd.serve_forever()

