#!/usr/bin/env python3

"""
绠€鍗曠殑HTTP鏈嶅姟鍣紙浠呮爣鍑嗗簱锛夛紝鎻愪緵锛?- GET  /                 鍋ュ悍妫€鏌?- POST /api/upload       鏂囦欢涓婁紶锛坢ultipart/form-data: file锛?- GET  /api/history      妯℃嫙鍘嗗彶璁板綍
- DELETE /api/history/:id 妯℃嫙鍒犻櫎
- GET  /uploads/:name    璁块棶涓婁紶鏂囦欢
"""

from __future__ import annotations

import http.server
import io
import json
import mimetypes
import os
import re
import socketserver
import base64
import hashlib
import time
import uuid
import sys
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse, urlencode
from typing import Any, Callable

# Ensure project root is importable for backend.* modules and config loading.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    from backend.services.vector_search import cosine_search as _cosine_search
except Exception:
    from services.vector_search import cosine_search as _cosine_search  # type: ignore

try:
    from backend.requirement_network import _clamp_unit_content as _clamp_unit_embed_text
except Exception:

    def _clamp_unit_embed_text(text: Any, max_len: int = 8000) -> str:
        s = str(text or "").strip()
        return s[:max_len] if len(s) > max_len else s


try:
    from backend.services.search_rerank import rerank_results as _rerank_results
except Exception:
    from services.search_rerank import rerank_results as _rerank_results  # type: ignore

try:
    from backend.services.normalize import (
        now_iso as _now_iso,
        parse_menu_from_filename as _parse_menu_from_filename,
        is_valid_filename as _is_valid_filename,
        extract_upload_stored_name as _extract_upload_stored_name,
        build_storage_filename as _build_storage_filename,
        style_table_rows_have_content as _style_table_rows_have_content,
        style_table_from_saved_analysis_style as _style_table_from_saved_analysis_style,
        align_step_expected_to_steps as _align_step_expected_to_steps,
        normalize_case as _normalize_case,
        normalize_case_priority as _normalize_case_priority,
        normalize_record as _normalize_record,
        merge_case_executor_from_payload as _merge_case_executor_from_payload,
    )
except Exception:
    from services.normalize import (  # type: ignore
        now_iso as _now_iso,
        parse_menu_from_filename as _parse_menu_from_filename,
        is_valid_filename as _is_valid_filename,
        extract_upload_stored_name as _extract_upload_stored_name,
        build_storage_filename as _build_storage_filename,
        style_table_rows_have_content as _style_table_rows_have_content,
        style_table_from_saved_analysis_style as _style_table_from_saved_analysis_style,
        align_step_expected_to_steps as _align_step_expected_to_steps,
        normalize_case as _normalize_case,
        normalize_case_priority as _normalize_case_priority,
        normalize_record as _normalize_record,
        merge_case_executor_from_payload as _merge_case_executor_from_payload,
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
    from backend.api.history_cases import (
        handle_get as _api_history_cases_get,
        handle_post as _api_history_cases_post,
        handle_put as _api_history_cases_put,
        handle_delete as _api_history_cases_delete,
    )
except Exception:
    try:
        from api.history_cases import (  # type: ignore
            handle_get as _api_history_cases_get,
            handle_post as _api_history_cases_post,
            handle_put as _api_history_cases_put,
            handle_delete as _api_history_cases_delete,
        )
    except Exception:
        _api_history_cases_get = None
        _api_history_cases_post = None
        _api_history_cases_put = None
        _api_history_cases_delete = None

try:
    from backend.api.systems import (
        handle_get as _api_systems_get,
        handle_post as _api_systems_post,
    )
except Exception:
    try:
        from api.systems import (  # type: ignore
            handle_get as _api_systems_get,
            handle_post as _api_systems_post,
        )
    except Exception:
        _api_systems_get = None
        _api_systems_post = None

try:
    from backend.api.auth_api import handle_get as _api_auth_get, handle_post as _api_auth_post
except Exception:
    try:
        from api.auth_api import handle_get as _api_auth_get, handle_post as _api_auth_post  # type: ignore
    except Exception:
        _api_auth_get = None
        _api_auth_post = None


try:
    from backend.llm_vision import try_visual_analysis_for_screenshot, try_extract_manual_from_screenshot
except Exception:
    try:
        from llm_vision import try_visual_analysis_for_screenshot, try_extract_manual_from_screenshot
    except Exception:

        def try_visual_analysis_for_screenshot(*_a: Any, **_k: Any) -> tuple[bool, str]:
            return False, "鏃犳硶鍔犺浇 llm_vision 妯″潡"

        def try_extract_manual_from_screenshot(*_a: Any, **_k: Any) -> tuple[bool, dict[str, Any] | str]:
            return False, "鏃犳硶鍔犺浇 llm_vision 妯″潡"


PORT = 5000
UPLOAD_DIR = PROJECT_ROOT / "uploads"
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_PATH = DATA_DIR / "history.json"
CASES_PATH = DATA_DIR / "cases.json"
SYSTEMS_PATH = DATA_DIR / "systems.json"

try:
    from backend.config.loader import load_config as _load_config
except Exception:
    try:
        from config.loader import load_config as _load_config  # type: ignore
    except Exception:
        _load_config = None

from backend.config.model_resolve import (
    case_generation_model,
    dashscope_compat_base_url,
    embedding_model,
    llm_vision_model,
    ocr_dashscope_model,
)


def _parse_json_body(handler: http.server.BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length > 0:
        raw = handler.rfile.read(content_length)
    else:
        # 鍏煎閮ㄥ垎瀹㈡埛绔湭姝ｇ‘璁剧疆 Content-Length 鐨勬儏鍐?
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
    if callable(_load_config):
        try:
            return _load_config()
        except Exception:
            return {}
    # fallback: 鏋佺鎯呭喌涓?loader 瀵煎叆澶辫触锛屼繚鎸佹棫琛屼负鍏煎
    legacy = PROJECT_ROOT / "config.local.json"
    if not legacy.exists():
        return {}
    try:
        return json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _json_row_matches_system_id(row: dict[str, Any], system_id: int) -> bool:
    v = row.get("system_id")
    if v is None or v == "":
        return False
    try:
        return int(v) == int(system_id)
    except (ValueError, TypeError):
        return False


def _read_history(system_id: int | None = None) -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        raw = HISTORY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            items = [x for x in data if isinstance(x, dict)]
            if system_id is not None:
                sid = int(system_id)
                items = [x for x in items if _json_row_matches_system_id(x, sid)]
            return items
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


# MySQL 鎸佷箙鍖栵細鑻?config.local.json 涓厤缃簡 mysql 涓斿彲杩炴帴锛屽垯鍒涘缓搴撹〃骞舵敼鐢?MySQL
_db_mysql = None
_storage = "file"

def _mysql_configured() -> bool:
    cfg = _read_config()
    mysql = cfg.get("mysql")
    if not isinstance(mysql, dict):
        return False
    if mysql.get("enabled") is False:
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
            raise RuntimeError(
                f"MySQL 已启用但初始化失败: {msg}。"
                "请检查库是否存在、账号权限，或临时在 config/local.yaml 设置 mysql.enabled: false 使用本地 JSON。"
            )
    elif mysql_cfg_present:
        raise RuntimeError(
            "MySQL 已在配置中启用但无法连接（服务未启动、端口/密码错误，或未安装 pymysql）。"
            "请启动 MySQL 并核对 config/local.yaml 的 mysql 段；若暂不使用数据库，请设置 mysql.enabled: false 使用本地 JSON。"
        )
    return _storage == "mysql"


def _read_history_one(history_id: int, system_id: int | None = None) -> dict[str, Any] | None:
    # Read one history record by id (prefer DB primary-key query).
    try:
        hid = int(history_id)
    except Exception:
        return None
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "read_history_by_id"):
        try:
            row = _db_mysql.read_history_by_id(hid, system_id=system_id)
            return row if isinstance(row, dict) else None
        except Exception:
            pass
    for x in _read_history(system_id=system_id):
        if not isinstance(x, dict):
            continue
        try:
            if int(x.get("id", -1)) == hid:
                return x
        except Exception:
            continue
    return None


def _next_history_id() -> int:
    if _use_mysql() and _db_mysql:
        return _db_mysql.next_history_id()
    return _next_id(_read_history())


def _next_case_id() -> int:
    if _use_mysql() and _db_mysql:
        return _db_mysql.next_case_id()
    return _next_id(_read_cases())


def _read_cases(system_id: int | None = None) -> list[dict[str, Any]]:
    if not CASES_PATH.exists():
        return []
    try:
        raw = CASES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            items = [x for x in data if isinstance(x, dict)]
            if system_id is not None:
                sid = int(system_id)
                items = [x for x in items if _json_row_matches_system_id(x, sid)]
            return items
    except Exception:
        return []
    return []


def _write_cases(items: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CASES_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 绯荤粺绠＄悊锛圝SON 鏂囦欢妯″紡 / MySQL 妯″紡缁熶竴鍏ュ彛锛?# ---------------------------------------------------------------------------

def _read_systems_file() -> list[dict[str, Any]]:
    if not SYSTEMS_PATH.exists():
        return [{"id": 1, "name": "默认系统", "description": "系统初始化时自动创建的默认系统", "created_at": "", "updated_at": ""}]
    try:
        raw = SYSTEMS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return [{"id": 1, "name": "默认系统", "description": "系统初始化时自动创建的默认系统", "created_at": "", "updated_at": ""}]


def _write_systems_file(items: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SYSTEMS_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_systems() -> list[dict[str, Any]]:
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "read_systems"):
        return _db_mysql.read_systems()
    return _read_systems_file()


def _read_system_by_id(system_id: int) -> dict[str, Any] | None:
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "read_system_by_id"):
        return _db_mysql.read_system_by_id(system_id)
    items = _read_systems_file()
    return next((s for s in items if int(s.get("id", -1)) == system_id), None)


def _create_system(name: str, description: str = "", created_at: str = "", updated_at: str = "") -> dict[str, Any] | None:
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "create_system"):
        return _db_mysql.create_system(name, description, created_at, updated_at)
    items = _read_systems_file()
    max_id = max((int(s.get("id", 0)) for s in items), default=0)
    new_sys = {"id": max_id + 1, "name": name, "description": description, "created_at": created_at, "updated_at": updated_at}
    items.append(new_sys)
    _write_systems_file(items)
    return new_sys


def _update_system(system_id: int, name: str | None = None, description: str | None = None, updated_at: str = "") -> dict[str, Any] | None:
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "update_system"):
        return _db_mysql.update_system(system_id, name=name, description=description, updated_at=updated_at)
    items = _read_systems_file()
    idx = next((i for i, s in enumerate(items) if int(s.get("id", -1)) == system_id), None)
    if idx is None:
        return None
    if name is not None:
        items[idx]["name"] = name
    if description is not None:
        items[idx]["description"] = description
    if updated_at:
        items[idx]["updated_at"] = updated_at
    _write_systems_file(items)
    return items[idx]


def _delete_system(system_id: int) -> bool:
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "delete_system"):
        return _db_mysql.delete_system(system_id)
    items = _read_systems_file()
    before = len(items)
    items = [s for s in items if int(s.get("id", -1)) != system_id]
    if len(items) == before:
        return False
    _write_systems_file(items)
    return True


# 鍚姩鏃跺皾璇曟寕杞?MySQL锛岃嫢閰嶇疆涓斿彲杩炴帴鍒欏垱寤?llm_case_system 鍙婅〃
_use_mysql()

try:
    _cfg_boot = _read_config()
    _ac_boot = _cfg_boot.get("auth") if isinstance(_cfg_boot.get("auth"), dict) else {}
    _mysql_ok = _use_mysql() and _db_mysql is not None
    _auth_on = bool(_ac_boot.get("enabled", True)) and _mysql_ok
    if _auth_on:
        print("[auth] 璁よ瘉宸插惎鐢細闄?config / login / register 澶栵紝/api/* 椤绘惡甯︽湁鏁?token")
    elif _mysql_ok and not bool(_ac_boot.get("enabled", True)):
        print("[auth] 璁よ瘉宸插叧闂細config 涓?auth.enabled 涓?false")
    else:
        print("[auth] 璁よ瘉鏈敓鏁堬細闇€ MySQL 杩炴帴鎴愬姛锛涜閰嶇疆 mysql 骞跺鍒?config/local.example.yaml 涓?config/local.yaml")
except Exception:
    pass


def _auth_cfg_dict() -> dict[str, bool]:
    c = _read_config()
    a = c.get("auth") if isinstance(c.get("auth"), dict) else {}
    mysql_on = _use_mysql() and _db_mysql is not None
    return {
        "enabled": bool(a.get("enabled", True)) and mysql_on,
        "require_login": bool(a.get("require_login", False)) and mysql_on,
    }


def _extract_session_token_for_gate(handler: Any, qs: dict[str, list[str]] | None = None) -> str:
    h = handler.headers.get("Authorization") or ""
    if isinstance(h, str) and h.lower().startswith("bearer "):
        return h[7:].strip()
    x = handler.headers.get("X-Session-Token") or ""
    if x:
        return str(x).strip()
    if qs:
        for k in ("access_token", "token"):
            v = (qs.get(k) or [None])[0]
            if v:
                return str(v).strip()
    return ""


def _auth_public_api(method: str, path: str) -> bool:
    p = path.rstrip("/") or "/"
    if p == "/api/auth/config":
        return True
    if method == "POST" and p in ("/api/auth/login", "/api/auth/register"):
        return True
    return False


def _api_path_requires_auth(method: str, path: str) -> bool:
    if not path.startswith("/api/"):
        return False
    if _auth_public_api(method, path):
        return False
    return True


def _auth_gate(handler: Any, method: str, path: str, qs: dict[str, list[str]] | None = None) -> bool:
    cfg = _auth_cfg_dict()
    # 璁よ瘉鍚敤鏃讹紝闄ょ櫧鍚嶅崟澶栧叏閮?/api/* 蹇呴』鎼哄甫鏈夋晥 token锛堜笉鍐嶄緷璧?require_login 寮€鍏筹級
    if not cfg["enabled"]:
        return True
    if not _api_path_requires_auth(method, path):
        return True
    tok = _extract_session_token_for_gate(handler, qs)
    if not tok or not _db_mysql or not hasattr(_db_mysql, "auth_validate_token"):
        handler._send_json(401, {"error": "请登录"})
        return False
    user = _db_mysql.auth_validate_token(tok)
    if not user:
        handler._send_json(401, {"error": "请登录"})
        return False
    handler._auth_user = user  # type: ignore[attr-defined]
    return True


def _respond_auth_me(handler: Any) -> None:
    u = getattr(handler, "_auth_user", None)
    if not u:
        handler._send_json(401, {"error": "请登录"})
        return
    handler._send_json(
        200,
        {
            "user": {
                "id": u["id"],
                "username": u["username"],
                "display_name": u["display_name"],
                "role_id": u.get("role_id"),
            },
            "permissions": u.get("permissions") or [],
        },
    )


def _auth_permission_codes(handler: Any) -> set[str]:
    user = getattr(handler, "_auth_user", None)
    perms = user.get("permissions") if isinstance(user, dict) else []
    return {str(x) for x in perms if x}


def _auth_has_permission(handler: Any, code: str) -> bool:
    perms = _auth_permission_codes(handler)
    return "*" in perms or code in perms


def _auth_require_any(handler: Any, codes: tuple[str, ...] | list[str]) -> bool:
    if any(_auth_has_permission(handler, code) for code in codes):
        return True
    handler._send_json(403, {"error": "娌℃湁鏉冮檺"})
    return False


# _normalize_case, _normalize_record, _parse_menu_from_filename, _is_valid_filename,
# _extract_upload_stored_name, _build_storage_filename, _style_table_rows_have_content,
# _style_table_from_saved_analysis_style 鈫?moved to backend/services/normalize.py



def _ensure_requirement_network_for_case_record(
    record: dict[str, Any],
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    if not (_use_mysql() and _db_mysql and hasattr(_db_mysql, "read_requirement_network_for_search")):
        return
    try:
        hid = int(record.get("id") or 0)
    except Exception:
        hid = 0
    if hid <= 0:
        return
    sid_raw = record.get("system_id")
    try:
        sid = int(sid_raw) if sid_raw is not None else None
    except Exception:
        sid = None

    def _emit(msg: str) -> None:
        if callable(emit):
            try:
                emit({"event": "log", "msg": msg, "history_id": hid})
            except Exception:
                pass

    try:
        try:
            existing = _db_mysql.read_requirement_network_for_search(history_id=hid, system_id=sid)
        except TypeError:
            existing = _db_mysql.read_requirement_network_for_search(history_id=hid)
    except Exception:
        existing = []

    built_at = str(record.get("vector_built_at") or "").strip()
    updated_marks = [
        str(record.get("updated_at") or "").strip(),
        str(record.get("analysis_generated_at") or "").strip(),
    ]
    latest_mark = max([x for x in updated_marks if x], default="")
    should_rebuild = not (isinstance(existing, list) and bool(existing))
    if not should_rebuild and built_at and latest_mark and latest_mark > built_at:
        should_rebuild = True
        _emit("检测到分析内容更新，自动重建需求网络以保证联动语义新鲜度")
    if not should_rebuild:
        return

    _emit("需求网络为空，自动补建当前记录的需求向量与联动语义")
    try:
        from backend.requirement_network import build_atomic_units_and_edges
        from backend.embeddings_service import embed_texts
        from backend.services.unit_content_clean import filter_units_and_edges
    except Exception:
        from requirement_network import build_atomic_units_and_edges  # type: ignore
        from embeddings_service import embed_texts  # type: ignore
        from services.unit_content_clean import filter_units_and_edges  # type: ignore

    r = _normalize_record(dict(record))

    def _stable_unit_key(prefix: str, raw: str) -> str:
        s = str(raw or "").strip() or "empty"
        return f"{prefix}:{hashlib.sha1(s.encode('utf-8')).hexdigest()[:10]}"

    def _is_related_text(a: str, b: str) -> bool:
        sa = str(a or "").strip()
        sb = str(b or "").strip()
        if not sa or not sb:
            return False
        if sa == sb:
            return True
        if len(sa) >= 2 and sa in sb:
            return True
        if len(sb) >= 2 and sb in sa:
            return True
        return False

    def _extract_record_signals(rec: dict[str, Any]) -> dict[str, Any]:
        menu_path = _breadcrumb_for_record(rec)
        actions: set[str] = set()
        fields: set[str] = set()
        results: set[str] = set()
        rows = rec.get("analysis_style_table")
        if isinstance(rows, list):
            for row in rows[:300]:
                if not isinstance(row, dict):
                    continue
                attr = str(row.get("attribute") or "").strip()
                el = str(row.get("element") or "").strip()
                req = str(row.get("requirement") or "").strip()
                txt = f"{el} {req}".strip()
                if not txt:
                    continue
                if ("按钮" in attr) or any(x in txt for x in ["提交", "保存", "删除", "新增", "查询", "导入", "导出", "确认", "取消", "审批"]):
                    actions.add(el or txt[:40])
                elif ("表格" in attr) or ("列表" in attr) or any(x in txt for x in ["表格", "列表", "结果"]):
                    results.add(el or txt[:40])
                else:
                    fields.add(el or txt[:40])

        ad = rec.get("analysis_data")
        if isinstance(ad, dict):
            cf = ad.get("current_function")
            if isinstance(cf, dict):
                for x in (cf.get("core_actions") if isinstance(cf.get("core_actions"), list) else []):
                    sx = str(x or "").strip()
                    if sx:
                        actions.add(sx)
                for x in (cf.get("key_fields") if isinstance(cf.get("key_fields"), list) else []):
                    sx = str(x or "").strip()
                    if sx:
                        fields.add(sx)
                for x in (cf.get("result_views") if isinstance(cf.get("result_views"), list) else []):
                    sx = str(x or "").strip()
                    if sx:
                        results.add(sx)
            for item in (ad.get("downstream_impacts") if isinstance(ad.get("downstream_impacts"), list) else [])[:80]:
                if not isinstance(item, dict):
                    continue
                sx = str(item.get("action") or "").strip()
                tx = str(item.get("target") or "").strip()
                if sx:
                    actions.add(sx)
                if tx:
                    results.add(tx)
            for item in (ad.get("upstream_dependencies") if isinstance(ad.get("upstream_dependencies"), list) else [])[:80]:
                if not isinstance(item, dict):
                    continue
                ox = str(item.get("data_object") or "").strip()
                if ox:
                    fields.add(ox)

        req_content = str(rec.get("analysis_content") or "").strip()
        req_key = _stable_unit_key("req_content", req_content[:2000]) if req_content else ""
        return {
            "menu_path": menu_path,
            "actions": list(actions)[:60],
            "fields": list(fields)[:80],
            "results": list(results)[:60],
            "req_key": req_key,
        }

    units, edges = build_atomic_units_and_edges(r)
    current_sig = _extract_record_signals(r)
    source_req_key = str(current_sig.get("req_key") or "").strip()
    cross_added = 0

    others = [_normalize_record(x) for x in _read_history(system_id=sid)] if sid is not None else []
    if sid is None:
        _emit("当前记录缺少 system_id，仅补建本记录需求单元，跳过跨页面联动以避免跨系统污染")
    for other in others:
        try:
            other_hid = int(other.get("id") or 0)
        except Exception:
            other_hid = 0
        if other_hid <= 0 or other_hid == hid:
            continue
        if cross_added >= 10:
            break
        other_sig = _extract_record_signals(other)
        other_fields = [str(x) for x in (other_sig.get("fields") or [])]
        other_results = [str(x) for x in (other_sig.get("results") or [])]
        other_targets = other_fields + other_results
        matched_action = ""
        matched_target = ""
        relation_type = "cross_page_trigger"
        for act in [str(x) for x in (current_sig.get("actions") or [])]:
            hit = next((t for t in other_targets if _is_related_text(act, t)), "")
            if hit:
                matched_action = act
                matched_target = hit
                break
        if not matched_action:
            acts = [str(x) for x in (current_sig.get("actions") or []) if str(x).strip()]
            tgts = [str(x) for x in other_targets if str(x).strip()]
            if acts and tgts:
                matched_action = acts[0]
                matched_target = tgts[0]
                relation_type = "cross_page_assumed"
            else:
                continue
        src_menu = str(current_sig.get("menu_path") or f"history:{hid}")
        tgt_menu = str(other_sig.get("menu_path") or f"history:{other_hid}")
        link_raw = f"{hid}|{other_hid}|{matched_action}|{matched_target}|{src_menu}|{tgt_menu}"
        cross_key = _stable_unit_key("cross_page", link_raw)
        cross_content = (
            f"跨页面联动：在[{src_menu}]执行动作[{matched_action}]后，"
            f"应在[{tgt_menu}]验证目标元素/结果[{matched_target}]的联动变化。"
        )
        units.append(
            {
                "unit_key": cross_key,
                "unit_type": "cross_page_link",
                "content": _clamp_unit_embed_text(cross_content),
                "metadata": {
                    "history_id": hid,
                    "source_history_id": hid,
                    "target_history_id": other_hid,
                    "source_menu": src_menu,
                    "target_menu": tgt_menu,
                    "matched_action": matched_action,
                    "matched_target": matched_target,
                    "relation_type": relation_type,
                },
            }
        )
        if source_req_key:
            edges.append(
                {
                    "from_unit_key": source_req_key,
                    "to_unit_key": cross_key,
                    "relation_type": relation_type,
                    "metadata": {"history_id": hid, "target_history_id": other_hid},
                }
            )
        target_req_key = str(other_sig.get("req_key") or "").strip()
        if target_req_key:
            edges.append(
                {
                    "from_unit_key": cross_key,
                    "to_unit_key": target_req_key,
                    "relation_type": "cross_page_dependency",
                    "metadata": {"history_id": hid, "target_history_id": other_hid},
                }
            )
        cross_added += 1

    units, edges = filter_units_and_edges(units, edges)
    embed_allow_types = {
        "requirement_rule",
        "interaction_rule",
        "data_upstream",
        "data_downstream",
        "data_logic_relation",
        "data_element",
        "cross_page_link",
        "vector_analysis_rule",
    }
    texts: list[str] = []
    unit_keys: list[str] = []
    for u in units:
        if not isinstance(u, dict):
            continue
        uk = str(u.get("unit_key") or "").strip()
        c = str(u.get("content") or "").strip()
        ut = str(u.get("unit_type") or "").strip()
        if not uk or not c:
            continue
        if ut and ut not in embed_allow_types:
            continue
        texts.append(_clamp_unit_embed_text(c))
        unit_keys.append(uk)
    embed_model = embedding_model(_read_config())
    embeddings_list, used_model = ([], embed_model)
    if texts:
        embeddings_list, used_model = embed_texts(texts, model_name=embed_model or None)
    embeddings: dict[str, list[float]] = {}
    for uk, vec in zip(unit_keys, embeddings_list):
        if isinstance(vec, list) and vec:
            embeddings[uk] = vec
    _db_mysql.write_requirement_network(
        hid,
        units=units,
        edges=edges,
        embeddings=embeddings,
        embedding_model=used_model or embed_model or "",
        system_id=sid,
    )
    try:
        if hasattr(_db_mysql, "update_history_vector_meta"):
            _db_mysql.update_history_vector_meta(
                history_id=hid,
                vector_built_at=_now_iso(),
                vector_build_summary=f"units={len(units)},edges={len(edges)},embeddings={len(embeddings)}",
            )
    except Exception:
        pass
    _emit(f"需求网络自动补建完成：units={len(units)}, edges={len(edges)}, embeddings={len(embeddings)}")


def _generate_cases_from_history(
    record: dict[str, Any],
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    record = _normalize_record(record)
    try:
        _ensure_requirement_network_for_case_record(record, emit=emit)
    except Exception as exc:
        if callable(emit):
            try:
                emit({"event": "log", "msg": f"需求网络自动补建失败，已降级继续生成：{exc}"})
            except Exception:
                pass
    reader = None
    if _use_mysql() and _db_mysql and hasattr(_db_mysql, "read_requirement_network_for_search"):
        reader = _db_mysql.read_requirement_network_for_search
    return _svc_generate_cases_from_history(
        record=record,
        normalize_record=_normalize_record,
        normalize_case=_normalize_case,
        now_iso=_now_iso,
        manual_from_legacy_fields_buttons=_manual_from_legacy_fields_buttons,
        legacy_buttons_fields_from_elements=_legacy_buttons_fields_from_elements,
        read_config=_read_config,
        get_llm_vision_runtime=_get_llm_vision_runtime,
        read_requirement_network_for_search=reader,
        emit=emit,
    )


_ZIP_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_ZIP_UPLOAD_BYTES = 100 * 1024 * 1024
_MAX_ZIP_IMAGE_MEMBERS = 300
_MAX_ONE_IMAGE_FROM_ZIP = 25 * 1024 * 1024


def _zip_inner_path_safe(raw: str) -> str | None:
    raw = raw.replace("\\", "/").strip()
    if not raw or raw.endswith("/"):
        return None
    parts = Path(raw).parts
    if ".." in parts:
        return None
    if any(p.startswith("__MACOSX") for p in parts):
        return None
    base = Path(raw).name
    if not base or base.startswith("."):
        return None
    if base in (".DS_Store", "Thumbs.db"):
        return None
    return raw


def _history_records_from_zip_bytes(
    file_content: bytes,
    upload_system_id: int | None,
) -> list[dict[str, Any]]:
    # Extract images from ZIP and create multiple history records.
    try:
        zf = zipfile.ZipFile(io.BytesIO(file_content), "r")
    except zipfile.BadZipFile as e:
        raise ValueError("不是有效的 ZIP 压缩包") from e

    members: list[zipfile.ZipInfo] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        inner = _zip_inner_path_safe(info.filename)
        if not inner:
            continue
        suf = Path(inner).suffix.lower()
        if suf not in _ZIP_IMAGE_EXTS:
            continue
        if int(getattr(info, "file_size", 0) or 0) > _MAX_ONE_IMAGE_FROM_ZIP:
            continue
        members.append(info)

    members.sort(key=lambda x: str(x.filename).replace("\\", "/").lower())
    if not members:
        raise ValueError("压缩包内未找到可用图片（支持 png/jpg/jpeg/webp）")

    if len(members) > _MAX_ZIP_IMAGE_MEMBERS:
        raise ValueError(f"压缩包内图片过多（最多 {_MAX_ZIP_IMAGE_MEMBERS} 张）")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    items = _read_history()
    out: list[dict[str, Any]] = []
    used_basenames: dict[str, int] = {}
    # 同一 ZIP 内需一次性分配起始 ID，避免批量写入时重复取到同一 next id。
    next_rid = _next_history_id()

    for info in members:
        inner = _zip_inner_path_safe(info.filename)
        if not inner:
            continue
        base_name = Path(inner).name
        if not _is_valid_filename(base_name):
            stem, ext = os.path.splitext(base_name)
            safe = f"{stem}_{abs(hash(inner)) % 100000}{ext}"
            if not _is_valid_filename(safe):
                continue
            display_name = safe
        else:
            display_name = base_name
            key = base_name
            if key in used_basenames:
                used_basenames[key] += 1
                stem, ext = os.path.splitext(base_name)
                display_name = f"{stem}_{used_basenames[key]}{ext}"
            else:
                used_basenames[key] = 0

        raw = zf.read(info)
        if len(raw) > _MAX_ONE_IMAGE_FROM_ZIP:
            continue

        stored_name = _build_storage_filename(display_name)
        file_path = UPLOAD_DIR / stored_name
        while file_path.exists():
            stored_name = _build_storage_filename(display_name)
            file_path = UPLOAD_DIR / stored_name
        with file_path.open("wb") as f:
            f.write(raw)

        file_url = f"/uploads/{stored_name}"
        system_name, menu_structure = _parse_menu_from_filename(display_name)
        rid = next_rid
        next_rid += 1
        record = {
            "id": rid,
            "file_name": display_name,
            "file_url": file_url,
            "system_name": system_name,
            "menu_structure": menu_structure,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "analysis": "",
            "system_id": upload_system_id,
        }

        out.append(record)

    if not out:
        raise ValueError("鏈兘浠庡帇缂╁寘涓В鍘嬪嚭鏈夋晥鍥剧墖")

    for r in reversed(out):
        items.insert(0, r)
    _write_history(items)
    return out


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
        return "寮圭獥"
    if page_type == "form":
        return "琛ㄥ崟"

    # Fallback: infer by common UI words
    t = "".join((ocr_text or "").split())
    if any(x in t for x in ["鍙栨秷", "纭畾", "鍏抽棴", "杩斿洖"]):
        return "寮圭獥"
    return "椤甸潰"


def _build_tested_items_from_ocr(record: dict[str, Any], ocr_text: str) -> tuple[list[dict[str, Any]], str]:
    container = _infer_container(record, ocr_text)
    t_raw = str(ocr_text or "")
    t = "".join(t_raw.split())
    tested_items: list[dict[str, Any]] = []

    def _push(title: str, direction: list[str]) -> None:
        if any(x.get("title") == title for x in tested_items):
            return
        tested_items.append({"title": title, "direction": "\n".join(direction)})

    field_hints = [
        (["??"], "??"),
        (["???", "??", "??"], "???"),
        (["??"], "??"),
        (["??", "???"], "??"),
        (["??"], "??"),
        (["??", "??"], "????"),
        (["??"], "??"),
        (["??"], "??"),
    ]
    for keys, name in field_hints:
        if any(k in t_raw or "".join(k.split()) in t for k in keys):
            _push(
                f"{container}?? - {name}",
                ["??/??/????", "?????", "?????????", "?????????"],
            )

    action_hints = [
        (["??", "??", "??"], "????"),
        (["??", "??", "??"], "????"),
        (["??"], "????"),
        (["??", "??", "??"], "????"),
        (["??", "??", "??"], "??"),
        (["??", "??"], "??"),
        (["??"], "??"),
    ]
    for keys, name in action_hints:
        if any(k in t_raw or "".join(k.split()) in t for k in keys):
            _push(
                f"{container}?? - {name}",
                ["?????????", "????????????", "???????????"],
            )

    if not tested_items:
        _push(
            f"{container}????",
            ["??????", "????????", "?????????"],
        )

    bullet_lines = []
    for it in tested_items[:12]:
        dir_text = str(it.get("direction") or "")
        bullet_lines.append(f"- {it.get('title')}\n  {dir_text.replace(chr(10), chr(10) + '  ')}")
    suffix = "\n\nOCR????????\n" + "\n".join(bullet_lines)
    return tested_items[:12], suffix


def _build_manual_draft_from_ocr(record: dict[str, Any], ocr_text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    container = _infer_container(record, ocr_text)
    t_raw = str(ocr_text or "")
    t_norm = "".join(t_raw.split())

    page_type = "list"
    if container == "??":
        page_type = "modal"
    elif container == "??":
        page_type = "form"

    field_defs: list[tuple[list[str], str, str, bool, int | str, int | str]] = [
        (["??"], "??", "text", True, 2, 20),
        (["???", "??", "??"], "???", "phone", True, 11, 11),
        (["??"], "??", "email", True, 5, 50),
        (["??", "???"], "??", "text", True, 3, 20),
        (["??"], "??", "text", True, 6, 20),
        (["??"], "??", "number", True, "", ""),
        (["??"], "??", "number", True, "", ""),
        (["??", "??"], "??", "text", False, "", 200),
    ]

    fields: list[dict[str, Any]] = []
    field_hints: list[dict[str, Any]] = []
    for keys, name, ftype, required, min_len, max_len in field_defs:
        if any(k in t_raw or "".join(k.split()) in t_norm for k in keys):
            hint = "??/??/??/????"
            fields.append(
                {
                    "name": name,
                    "type": ftype,
                    "required": required,
                    "queryable": False,
                    "validation": hint,
                    "min_len": min_len,
                    "max_len": max_len,
                    "options": [],
                    "hint": hint,
                }
            )
            field_hints.append({"name": name, "direction": hint})

    buttons: list[dict[str, Any]] = []

    def _push_btn(name: str, action: str, opens_modal: bool = False, requires_confirm: bool = False, matched_by: str = "") -> None:
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

    _push_btn("??", "open")
    _push_btn("??", "edit")
    action_defs: list[tuple[list[str], str, str, bool, bool]] = [
        (["??", "??", "??"], "??", "query", False, False),
        (["??", "??", "??"], "??", "create", True, False),
        (["??", "??", "??"], "??", "edit", True, False),
        (["??"], "??", "delete", False, True),
    ]
    for keys, name, action, opens_modal, requires_confirm in action_defs:
        hit = next((k for k in keys if k in t_raw or "".join(k.split()) in t_norm), "")
        if hit:
            _push_btn(name, action, opens_modal, requires_confirm, hit)

    page_elements: list[dict[str, Any]] = []
    for b in buttons:
        n = _normalize_page_element(
            {
                "name": b.get("name"),
                "element_type": "button",
                "ui_pattern": "button",
                "action": b.get("action"),
                "opens_modal": b.get("opens_modal"),
                "requires_confirm": b.get("requires_confirm"),
                "source": b.get("source") or "ocr",
                "source_text": b.get("source_text") or "",
            }
        )
        if n:
            page_elements.append(n)

    manual_draft = {
        "page_type": page_type,
        "buttons": buttons,
        "fields": fields,
        "page_elements": page_elements,
        "control_logic": "",
        "text_requirements": "",
    }
    return manual_draft, field_hints
def _merge_manual_draft(base: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    # Merge LLM-extracted manual draft into OCR-derived draft.
    out = dict(base if isinstance(base, dict) else {})
    base_buttons = out.get("buttons") if isinstance(out.get("buttons"), list) else []
    base_fields = out.get("fields") if isinstance(out.get("fields"), list) else []
    llm_buttons = llm.get("buttons") if isinstance(llm.get("buttons"), list) else []
    llm_fields = llm.get("fields") if isinstance(llm.get("fields"), list) else []

    def _name(v: Any) -> str:
        return v.get("name").strip() if isinstance(v, dict) and isinstance(v.get("name"), str) else ""

    # Buttons: prefer LLM extraction, then backfill missing OCR buttons.
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

    # 字段：按用户要求不自动生成，保持为空，后续由「数据需求补充」人工维护
    merged_fields: list[dict[str, Any]] = []

    # 淇濆簳鎸夐挳锛岄伩鍏嶇紪杈戝櫒鏃犳硶鎿嶄綔
    if not any(_name(x) == "鍙栨秷" for x in merged_buttons):
        merged_buttons.append({"name": "鍙栨秷", "action": "open", "opens_modal": False, "requires_confirm": False, "source": "default", "source_text": "淇濆簳鍔ㄤ綔"})
    if not any(_name(x) == "淇濆瓨" for x in merged_buttons):
        merged_buttons.append({"name": "淇濆瓨", "action": "edit", "opens_modal": False, "requires_confirm": False, "source": "default", "source_text": "淇濆簳鍔ㄤ綔"})

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
    # Return: enabled, api_key, base_url, model.
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
    ) or dashscope_compat_base_url(cfg)
    model = llm_vision_model(cfg)
    return enabled, api_key, base_url, model


def _get_llm_text_runtime(cfg: dict[str, Any]) -> tuple[bool, str, str, str]:
    # Resolve text-generation runtime from case_generation -> llm_vision -> ocr config.
    analysis_cfg = cfg.get("analysis") if isinstance(cfg.get("analysis"), dict) else {}
    case_cfg = analysis_cfg.get("case_generation") if isinstance(analysis_cfg.get("case_generation"), dict) else {}
    lv_cfg = analysis_cfg.get("llm_vision") if isinstance(analysis_cfg.get("llm_vision"), dict) else {}
    ocr_cfg = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
    ds_cfg = ocr_cfg.get("dashscope") if isinstance(ocr_cfg.get("dashscope"), dict) else {}

    enabled_raw = case_cfg.get("enabled")
    enabled = True if enabled_raw is None else bool(enabled_raw)

    api_key = ""
    if isinstance(case_cfg.get("api_key"), str) and case_cfg.get("api_key").strip():
        api_key = case_cfg.get("api_key").strip()
    elif isinstance(lv_cfg.get("api_key"), str) and lv_cfg.get("api_key").strip():
        api_key = lv_cfg.get("api_key").strip()
    elif isinstance(ds_cfg.get("api_key"), str) and ds_cfg.get("api_key").strip():
        api_key = ds_cfg.get("api_key").strip()
    else:
        api_key = os.getenv("DASHSCOPE_API_KEY") or ""

    base_url = ""
    if isinstance(case_cfg.get("base_url"), str) and case_cfg.get("base_url").strip():
        base_url = case_cfg.get("base_url").strip()
    elif isinstance(lv_cfg.get("base_url"), str) and lv_cfg.get("base_url").strip():
        base_url = lv_cfg.get("base_url").strip()
    elif isinstance(ds_cfg.get("base_url"), str) and ds_cfg.get("base_url").strip():
        base_url = ds_cfg.get("base_url").strip()
    else:
        base_url = dashscope_compat_base_url(cfg)

    model = case_generation_model(cfg)
    # Guard: realtime models are not stable for this sync text completion path.
    if isinstance(model, str) and "realtime" in model.lower():
        fallback_model = llm_vision_model(cfg)
        if isinstance(fallback_model, str) and fallback_model.strip() and "realtime" not in fallback_model.lower():
            model = fallback_model.strip()
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


def _analysis_style_table_from_ocr(ocr_excerpt: str, ok: bool, ocr_err: str) -> list[dict[str, Any]]:
    # Split OCR excerpt into style table rows for UI display.
    rows: list[dict[str, Any]] = []
    if ok:
        text = (ocr_excerpt or "").strip()
        if text:
            for line in text.splitlines():
                s = line.strip()
                if s:
                    rows.append({"element": s, "attribute": "其他", "requirement": ""})
            if not rows:
                rows.append({"element": text, "attribute": "其他", "requirement": ""})
    else:
        err = str(ocr_err or "").strip()
        if err:
            rows.append({"element": err[:2048], "attribute": "其他", "requirement": ""})
    return rows


def _generate_requirement_library_for_record(record: dict[str, Any], *, stage: str = "all") -> dict[str, Any]:
    # Build requirement library content for one history record.
    found = _normalize_record(record)
    stage_clean = str(stage or "all").strip().lower()
    if stage_clean not in {"all", "style", "rest"}:
        stage_clean = "all"
    want_style = stage_clean in {"all", "style"}
    want_rest = stage_clean in {"all", "rest"}

    # Breadcrumb/menu-driven metadata
    breadcrumb = _breadcrumb_for_record(found)
    file_name = str(found.get("file_name") or "").strip()

    # 1) style analysis (OCR): generate first, then prefer edited style result.
    analysis_style = str(found.get("analysis_style") or "").strip()
    existing_table = found.get("analysis_style_table")
    analysis_style_table = existing_table if isinstance(existing_table, list) else []

    ok = False
    ocr_excerpt = ""
    provider = "saved"
    if want_style or not _style_table_rows_have_content(analysis_style_table):
        ok, provider, ocr_text_or_err = _ocr_extract_text(found)
        ocr_text = ocr_text_or_err if ok else ""
        if not isinstance(ocr_text, str):
            ocr_text = str(ocr_text or "")
        ocr_excerpt = ocr_text.strip()
        if len(ocr_excerpt) > 6000:
            ocr_excerpt = ocr_excerpt[:6000] + "\n...[OCR 鎽樿鎴柇]"
        if ok:
            analysis_style = f"OCR识别原文（来源: {provider}，摘要）:\n{ocr_excerpt}".strip()
        else:
            analysis_style = f"OCR识别失败：{ocr_text_or_err}".strip()
        analysis_style_table = _analysis_style_table_from_ocr(ocr_excerpt, ok, ocr_text_or_err if not ok else "")
    else:
        rows_preview = []
        for row in analysis_style_table[:120]:
            if not isinstance(row, dict):
                continue
            el = str(row.get("element") or "").strip()
            req = str(row.get("requirement") or "").strip()
            if el:
                rows_preview.append(el)
            if req:
                rows_preview.append(req)
        ocr_excerpt = "\n".join(rows_preview)[:6000].strip()

    # 从样式表推断页面元素（替代手动补录）
    buttons_set: set[str] = set()
    fields_set: set[str] = set()
    tables_set: set[str] = set()
    for row in analysis_style_table[:240]:
        if not isinstance(row, dict):
            continue
        attr = str(row.get("attribute") or "其他").strip()
        el = str(row.get("element") or "").strip()
        req = str(row.get("requirement") or "").strip()
        text = f"{el} {req}".strip()
        if not text:
            continue
        is_button = ("按钮" in attr) or any(k in text for k in ["提交", "保存", "删除", "新增", "查询", "导入", "导出", "确认", "取消"])
        is_table = ("表格" in attr) or ("列表" in attr) or any(k in text for k in ["表格", "列表", "数据网格"])
        is_field = ("表单" in attr) or ("筛选" in attr) or ("文本" in attr) or any(k in text for k in ["名称", "编号", "时间", "状态", "类型", "关键字", "输入"])
        if is_button:
            buttons_set.add(el or text[:40])
        elif is_table:
            tables_set.add(el or text[:40])
        elif is_field:
            fields_set.add(el or text[:40])

    button_names = [x for x in list(buttons_set) if x][:30]
    field_names = [x for x in list(fields_set) if x][:30]
    table_names = [x for x in list(tables_set) if x][:30]
    page_type = "list" if table_names else ("form" if field_names else "unknown")

    upstream_dependencies: list[dict[str, Any]] = []
    for fn in field_names[:30]:
        upstream_dependencies.append(
            {
                "source": "上游输入/主数据",
                "data_object": fn,
                "trigger": "页面加载或查询提交时读取",
                "rule": "用于筛选、校验或回显",
            }
        )

    downstream_impacts: list[dict[str, Any]] = []
    for bn in button_names[:30]:
        downstream_impacts.append(
            {
                "target": "下游业务处理/状态更新",
                "action": bn,
                "impact": "触发写入、审批流转或结果反馈",
            }
        )

    data_logic_relations: list[dict[str, Any]] = []
    for fn in field_names[:30]:
        data_logic_relations.append(
            {
                "from": f"输入字段:{fn}",
                "to": "业务规则引擎",
                "relation": "校验/过滤",
                "detail": "输入值参与条件判断与数据过滤",
            }
        )
    for bn in button_names[:30]:
        data_logic_relations.append(
            {
                "from": f"操作按钮:{bn}",
                "to": "业务处理结果",
                "relation": "触发",
                "detail": "触发后更新状态并反馈到页面",
            }
        )
    for tn in table_names[:30]:
        data_logic_relations.append(
            {
                "from": "查询条件集合",
                "to": f"结果集:{tn}",
                "relation": "决定展示范围",
                "detail": "按筛选条件返回并分页展示数据",
            }
        )

    upstream_lines = [
        f"- 来源={x.get('source') or ''}；数据对象={x.get('data_object') or ''}；触发={x.get('trigger') or ''}；规则={x.get('rule') or ''}"
        for x in upstream_dependencies[:20]
    ]
    downstream_lines = [
        f"- 目标={x.get('target') or ''}；动作={x.get('action') or ''}；影响={x.get('impact') or ''}"
        for x in downstream_impacts[:20]
    ]
    relation_lines = [
        f"- {x.get('from') or ''} -> {x.get('to') or ''}（{x.get('relation') or ''}）：{x.get('detail') or ''}"
        for x in data_logic_relations[:40]
    ]
    analysis_data = (
        "【当前功能】\n"
        + f"- 截图: {file_name or '未知'}\n"
        + f"- 菜单路径: {breadcrumb or '未知'}\n"
        + f"- 页面类型: {page_type or 'unknown'}\n"
        + f"- 核心动作: {button_names[:20]}\n"
        + f"- 关键字段: {field_names[:30]}\n"
        + f"- 结果视图: {table_names[:20]}\n\n"
        + "【上游数据依赖】\n"
        + ("\n".join(upstream_lines) if upstream_lines else "- 暂无（建议补录页面字段或 OCR 识别文本）")
        + "\n\n【下游影响】\n"
        + ("\n".join(downstream_lines) if downstream_lines else "- 暂无（建议补录按钮动作与业务结果）")
        + "\n\n【数据逻辑关系】\n"
        + ("\n".join(relation_lines) if relation_lines else "- 暂无（建议补录字段、按钮与规则）")
        + "\n\n【OCR证据】\n"
        + f"- OCR来源: {provider if ok else 'none'}\n"
        + f"- OCR摘要: {(ocr_excerpt[:800] + '...') if len(ocr_excerpt) > 800 else ocr_excerpt}"
    )

    # 3) 交互分析：基于菜单 + OCR 样式元素，不再依赖手动补录。
    interaction = _build_analysis(found)
    if button_names or field_names or table_names:
        interaction = (
            interaction.strip()
            + "\n\n【OCR元素交互概览】\n"
            + f"- 按钮动作: {button_names[:20] or ['（待确认）']}\n"
            + f"- 输入/筛选: {field_names[:20] or ['（待确认）']}\n"
            + f"- 列表/结果视图: {table_names[:20] or ['（待确认）']}"
        )
    analysis_interaction = interaction.strip()

    # 2) 闇€姹傚唴瀹瑰垎鏋愶紙浠呭熀浜?OCR/鑿滃崟涓婁笅鏂囷級
    analysis_content = ""
    style_lines: list[str] = []
    for row in analysis_style_table[:80]:
        if not isinstance(row, dict):
            continue
        el = str(row.get("element") or "").strip()
        attr = str(row.get("attribute") or "其他").strip() or "其他"
        req = str(row.get("requirement") or "").strip()
        if el or req:
            line = f"- [{attr}] {el or '（未识别元素名）'}"
            if req:
                line += f"；补充：{req}"
            style_lines.append(line)

    style_block = "\n".join(style_lines[:60]).strip() or "（暂无可结构化 OCR 元素，使用 OCR 原文摘要推断）"
    cfg = _read_config()
    llm_enabled, api_key, base_url, model = _get_llm_text_runtime(cfg)
    if want_rest and llm_enabled and api_key:
        user_prompt = (
            "请基于当前截图的 OCR 结果，输出《系统需求分析库-需求内容分析》（中文、结构化）。\n\n"
            + f"- 菜单路径: {breadcrumb or '未知'}\n"
            + f"- 页面类型: {page_type or '未知'}\n"
            + f"- 截图文件: {file_name or '未知'}\n\n"
            + "【OCR结构化元素】\n"
            + f"{style_block}\n\n"
            + "【OCR原文摘要】\n"
            + f"{ocr_excerpt or '（暂无）'}\n\n"
            + "输出要求：\n"
            + "1) 分章节：业务目标、业务范围、关键规则、字段/按钮约束、验收口径、异常口径、关键验证点。\n"
            + "2) 仅依据 OCR 信息推断，不能确认的内容标注“待确认”。\n"
            + "3) 用可执行、可验证的需求语句表达。\n"
            + "4) 不输出 JSON。"
        )
        system_prompt = "你是资深业务需求与测试分析专家，擅长从界面 OCR 证据提炼需求。"
        analysis_content = _dashscope_text_completion(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    elif want_rest:
        inferred_goals = []
        if breadcrumb:
            inferred_goals.append(f"- 目标功能路径: {breadcrumb}")
        if page_type:
            inferred_goals.append(f"- 页面形态: {page_type}")
        if button_names:
            inferred_goals.append(f"- 关键动作: {button_names[:12]}")
        if field_names:
            inferred_goals.append(f"- 关键字段: {field_names[:16]}")
        if table_names:
            inferred_goals.append(f"- 结果视图: {table_names[:8]}")
        if not inferred_goals:
            inferred_goals.append("- OCR识别信息有限，建议补充更清晰截图后重试。")
        ocr_req_points = style_lines[:24] if style_lines else [f"- OCR摘要: {ocr_excerpt[:500] or '（暂无）'}"]
        analysis_content = (
            "【业务目标】\n"
            + "\n".join(inferred_goals)
            + "\n\n【OCR推断需求点】\n"
            + "\n".join(ocr_req_points)
            + "\n\n【验收与异常口径】\n"
            + "- 验收口径：页面关键动作可完成，关键字段校验生效，结果视图反馈一致。\n"
            + "- 异常口径：非法输入、空值、越界或重复触发应有明确提示与拦截。\n"
            + "- 待确认：涉及业务策略/权限细则时，以产品规则为准。"
        )
    else:
        analysis_content = str(found.get("analysis_content") or "")
        analysis_interaction = str(found.get("analysis_interaction") or "")
        analysis_data = found.get("analysis_data")

    return {
        "analysis_style": analysis_style,
        "analysis_style_table": analysis_style_table,
        "analysis_content": analysis_content,
        "analysis_interaction": analysis_interaction,
        "analysis_data": analysis_data,
    }


def _normalize_vector_build_output(text: str) -> str:
    """统一章节名，兼容旧版 LLM 输出。"""
    t = str(text or "").strip()
    if not t:
        return t
    return t.replace("【可检索业务规则句】", "【业务检索句】")


def _fallback_vector_build_document(
    page_for_rule: str,
    menu: str,
    style_rows: list[Any],
    data_block: str,
) -> str:
    """无 LLM 时的向量建库文本兜底，结构与「业务检索句」模板一致，便于入库与检索。"""
    p = page_for_rule or "当前页面"
    m = menu or p
    db_hint = (data_block or "").strip().replace("\r\n", "\n")
    if len(db_hint) > 800:
        db_hint = db_hint[:800] + "…"

    intro = (
        f"当前功能旨在围绕「{p}」提供与菜单路径「{m}」一致的界面能力，包括统计数据展示及可能的导出下载；"
        "数据与列表范围应限制在当前登录用户权限可见范围内（待业务确认）。"
        "若界面含多列统计，宜支持按科目或类别维度汇总，并提供合计行或汇总值供核对；"
        "宜展示或记录统计生成时间以保证时效性与可追溯性（待确认）。"
    )
    upstream = (
        "上游输入：\n"
        "- 用户登录信息：用于获取当前用户所属组织、考点或数据范围（待业务确认）\n"
        "- 主数据/配置：科目、类别、枚举等配置数据（表名与字段待结合库表确认）\n"
        "- 业务事实数据：列表与统计所依赖的明细或汇总数据来源（待确认）\n"
    )
    if db_hint and db_hint != "（暂无）":
        upstream += f"- 本记录已保存的数据分析摘录：{db_hint[:400]}{'…' if len(db_hint) > 400 else ''}\n"

    core = (
        "核心处理逻辑：\n"
        "- 权限过滤：按用户所属考点或角色隔离数据，避免跨范围查看（待确认）\n"
        "- 统计计算：按界面可见维度聚合，并计算合计或汇总（待确认）\n"
        "- 时间生成：统计或导出时可附带当前系统时间，格式由业务约定（待确认）\n"
    )
    downstream = (
        "下游输出影响：\n"
        "- 界面展示：在当前页面渲染考点/科目/人数等与素材一致的表格或列表（待确认）\n"
        "- 文件下载：若含导出，则文件内容应与当前页面展示一致（待确认）\n"
        "- 数据核对：合计与明细供用户或管理员校验（待确认）\n"
    )

    rules: list[str] = [
        f"页面={p}；操作=页面加载；条件=当前登录用户；结果=展示与本页权限相关的考点或业务上下文（待确认）",
        f"页面={p}；操作=数据展示；条件=列表有数据；结果=按列展示各维度统计或明细（待确认）",
        f"页面={p}；操作=合计计算；条件=各行列数据齐全；结果=展示申请或人数类合计值（待确认）",
        f"页面={p}；操作=时间显示；条件=生成统计或报表；结果=展示或记录统计生成时间（待确认）",
        f"页面={p}；操作=数据权限；条件=用户考点或组织归属；结果=仅展示当前用户权限范围内数据（待确认）",
        f"页面={p}；操作=下载报表；触发=点击导出或下载；结果=生成与当前页面一致的文件（待确认）",
        f"页面={p}；操作=字段校验；条件=人数类字段；结果=数值应大于等于零（待确认）",
        f"页面={p}；操作=空数据展示；条件=无业务记录；结果=显示零、横杠或空状态提示（待确认）",
        f"页面={p}；操作=权限异常；条件=用户未关联考点或角色；结果=提示无权限或展示未知占位（待确认）",
        f"页面={p}；操作=数据一致性；条件=与后台查询；结果=页面与底层数据一致（待确认）",
        f"页面={p}；操作=刷新页面；触发=重新加载；结果=统计时间与数据刷新为最新（待确认）",
        f"页面={p}；操作=跨考点隔离；条件=不同考点账号；结果=不同账号可见考点代码与名称不同（待确认）",
        f"页面={p}；操作=菜单入口；路径={m}；结果=从菜单进入本统计或列表页（待确认）",
    ]
    for row in style_rows[:12]:
        if not isinstance(row, dict):
            continue
        el = str(row.get("element") or "").strip()
        attr = str(row.get("attribute") or "").strip() or "其他"
        if not el:
            continue
        rules.append(
            f"页面={p}；操作=界面元素；条件=元素类型为{attr}；结果=展示或交互「{el[:80]}」"
        )

    body = (
        "【需求向量构建分析结果】\n\n"
        f"{intro}\n\n"
        f"{upstream}\n"
        f"{core}\n"
        f"{downstream}\n\n"
        "【业务检索句】\n"
        + "\n".join(rules)
    )
    return _normalize_vector_build_output(body)


def _build_vector_analysis_text_for_record(record: dict[str, Any]) -> str:
    # Build vector-analysis text for one record.
    rec = _normalize_record(dict(record))
    file_name = str(rec.get("file_name") or "").strip()
    breadcrumb = _breadcrumb_for_record(rec)
    style_rows = rec.get("analysis_style_table") if isinstance(rec.get("analysis_style_table"), list) else []
    style_lines: list[str] = []
    for row in style_rows[:80]:
        if not isinstance(row, dict):
            continue
        el = str(row.get("element") or "").strip()
        attr = str(row.get("attribute") or "其他").strip() or "其他"
        req = str(row.get("requirement") or "").strip()
        if el or req:
            style_lines.append(f"- [{attr}] {el}" + (f"；补充：{req}" if req else ""))

    style_fallback = str(rec.get("analysis_style") or "").strip()
    content_text = str(rec.get("analysis_content") or "").strip()
    interaction_text = str(rec.get("analysis_interaction") or "").strip()
    data_text = rec.get("analysis_data")
    if isinstance(data_text, str):
        data_block = data_text.strip()
    elif isinstance(data_text, (dict, list)):
        data_block = json.dumps(data_text, ensure_ascii=False)
    else:
        data_block = ""

    source_text = (
        f"截图文件: {file_name}\n"
        f"菜单路径: {breadcrumb}\n\n"
        f"【系统元素识别】\n{chr(10).join(style_lines) if style_lines else (style_fallback or '（暂无）')}\n\n"
        f"【需求内容分析】\n{content_text or '（暂无）'}\n\n"
        f"【交互分析】\n{interaction_text or '（暂无）'}\n\n"
        f"【数据分析】\n{data_block or '（暂无）'}\n"
    )

    cfg = _read_config()
    llm_enabled, api_key, base_url, model = _get_llm_text_runtime(cfg)
    if llm_enabled and api_key:
        user_prompt = (
            "请基于以下信息输出《需求向量构建分析结果》（中文纯文本，用于需求向量库入库、拆句与语义检索）。\n"
            "全文结构必须严格按顺序包含下列块（标题单独成行，标点与示例一致）：\n"
            "A) 首行固定为：【需求向量构建分析结果】\n"
            "B) 空一行后写一段「当前功能旨在……」开篇说明（约 3–8 句）：概括业务目的、统计/可视化/下载、"
            "用户仅能查看权限范围内数据（如考点维度）、按科目或类别统计申请人数与总人数、合计值核对、"
            "统计生成时间可追溯等；须结合下方素材写实，缺失处写「待确认」。\n"
            "C) 空一行后写「上游输入：」单独一行，下列至少 3 条子项，均以「- 」开头；可写用户登录与考点归属、"
            "科目/配置数据来源（如能推断可写表名如 subject_info 及关键筛选条件）、业务事实表（如 score_review 等，"
            "素材未写明则标「待确认」）。\n"
            "D) 「核心处理逻辑：」单独一行，下列至少 3 条「- 」子项：权限过滤与考点隔离、按科目维度聚合与合计、"
            "统计时间格式（如 YYYY 年 M 月 D 日）等。\n"
            "E) 「下游输出影响：」单独一行，下列至少 3 条「- 」子项：界面表格/列表展示、导出文件与页面一致、"
            "合计与明细供核对等。\n"
            "F) 空一行后写「【业务检索句】」单独一行；以下每一行一条检索句，无空行、无序号、无 Markdown。\n"
            "   每条必须为同一类模板，分号一律使用中文「；」，且每条须同时包含字段：页面=、操作=、条件=、结果=。\n"
            "   可按需在同一条中追加：触发=、路径=、目标=、场景=（均用「；」分隔）。\n"
            "   「页面=」名称须与菜单/截图主题一致（如 报名人数统计）。至少输出 20 条，尽量覆盖："
            "页面加载、列表展示、合计、统计时间展示、权限与考点隔离、下载/导出、字段非负校验、空数据、"
            "权限异常、数据一致性、排序、刷新、只读字段、科目/表来源、跨账号考点差异、合计校验、时间追溯、"
            "下载失败提示、服务端校验、菜单路径入口、可视化展示、汇总核对、时效性等。\n"
            "G) 不输出 JSON。\n\n"
            + source_text
        )
        system_prompt = (
            "你是资深系统分析师兼测试需求分析专家。「【业务检索句】」中每一条必须是完整的「页面=…；操作=…；条件=…；结果=…」句式，"
            "以便程序整行写入需求网络向量单元并与检索联动；禁止用英文分号替代中文分号。"
        )
        out = _dashscope_text_completion(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if isinstance(out, str) and out.strip() and not out.strip().startswith("LLM 请求失败"):
            return _normalize_vector_build_output(out.strip())

    menu = breadcrumb or file_name or "未知"
    page_label = menu
    if " / " in page_label:
        page_label = page_label.rsplit(" / ", 1)[-1].strip() or page_label
    elif "/" in page_label and "://" not in page_label:
        page_label = page_label.rsplit("/", 1)[-1].strip() or page_label
    file_stem = file_name
    if "." in file_stem:
        file_stem = file_stem.rsplit(".", 1)[0]
    page_for_rule = page_label or file_stem or "未知"

    return _fallback_vector_build_document(page_for_rule, menu, style_rows, data_block)


def _build_case_generation_analysis_text_for_record(record: dict[str, Any]) -> str:
    rec = _normalize_record(dict(record))
    file_name = str(rec.get("file_name") or "").strip() or "unknown"
    breadcrumb = _breadcrumb_for_record(rec)

    style_rows = rec.get("analysis_style_table") if isinstance(rec.get("analysis_style_table"), list) else []
    style_lines: list[str] = []
    for row in style_rows[:40]:
        if not isinstance(row, dict):
            continue
        element_name = str(row.get("element") or "").strip()
        attribute = str(row.get("attribute") or "").strip() or "attribute"
        requirement = str(row.get("requirement") or "").strip()
        if not any([element_name, attribute, requirement]):
            continue
        line = f"- {element_name or 'unnamed-element'}"
        if attribute:
            line += f" | attr: {attribute}"
        if requirement:
            line += f" | requirement: {requirement}"
        style_lines.append(line)

    style_text = "\n".join(style_lines) if style_lines else str(rec.get("analysis_style") or "").strip()
    content_text = str(rec.get("analysis_content") or "").strip()
    interaction_text = str(rec.get("analysis_interaction") or "").strip()
    data_value = rec.get("analysis_data")
    if isinstance(data_value, str):
        data_text = data_value.strip()
    elif isinstance(data_value, (dict, list)):
        data_text = json.dumps(data_value, ensure_ascii=False, indent=2)
    else:
        data_text = ""

    source_text = (
        f"source_file: {file_name}\n"
        f"breadcrumb: {breadcrumb or 'unknown'}\n\n"
        f"style:\n{style_text or 'n/a'}\n\n"
        f"content:\n{content_text or 'n/a'}\n\n"
        f"interaction:\n{interaction_text or 'n/a'}\n\n"
        f"data:\n{data_text or 'n/a'}\n"
    )

    cfg = _read_config()
    llm_enabled, api_key, base_url, model = _get_llm_text_runtime(cfg)
    if llm_enabled and api_key:
        user_prompt = (
            "Based on the following page analysis, output concise test-analysis text for case generation.\n"
            "Need: key features, critical fields/buttons, normal/abnormal/boundary flows, and cross-page dependencies.\n\n"
            f"{source_text}"
        )
        system_prompt = (
            "You are a senior QA analyst. Return practical, concise analysis text that is ready for test-case generation."
        )
        out = _dashscope_text_completion(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if isinstance(out, str) and out.strip() and not out.strip().startswith("LLM "):
            return out.strip()

    page_name = breadcrumb or file_name or "unknown-page"
    field_lines = style_lines[:24] or ["- no field extracted; supplement from page semantics."]
    return (
        "Page Test Analysis\n"
        f"- page: {page_name}\n"
        "- Build cases from flow, validation, interaction, and data-linkage dimensions.\n\n"
        "Content\n"
        f"- content: {content_text or 'not provided'}\n"
        f"- interaction: {interaction_text or 'not provided'}\n\n"
        "Fields\n"
        + "\n".join(field_lines)
        + "\n\nData\n"
        + f"- data: {data_text or 'not provided'}\n"
    )

def _ocr_local_tesseract(image_path: Path, lang: str, tesseract_cmd: str | None = None) -> tuple[bool, str]:
    # Local OCR via pytesseract (zero-token option).
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
    # NetEase Youdao OCR API call.
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
    # DashScope OpenAI-compatible OCR call with data URL payload.
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
                    {"type": "text", "text": "Please extract text from the image only; do not add explanation."},
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
    # Returns: (ok, provider, text_or_error).
    # provider: tesseract | dashscope
    record = _normalize_record(record)
    stored_name = _extract_upload_stored_name(record.get("file_url"))
    if not stored_name:
        # 兼容旧数据：file_url 为空时退回 file_name 作为落盘名
        file_name = record.get("file_name")
        stored_name = str(file_name or "").strip() if isinstance(file_name, str) else ""
    if not stored_name:
        return False, "none", "Missing file_url/file_name"
    image_path = UPLOAD_DIR / stored_name
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
    base_url = (
        ds_cfg.get("base_url")
        if isinstance(ds_cfg.get("base_url"), str) and str(ds_cfg.get("base_url") or "").strip()
        else None
    ) or dashscope_compat_base_url(cfg)
    model = (
        ds_cfg.get("model")
        if isinstance(ds_cfg.get("model"), str) and str(ds_cfg.get("model") or "").strip()
        else ocr_dashscope_model(cfg)
    )
    if provider in ["auto", "dashscope"] and api_key:
        ok, text = _ocr_dashscope(image_path, api_key, base_url, model)
        # 对外展示：DashScope 为接入名，实际为通义千问等视觉模型（与配置 ocr.dashscope.model 一致）
        prov_label = f"通义千问 OCR（DashScope，{model}）" if model else "通义千问 OCR（DashScope）"
        if ok:
            return True, prov_label, text
        return False, prov_label, text

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

        if callable(_api_auth_get):
            if _api_auth_get(
                self,
                path=path,
                deps={
                    "read_config": _read_config,
                    "use_mysql": _use_mysql,
                    "db_mysql": _db_mysql,
                },
            ):
                return
        if not _auth_gate(self, "GET", path, qs):
            return

        path_norm = path.rstrip("/") or "/"
        if path_norm == "/api/auth/me":
            _respond_auth_me(self)
            return

        if callable(_api_systems_get):
            handled = _api_systems_get(
                self,
                path=path,
                deps={
                    "read_systems": _read_systems,
                    "read_system_by_id": _read_system_by_id,
                },
            )
            if handled:
                return

        if callable(_api_history_cases_get):
            handled = _api_history_cases_get(
                self,
                path=path,
                qs=qs,
                deps={
                    "read_history": _read_history,
                    "write_history": _write_history,
                    "normalize_record": _normalize_record,
                    "read_cases": _read_cases,
                    "normalize_case": _normalize_case,
                },
            )
            if handled:
                return

        if path.startswith("/api/ocr/manual/"):
            rest = path[len("/api/ocr/manual/") :].strip("/")
            parts = [p for p in rest.split("/") if p]
            if len(parts) != 1:
                self._send_json(400, {"error": "Invalid path"})
                return
            try:
                rid = int(parts[0])
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            items = _read_history()
            found = next((x for x in items if int(x.get("id", -1)) == rid), None)
            if not found:
                self._send_json(404, {"error": "Not found"})
                return
            found = _normalize_record(found)

            ok, provider, ocr_text_or_err = _ocr_extract_text(found)
            if not ok:
                self._send_json(502, {"error": f"OCR failed: {ocr_text_or_err}", "provider": provider})
                return
            ocr_text = str(ocr_text_or_err or "")
            manual_draft, field_hints = _build_manual_draft_from_ocr(found, ocr_text)

            refs = _extract_ocr_references(ocr_text)
            if not isinstance(manual_draft.get("ocr_refs"), dict):
                manual_draft["ocr_refs"] = refs
            else:
                merged_refs = dict(manual_draft.get("ocr_refs") or {})
                if not isinstance(merged_refs.get("button_candidates"), list):
                    merged_refs["button_candidates"] = refs.get("button_candidates") or []
                if not isinstance(merged_refs.get("field_candidates"), list):
                    merged_refs["field_candidates"] = refs.get("field_candidates") or []
                if not isinstance(merged_refs.get("ocr_raw_text"), str):
                    merged_refs["ocr_raw_text"] = refs.get("ocr_raw_text") or ""
                manual_draft["ocr_refs"] = merged_refs
            manual_draft["ocr_raw_text"] = ocr_text

            cfg = _read_config()
            enabled, api_key, base_url, model = _get_llm_vision_runtime(cfg)
            llm_used = False
            llm_status = "skip"
            if enabled and api_key:
                image_name = found.get("file_name") if isinstance(found.get("file_name"), str) else ""
                image_path = UPLOAD_DIR / image_name if image_name else None
                if image_path and image_path.exists():
                    breadcrumb = _breadcrumb_for_record(found)
                    excerpt = ocr_text.strip()
                    if len(excerpt) > 2200:
                        excerpt = excerpt[:2200] + "\n...(OCR 鎽樿鎴柇)"
                    ok_llm, llm_data_or_err = try_extract_manual_from_screenshot(
                        image_path=image_path,
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                        breadcrumb=breadcrumb,
                        file_name=image_name,
                        ocr_excerpt=excerpt,
                    )
                    if ok_llm and isinstance(llm_data_or_err, dict):
                        manual_draft = _merge_manual_draft(manual_draft, llm_data_or_err)
                        llm_used = True
                        llm_status = "ok"
                    else:
                        llm_status = f"failed: {llm_data_or_err}"
                else:
                    llm_status = "image_not_found"
            else:
                llm_status = "disabled_or_no_key"

            page_elements = manual_draft.get("page_elements") if isinstance(manual_draft.get("page_elements"), list) else []
            if not page_elements:
                page_elements = _build_page_elements_from_ocr_refs(manual_draft.get("ocr_refs") if isinstance(manual_draft.get("ocr_refs"), dict) else {})
                manual_draft["page_elements"] = page_elements
            manual_draft = _manual_from_legacy_fields_buttons(manual_draft)

            self._send_json(
                200,
                {
                    "ok": True,
                    "history_id": rid,
                    "provider": provider,
                    "llm_used": llm_used,
                    "llm_status": llm_status,
                    "manual_draft": manual_draft,
                    "field_hints": field_hints,
                },
            )
            return

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
            _rest_h = path[len("/api/history/") :].strip("/")
            _parts_h = [p for p in _rest_h.split("/") if p]
            if len(_parts_h) != 1:
                self._send_json(400, {"error": "Invalid path"})
                return
            try:
                rid = int(_parts_h[0])
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

        # ---- SSE: requirement analysis library batch generate (progress + previews) ----
        if path == "/api/requirement-analysis/generate/sse":
            force = (qs.get("force") or ["1"])[0]
            target_hid = (qs.get("history_id") or [None])[0]
            stage = str((qs.get("stage") or ["all"])[0] or "all").strip().lower()
            if stage not in ("all", "style", "rest"):
                self._send_json(400, {"error": "Invalid stage, expected all/style/rest"})
                return
            try:
                all_records = [_normalize_record(x) for x in _read_history()]
            except Exception as e:
                # SSE 失败则直接返回 JSON（非事件流）
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return
            records = all_records
            if target_hid not in (None, ""):
                try:
                    hid_i = int(target_hid)
                except Exception:
                    self._send_json(400, {"error": "Invalid history_id"})
                    return
                records = [r for r in all_records if int(r.get("id", -1)) == hid_i]
                if not records:
                    self._send_json(404, {"error": "history_id not found"})
                    return

            # SSE headers（须关闭连接或客户端在 done 后 cancel，否则 fetch 流在 keep-alive 下可能永不结束）
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "close")
            self._send_cors()
            self.end_headers()

            def _sse(event: str, data: dict[str, Any]) -> None:
                try:
                    self.wfile.write(f"event: {event}\n".encode("utf-8"))
                    self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    # Ignore broken client stream write errors.
                    pass
            generated = 0
            errors: list[dict[str, Any]] = []
            total = len(records)
            stage_text = "全量分析" if stage == "all" else ("样式分析" if stage == "style" else "内容/交互/数据分析")
            _sse("log", {"msg": f"开始生成需求分析库（阶段：{stage_text}）…"})

            for r in records:
                hid = r.get("id")
                if hid is None:
                    continue
                hid_i = int(hid)
                has_style = bool(str(r.get("analysis_style") or "").strip())
                has_rest = bool(str(r.get("analysis_content") or "").strip() and str(r.get("analysis_interaction") or "").strip())
                if stage == "style":
                    need = str(force) == "1" or not has_style
                elif stage == "rest":
                    need = str(force) == "1" or not has_rest
                else:
                    need = str(force) == "1" or not (has_style and has_rest)
                if not need:
                    _sse("progress", {"history_id": hid_i, "stage": "skip", "generated": generated, "total": total})
                    continue

                _sse("progress", {"history_id": hid_i, "stage": "start", "generated": generated, "total": total})
                try:
                    out = _generate_requirement_library_for_record(r, stage=stage)
                    if stage in ("all", "style"):
                        r["analysis_style"] = out.get("analysis_style") or ""
                        ast = out.get("analysis_style_table")
                        r["analysis_style_table"] = ast if isinstance(ast, list) else []
                    if stage in ("all", "rest"):
                        r["analysis_content"] = out.get("analysis_content") or ""
                        r["analysis_interaction"] = out.get("analysis_interaction") or ""
                        r["analysis_data"] = out.get("analysis_data")
                    r["analysis_generated_at"] = _now_iso()
                    r["updated_at"] = _now_iso()
                    generated += 1

                    # send partial previews to SSE so frontend can render incremental result
                    style_preview = str(r.get("analysis_style") or "")[:220]
                    content_preview = str(r.get("analysis_content") or "")[:220]
                    interaction_preview = str(r.get("analysis_interaction") or "")[:220]
                    _sse(
                        "log",
                        {
                            "history_id": hid_i,
                            "msg": f"[{hid_i}] 已完成「{stage_text}」，预览已更新。",
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
                    _sse("log", {"history_id": hid_i, "msg": f"[{hid_i}] generation failed: {err}"})
                    _sse("progress", {"history_id": hid_i, "stage": "error", "generated": generated, "total": total})

            try:
                _write_history(all_records)
                _sse("log", {"msg": "需求分析库已写入存储。"})
            except Exception as e:
                _sse("log", {"msg": f"Persist failed: {e}"})
                errors.append({"history_id": None, "error": str(e)})

            _sse("done", {"ok": True, "stage": stage, "total": total, "generated": generated, "errors": errors[:20]})
            return

        # ---- SSE锛氱敤渚嬬敓鎴愶紙灞曠ず AI 瀵硅瘽杩囩▼ + 浜屾纭娴佺▼锛?---
        if path == "/api/cases/generate/sse":
            if not _auth_require_any(self, ("menu.case.management",)):
                return
            hid = (qs.get("history_id") or [None])[0]
            force = (qs.get("force") or ["0"])[0]
            req_system_id = (qs.get("system_id") or [None])[0]
            sid_filter = None
            if req_system_id not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(req_system_id)
                except Exception:
                    self._send_json(400, {"error": "Invalid system_id"})
                    return
            phase = str((qs.get("phase") or ["首次生成"])[0] or "首次生成")
            if not hid:
                self._send_json(400, {"error": "history_id required"})
                return
            try:
                hid_i = int(hid)
            except Exception:
                self._send_json(400, {"error": "Invalid history_id"})
                return

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
                    pass

            _sse("phase", {"history_id": hid_i, "phase": phase, "force": str(force) == "1"})

            try:
                history = _read_history(system_id=sid_filter)
                record = next((x for x in history if isinstance(x, dict) and int(x.get("id", -1)) == hid_i), None)
                if not record:
                    _sse("error", {"history_id": hid_i, "phase": phase, "error": "History record not found"})
                    _sse("done", {"ok": False, "history_id": hid_i, "phase": phase})
                    return

                record = _normalize_record(record)
                # Always read full case set before write-back.
                # Reading a system-scoped subset and then calling _write_cases(cases)
                # can drop records from other systems.
                raw_cases = _read_cases()
                cases = [x for x in (raw_cases if isinstance(raw_cases, list) else []) if isinstance(x, dict)]
                existed = [x for x in cases if int(x.get("history_id") or 0) == hid_i]
                if existed and str(force) != "1":
                    msg = (
                        f"该截图已生成过用例（共 {len(existed)} 条）。"
                        "是否删除旧用例并重新插入本次生成结果？"
                    )
                    _sse("need_confirm", {"history_id": hid_i, "phase": phase, "message": msg, "existing_count": len(existed), "generated_count": 0})
                    _sse(
                        "done",
                        {
                            "ok": False,
                            "history_id": hid_i,
                            "phase": phase,
                            "need_confirm": True,
                            "message": msg,
                            "existing_count": len(existed),
                            "generated_count": 0,
                        },
                    )
                    return

                _sse("log", {"history_id": hid_i, "phase": phase, "msg": f"Start phase {phase}: generating cases via AI..."})

                def _svc_emit(payload: dict[str, Any]) -> None:
                    event_name = str(payload.get("event") or "")
                    base = {"history_id": hid_i, "phase": phase, **payload}
                    if event_name in ("ai_request", "ai_response"):
                        _sse("dialog", base)
                    elif event_name == "scope_assessment":
                        _sse("scope", base)
                    elif event_name == "done":
                        _sse("log", {"history_id": hid_i, "phase": phase, "msg": str(payload.get("msg") or "AI 鐢熸垚瀹屾垚")})
                    elif event_name == "error":
                        _sse("error", {"history_id": hid_i, "phase": phase, "error": str(payload.get("msg") or "LLM 璋冪敤澶辫触")})
                    else:
                        _sse("log", {"history_id": hid_i, "phase": phase, "msg": str(payload.get("msg") or "")})

                try:
                    generated = _generate_cases_from_history(record, emit=_svc_emit)
                except Exception as e:
                    _sse("error", {"history_id": hid_i, "phase": phase, "error": str(e) or "LLM 鐢熸垚澶辫触锛岃妫€鏌ラ厤缃悗閲嶈瘯"})
                    _sse("done", {"ok": False, "history_id": hid_i, "phase": phase})
                    return

                replaced = 0
                if existed and str(force) == "1":
                    replaced = len(existed)
                    cases = [x for x in cases if int(x.get("history_id") or 0) != hid_i]
                    _sse("log", {"history_id": hid_i, "phase": phase, "msg": f"Existing cases replaced: {replaced}"})

                sse_system_id = sid_filter if sid_filter is not None else record.get("system_id")

                first_id = _next_case_id()
                for i, c in enumerate(generated):
                    c["id"] = first_id + i
                    if sse_system_id is not None:
                        c["system_id"] = sse_system_id
                    cases.insert(0, c)
                _write_cases(cases)
                _sse(
                    "done",
                    {
                        "ok": True,
                        "history_id": hid_i,
                        "phase": phase,
                        "inserted_count": len(generated),
                        "replaced_count": replaced,
                    },
                )
                return
            except Exception as e:
                _sse("error", {"history_id": hid_i, "phase": phase, "error": f"SSE processing failed: {e}"})
                _sse("done", {"ok": False, "history_id": hid_i, "phase": phase})
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
        path_clean = path.rstrip("/") or "/"

        if callable(_api_auth_post):
            if _api_auth_post(
                self,
                path=path,
                deps={
                    "read_config": _read_config,
                    "use_mysql": _use_mysql,
                    "db_mysql": _db_mysql,
                },
            ):
                return
        if not _auth_gate(self, "POST", path, qs):
            return

        if callable(_api_systems_post):
            handled = _api_systems_post(
                self,
                path=path,
                deps={
                    "read_systems": _read_systems,
                    "read_system_by_id": _read_system_by_id,
                    "create_system": _create_system,
                    "update_system": _update_system,
                    "delete_system": _delete_system,
                    "now_iso": _now_iso,
                },
            )
            if handled:
                return

        if callable(_api_history_cases_post):
            handled = _api_history_cases_post(
                self,
                path=path,
                deps={
                    "parse_json_body": _parse_json_body,
                    "read_history": _read_history,
                    "write_history": _write_history,
                    "normalize_record": _normalize_record,
                    "now_iso": _now_iso,
                    "next_history_id": _next_history_id,
                    "parse_menu_from_filename": _parse_menu_from_filename,
                    "is_valid_filename": _is_valid_filename,
                    "read_cases": _read_cases,
                    "write_cases": _write_cases,
                    "normalize_case": _normalize_case,
                    "next_case_id": _next_case_id,
                    "manual_from_legacy_fields_buttons": _manual_from_legacy_fields_buttons,
                    "legacy_buttons_fields_from_elements": _legacy_buttons_fields_from_elements,
                    "extract_upload_stored_name": _extract_upload_stored_name,
                    "upload_dir": UPLOAD_DIR,
                    "db_mysql": _db_mysql,
                    "use_mysql": _use_mysql,
                },
            )
            if handled:
                return

        def _delete_style_row_impl(rid: int, row_index: int) -> None:
            items = _read_history()
            hi = next((i for i, x in enumerate(items) if int(x.get("id", -1)) == rid), None)
            if hi is None:
                self._send_json(404, {"error": "Not found"})
                return
            record = _normalize_record(dict(items[hi]))
            table = record.get("analysis_style_table")
            if not isinstance(table, list):
                table = []
            if row_index < 0 or row_index >= len(table):
                self._send_json(400, {"error": "Invalid row index"})
                return
            table = table[:row_index] + table[row_index + 1 :]
            record["analysis_style_table"] = table
            record["updated_at"] = _now_iso()
            items[hi] = record
            _write_history(items)
            self._send_json(200, record)

        # POST /api/history/style-table-row/delete 鈥?鎵佸钩璺緞锛堟帹鑽愶紝閬垮厤宓屽璺緞鍦ㄤ唬鐞嗕笅 404锛?        # Body: {"history_id": 15, "id": 0} 鎴?{"history_id":15,"row_index":0} 鈥?id/row_index 涓鸿涓嬫爣
        if path_clean == "/api/history/style-table-row/delete":
            payload = _parse_json_body(self)
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "Invalid payload"})
                return
            raw_hid = payload.get("history_id")
            if raw_hid is None:
                raw_hid = payload.get("historyId")
            if raw_hid is None:
                self._send_json(400, {"error": "history_id required"})
                return
            try:
                rid = int(raw_hid)
            except Exception:
                self._send_json(400, {"error": "Invalid history_id"})
                return
            raw_ri = payload.get("row_index")
            if raw_ri is None:
                raw_ri = payload.get("id")
            if raw_ri is None:
                self._send_json(400, {"error": "row_index or id required"})
                return
            try:
                row_index = int(raw_ri)
            except Exception:
                self._send_json(400, {"error": "Invalid row index"})
                return
            _delete_style_row_impl(rid, row_index)
            return

        # POST /api/history/<id>/analysis-style-table/delete
        # Body: {"row_index": 0} 鎴?{"id": 0} 鈥?瑕佸垹闄ょ殑鏍峰紡琛ㄨ涓嬫爣锛? 璧凤級
        _style_del_suffix = "/analysis-style-table/delete"
        if path_clean.startswith("/api/history/") and path_clean.endswith(_style_del_suffix):
            mid = path_clean[len("/api/history/") : -len(_style_del_suffix)].strip("/")
            if not mid or "/" in mid:
                self._send_json(400, {"error": "Invalid path"})
                return
            try:
                rid = int(mid)
            except Exception:
                self._send_json(400, {"error": "Invalid id"})
                return
            payload = _parse_json_body(self)
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "Invalid payload"})
                return
            raw_ri = payload.get("row_index")
            if raw_ri is None:
                raw_ri = payload.get("id")
            if raw_ri is None:
                self._send_json(400, {"error": "row_index or id required"})
                return
            try:
                row_index = int(raw_ri)
            except Exception:
                self._send_json(400, {"error": "Invalid row index"})
                return
            _delete_style_row_impl(rid, row_index)
            return

        if path_clean in ["/api/requirement-analysis/generate", "/api/requirement/analysis/generate"]:
            force = (qs.get("force") or ["1"])[0]
            target_hid = (qs.get("history_id") or [None])[0]
            stage = str((qs.get("stage") or ["all"])[0] or "all").strip().lower()
            if stage not in ("all", "style", "rest"):
                self._send_json(400, {"error": "Invalid stage, expected all/style/rest"})
                return
            try:
                all_records = [_normalize_record(x) for x in _read_history()]
            except Exception as e:
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return
            records = all_records
            if target_hid not in (None, ""):
                try:
                    hid_i = int(target_hid)
                except Exception:
                    self._send_json(400, {"error": "Invalid history_id"})
                    return
                records = [r for r in all_records if int(r.get("id", -1)) == hid_i]
                if not records:
                    self._send_json(404, {"error": "history_id not found"})
                    return

            generated = 0
            errors: list[dict[str, Any]] = []
            for r in records:
                hid = r.get("id")
                if hid is None:
                    continue
                hid_i = int(hid)
                has_style = bool(str(r.get("analysis_style") or "").strip())
                has_rest = bool(str(r.get("analysis_content") or "").strip() and str(r.get("analysis_interaction") or "").strip())
                if stage == "style":
                    need = str(force) == "1" or not has_style
                elif stage == "rest":
                    need = str(force) == "1" or not has_rest
                else:
                    need = str(force) == "1" or not (has_style and has_rest)
                if not need:
                    continue

                try:
                    out = _generate_requirement_library_for_record(r, stage=stage)
                    if stage in ("all", "style"):
                        r["analysis_style"] = out.get("analysis_style") or ""
                        ast = out.get("analysis_style_table")
                        r["analysis_style_table"] = ast if isinstance(ast, list) else []
                    if stage in ("all", "rest"):
                        r["analysis_content"] = out.get("analysis_content") or ""
                        r["analysis_interaction"] = out.get("analysis_interaction") or ""
                        r["analysis_data"] = out.get("analysis_data")
                    r["analysis_generated_at"] = _now_iso()
                    r["updated_at"] = _now_iso()
                    generated += 1
                except Exception as e:
                    errors.append({"history_id": hid_i, "error": str(e)})

            try:
                _write_history(all_records)
            except Exception as e:
                self._send_json(500, {"error": f"保存需求库失败: {e}", "generated": generated, "errors": errors[:10]})
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "stage": stage,
                    "total": len(records),
                    "generated": generated,
                    "errors": errors[:20],
                },
            )
            return

        # ---- 需求向量：AI 分析当前截图预识别内容（仅输出文本）----
        if path_clean in ["/api/requirement-vector/analyze", "/api/requirement/vector/analyze"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    self._send_json(400, {"error": "Invalid system_id"})
                    return
            raw_hid = payload.get("history_id")
            try:
                hid_i = int(raw_hid)
            except Exception:
                self._send_json(400, {"error": "history_id required"})
                return
            rec = _read_history_one(hid_i, system_id=sid_filter)
            if not rec:
                self._send_json(404, {"error": "history_id not found"})
                return
            analysis_result = _build_case_generation_analysis_text_for_record(rec)
            self._send_json(200, {"ok": True, "history_id": hid_i, "analysis_result": analysis_result})
            return

        if path_clean in ["/api/requirement-network/preview", "/api/requirement/network/preview"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    self._send_json(400, {"error": "Invalid system_id"})
                    return
            raw_hid = payload.get("history_id")
            try:
                hid_i = int(raw_hid)
            except Exception:
                self._send_json(400, {"error": "history_id required"})
                return
            try:
                raw = _read_history_one(hid_i, system_id=sid_filter)
            except Exception as e:
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return
            if not raw:
                self._send_json(404, {"error": "history_id not found"})
                return
            build_text = _build_vector_analysis_text_for_record(_normalize_record(raw))
            self._send_json(200, {"ok": True, "history_id": hid_i, "build_text": build_text})
            return

        # ---- 闇€姹傜綉缁滃簱锛氬浘鏁版嵁锛堣妭鐐?杈?鍚戦噺锛屼緵鍓嶇鍙鍖栵級----
        if path_clean in ["/api/requirement-network/graph", "/api/requirement/network/graph"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            raw_hid = payload.get("history_id")
            try:
                hid_i = int(raw_hid)
            except Exception:
                self._send_json(400, {"error": "history_id required"})
                return
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            if not _use_mysql() or not _db_mysql or not hasattr(_db_mysql, "read_requirement_network_graph"):
                self._send_json(500, {"error": "MySQL 未启用或不可用，无法读取需求网络图数据"})
                return
            try:
                graph = _db_mysql.read_requirement_network_graph(history_id=hid_i, system_id=sid_filter)
            except Exception as e:
                self._send_json(500, {"error": f"read graph failed: {e}"})
                return
            try:
                from backend.services.visualization_service import compute_best_similarity_by_key

                units0 = graph.get("units") or []
                emb_map = {str(u.get("unit_key") or "").strip(): u.get("embedding") for u in units0 if isinstance(u, dict)}
                best_map = compute_best_similarity_by_key(
                    embeddings=emb_map,
                    keys=[str(u.get("unit_key") or "").strip() for u in units0 if isinstance(u, dict)],
                )
                for u in units0:
                    if not isinstance(u, dict):
                        continue
                    uk = str(u.get("unit_key") or "").strip()
                    if uk and uk in best_map:
                        u["best_similarity"] = float(best_map[uk])
            except Exception:
                pass
            self._send_json(
                200,
                {
                    "ok": True,
                    "history_id": hid_i,
                    "units": graph.get("units") or [],
                    "edges": graph.get("edges") or [],
                    "embedding_model": graph.get("embedding_model") or "",
                },
            )
            return

        # ---- 闇€姹傜綉缁滃簱锛氬叏閲忓浘锛堣法澶氫釜 history 鑱氬悎锛?---
        if path_clean in ["/api/requirement-network/graph-all", "/api/requirement/network/graph-all"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            try:
                limit_units = int(payload.get("limit_units", 800))
            except Exception:
                limit_units = 800
            try:
                limit_edges = int(payload.get("limit_edges", 4000))
            except Exception:
                limit_edges = 4000
            show_all = bool(payload.get("show_all") or payload.get("no_limit") or payload.get("unlimited"))

            if not _use_mysql() or not _db_mysql or not hasattr(_db_mysql, "read_requirement_network_graph_all"):
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                graph = _db_mysql.read_requirement_network_graph_all(
                    system_id=sid_filter,
                    limit_units=limit_units,
                    limit_edges=limit_edges,
                    show_all=show_all,
                )
            except Exception as e:
                self._send_json(500, {"error": f"read graph-all failed: {e}"})
                return
            try:
                from backend.services.visualization_service import compute_best_similarity_by_key

                units0 = graph.get("units") or []
                emb_map = {str(u.get("unit_key") or "").strip(): u.get("embedding") for u in units0 if isinstance(u, dict)}
                best_map = compute_best_similarity_by_key(
                    embeddings=emb_map,
                    keys=[str(u.get("unit_key") or "").strip() for u in units0 if isinstance(u, dict)],
                )
                for u in units0:
                    if not isinstance(u, dict):
                        continue
                    uk = str(u.get("unit_key") or "").strip()
                    if uk and uk in best_map:
                        u["best_similarity"] = float(best_map[uk])
            except Exception:
                pass
            # 诊断信息：帮助定位 best_similarity 全为 1.000 的根因（向量是否高度重合）
            diag: dict[str, Any] = {}
            try:
                import numpy as np

                units0 = graph.get("units") or []
                vecs: list[list[float]] = []
                for u in units0:
                    if not isinstance(u, dict):
                        continue
                    emb = u.get("embedding")
                    if isinstance(emb, list) and len(emb) >= 2:
                        try:
                            v = [float(x) for x in emb]
                        except Exception:
                            continue
                        vecs.append(v)
                if len(vecs) >= 2:
                    X = np.asarray(vecs, dtype=np.float32)
                    norms = np.linalg.norm(X, axis=1)
                    # L2 归一化
                    Xn = X / np.maximum(norms[:, None], 1e-12)
                    # 鏋佺畝閲嶅鐜囷細鐢ㄥ墠 8 缁村洓鑸嶄簲鍏ュ仛 fingerprint锛堣冻澶熷彂鐜扳€滄墍鏈夊悜閲忎竴鏍封€濓級
                    fp = []
                    for row in Xn:
                        a = row[:8]
                        fp.append(",".join([f"{float(x):.4f}" for x in a]))
                    unique = len(set(fp))
                    diag = {
                        "emb_count": int(X.shape[0]),
                        "emb_dim": int(X.shape[1]),
                        "norm_min": float(np.min(norms)),
                        "norm_max": float(np.max(norms)),
                        "fp_unique": int(unique),
                        "fp_dup_ratio": float(1.0 - (unique / max(1, len(fp)))),
                    }
            except Exception:
                diag = {}
            self._send_json(
                200,
                {
                    "ok": True,
                    "units": graph.get("units") or [],
                    "edges": graph.get("edges") or [],
                    "embedding_model": graph.get("embedding_model") or "",
                    "meta": {
                        "limit_units": limit_units,
                        "limit_edges": limit_edges,
                        "system_id": sid_filter,
                        "fallback_used": bool((graph.get("meta") or {}).get("fallback_used")),
                        "system_filter_available": bool((graph.get("meta") or {}).get("system_filter_available")),
                        "embedding_diag": diag,
                    },
                },
            )
            return

        # ---- 闇€姹傚悜閲忥細2D 闄嶇淮鏁ｇ偣锛堣瘖鏂?embedding 鍒嗗竷锛?---
        if path_clean in ["/api/requirement/viz/embeddings-2d", "/api/requirement-network/viz/embeddings-2d"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            raw_hid = payload.get("history_id")
            try:
                hid_i = int(raw_hid)
            except Exception:
                self._send_json(400, {"error": "history_id required"})
                return
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            method = str(payload.get("method") or "tsne").strip().lower()
            if not _use_mysql() or not _db_mysql or not hasattr(_db_mysql, "read_requirement_network_graph"):
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                import numpy as np

                from backend.services.visualization_service import normalize_xy_for_svg, reduce_embeddings_to_2d
            except Exception:
                self._send_json(500, {"error": "Visualization dependencies are unavailable (numpy/scikit-learn)."})
                return
            try:
                graph = _db_mysql.read_requirement_network_graph(history_id=hid_i, system_id=sid_filter)
            except Exception as e:
                self._send_json(500, {"error": f"read graph failed: {e}"})
                return
            units = graph.get("units") or []
            # Count graph entities for diagnostics
            try:
                counts = _db_mysql.count_requirement_network(hid_i) if hasattr(_db_mysql, "count_requirement_network") else {}
            except Exception:
                counts = {}
            emb_rows: list[list[float]] = []
            kept: list[dict[str, Any]] = []
            for u in units:
                if not isinstance(u, dict):
                    continue
                emb = u.get("embedding")
                # keep only valid non-empty embedding vectors
                if not isinstance(emb, list) or len(emb) < 1:
                    continue
                try:
                    emb_rows.append([float(x) for x in emb])
                except Exception:
                    continue
                kept.append(u)
            units_total = int(counts.get("units_total", len(units)) or 0)
            units_with_embedding = int(counts.get("units_with_embedding", len(emb_rows)) or 0)
            embeddings_total = int(counts.get("embeddings_total", 0) or 0)
            edges_total = int(counts.get("edges_total", 0) or 0)
            if len(emb_rows) < 1:
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "history_id": hid_i,
                        "method": "none",
                        "note": "not_enough_vectors",
                        "points": [],
                        "embedding_model": graph.get("embedding_model") or "",
                        "units_total": units_total,
                        "units_with_embedding": units_with_embedding,
                        "embeddings_total": embeddings_total,
                        "edges_total": edges_total,
                    },
                )
                return
            X = np.asarray(emb_rows, dtype=np.float64)
            try:
                xy, used = reduce_embeddings_to_2d(X, method=method)
                xy2 = normalize_xy_for_svg(xy)
            except Exception as e:
                self._send_json(500, {"error": f"reduce 2d failed: {e}"})
                return

            def _strip_base_context(text: str) -> str:
                # Remove base context KV prefixes for hover text.
                s = str(text or "").strip()
                if not s:
                    return ""
                if "system=" not in s or ";" not in s:
                    return s
                parts = [p.strip() for p in s.split(";") if p.strip()]
                # hover/鍘熷鏂囨湰閮戒笉灞曠ず杩欎簺涓婁笅鏂?KV锛堜細鏀惧埌鈥滆鎯呭脊绐椻€濈殑鏉ユ簮璺緞閲岋級
                drop_keys = ("system=", "menu=", "page=", "file=", "source=", "label=", "part_index=")
                kept_parts: list[str] = []
                for p in parts:
                    lp = p.lower()
                    if any(lp.startswith(k) for k in drop_keys):
                        continue
                    kept_parts.append(p)
                out = "; ".join(kept_parts).strip()
                return out or s

            def _short_text(text: str, limit: int = 120) -> str:
                s = str(text or "").strip()
                if len(s) <= limit:
                    return s
                return s[: max(0, limit - 3)] + "..."

            def _parse_kv(full_text: str) -> dict[str, str]:
                s = str(full_text or "").strip()
                if not s or ";" not in s:
                    return {}
                out: dict[str, str] = {}
                for part in [p.strip() for p in s.split(";") if p.strip()]:
                    if "=" not in part:
                        continue
                    k, v = part.split("=", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k and v and k not in out:
                        out[k] = v
                return out

            def _parse_source_context(full_text: str) -> dict[str, str]:
                # Parse source context KV from composed content.
                s = str(full_text or "").strip()
                out = {"system": "", "menu": "", "file": "", "page": ""}
                if not s or ";" not in s:
                    return out
                for part in [p.strip() for p in s.split(";") if p.strip()]:
                    if "=" not in part:
                        continue
                    k, v = part.split("=", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k in out and not out[k]:
                        out[k] = v[:512]
                return out

            # Compute top-3 cosine neighbors for each point.
            try:
                mat = np.asarray(emb_rows, dtype=np.float64)
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms = np.maximum(norms, 1e-12)
                mat_n = mat / norms
                sim = mat_n @ mat_n.T
            except Exception:
                sim = None
            points: list[dict[str, Any]] = []
            for i, u in enumerate(kept):
                content_raw = str(u.get("content") or "")[:4000]
                kv = _parse_kv(content_raw)
                # 鈥滃師濮嬫枃鏈€濓細灏介噺鎻愬彇鐪熸鍙鐨勮鍒?璇箟姝ｆ枃锛屼笉甯︿换浣?KV 鍓嶇紑
                extracted_text = ""
                for key in (
                    "rule",
                    "requirement",
                    "content",
                    "detail",
                    "summary",
                    "excerpt",
                    "impact",
                    "action",
                    "target",
                    "name",
                ):
                    if key in kv and str(kv.get(key) or "").strip():
                        extracted_text = str(kv[key]).strip()
                        break
                normalized_texts: list[str] | None = None
                confidence: float | None = None
                if "rule" in kv and str(kv.get("rule") or "").strip():
                    try:
                        from backend.services.rule_normalizer import normalize_rule_text
                    except Exception:
                        from services.rule_normalizer import normalize_rule_text  # type: ignore
                    rr = normalize_rule_text(str(kv.get("rule") or "").strip(), max_chars=30)
                    normalized_text = rr.normalized_text
                    normalized_texts = rr.normalized_texts
                    confidence = rr.confidence
                else:
                    normalized_text = extracted_text or _strip_base_context(content_raw)
                short_text = _short_text(normalized_text, 120)
                src_ctx = _parse_source_context(content_raw)
                top3: list[dict[str, Any]] = []
                best_sim = None
                if sim is not None:
                    try:
                        row = sim[i]
                        k = 4 if len(row) >= 4 else max(1, len(row))
                        idxs = np.argpartition(-row, k - 1)[:k]
                        idxs = idxs[np.argsort(-row[idxs])]
                        for j in idxs:
                            jj = int(j)
                            if jj == int(i):
                                continue
                            uu = kept[jj]
                            c2 = str(uu.get("content") or "")[:1200]
                            n2 = _strip_base_context(c2)
                            if best_sim is None:
                                try:
                                    best_sim = float(row[jj])
                                except Exception:
                                    best_sim = None
                            top3.append(
                                {
                                    "unit_key": uu.get("unit_key"),
                                    "unit_type": uu.get("unit_type"),
                                    "score": float(row[jj]),
                                    "short_text": _short_text(n2, 90),
                                }
                            )
                            if len(top3) >= 3:
                                break
                    except Exception:
                        top3 = []
                points.append(
                    {
                        "unit_key": u.get("unit_key"),
                        "unit_type": u.get("unit_type"),
                        "content": content_raw,
                        "short_text": short_text,
                        "normalized_text": normalized_text,
                        "extracted_text": extracted_text or normalized_text,
                        "normalized_texts": normalized_texts,
                        "confidence": confidence,
                        "top3_similar": top3,
                        "best_similarity": best_sim,
                        "source_context": src_ctx,
                        "x": float(xy2[i, 0]),
                        "y": float(xy2[i, 1]),
                    }
                )
            self._send_json(
                200,
                {
                    "ok": True,
                    "history_id": hid_i,
                    "method": used,
                    "points": points,
                    "embedding_model": graph.get("embedding_model") or "",
                    "units_total": units_total,
                    "units_with_embedding": units_with_embedding,
                    "embeddings_total": embeddings_total,
                    "edges_total": edges_total,
                },
            )
            return

        # ---- 鍚戦噺璐ㄩ噺璇婃柇锛氭渶杩戦偦鐩镐技搴﹀垎甯?+ 楂樼浉浼煎锛堝垽鏂垏鐗?娓呮礂鏄惁瀵艰嚧鍚岃川鍖栵級----
        if path_clean in ["/api/requirement/viz/embedding-quality", "/api/requirement-network/viz/embedding-quality"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            try:
                limit_units = int(payload.get("limit_units", 800))
            except Exception:
                limit_units = 800
            try:
                top_pairs = int(payload.get("top_pairs", 30))
            except Exception:
                top_pairs = 30
            try:
                nn_k = int(payload.get("nn_k", 6))
            except Exception:
                nn_k = 6

            if not _use_mysql() or not _db_mysql or not hasattr(_db_mysql, "read_requirement_network_graph_all"):
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                graph = _db_mysql.read_requirement_network_graph_all(
                    system_id=sid_filter,
                    limit_units=max(50, min(limit_units, 5000)),
                    limit_edges=0,
                )
            except Exception as e:
                self._send_json(500, {"error": f"read graph-all failed: {e}"})
                return

            units0 = [u for u in (graph.get("units") or []) if isinstance(u, dict)]
            # 组装向量矩阵（仅使用有 embedding 的 unit）
            items: list[dict[str, Any]] = []
            vecs: list[list[float]] = []
            for u in units0:
                emb = u.get("embedding")
                if not isinstance(emb, list) or len(emb) < 2:
                    continue
                try:
                    v = [float(x) for x in emb]
                except Exception:
                    continue
                items.append(u)
                vecs.append(v)

            if len(vecs) < 2:
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "note": "not_enough_vectors",
                        "units": len(units0),
                        "embeddings": len(vecs),
                        "pairs": [],
                        "stats": {},
                    },
                )
                return

            try:
                import numpy as np
                from sklearn.neighbors import NearestNeighbors  # type: ignore
            except Exception:
                self._send_json(500, {"error": "Visualization dependencies are unavailable (numpy/scikit-learn)."})
                return

            X = np.asarray(vecs, dtype=np.float32)
            norms = np.linalg.norm(X, axis=1)
            Xn = X / np.maximum(norms[:, None], 1e-12)

            k = max(2, min(int(nn_k) + 1, int(Xn.shape[0])))
            nn = NearestNeighbors(n_neighbors=k, metric="cosine", algorithm="auto")
            nn.fit(Xn)
            dists, idxs = nn.kneighbors(Xn, n_neighbors=k, return_distance=True)

            best_scores: list[float] = []
            best_pairs: list[dict[str, Any]] = []
            seen_pair: set[tuple[int, int]] = set()

            def _short(s: Any, lim: int = 140) -> str:
                t = str(s or "").strip()
                if len(t) <= lim:
                    return t
                return t[: max(0, lim - 3)] + "..."

            for i in range(Xn.shape[0]):
                # 找到第一个非自身的近邻
                j_best = None
                s_best = None
                for r in range(min(k, idxs.shape[1])):
                    j = int(idxs[i, r])
                    if j == i:
                        continue
                    s = float(1.0 - float(dists[i, r]))
                    j_best = j
                    s_best = s
                    break
                if j_best is None or s_best is None:
                    continue
                best_scores.append(float(s_best))

                a, b = (i, j_best) if i < j_best else (j_best, i)
                if (a, b) in seen_pair:
                    continue
                seen_pair.add((a, b))

                ua = items[a]
                ub = items[b]
                best_pairs.append(
                    {
                        "score": float(s_best),
                        "a": {
                            "unit_key": str(ua.get("unit_key") or ""),
                            "unit_type": str(ua.get("unit_type") or ""),
                            "history_id": (ua.get("metadata") or {}).get("history_id"),
                            "text": _short(ua.get("extracted_text") or ua.get("normalized_text") or ua.get("content")),
                            "source_context": ua.get("source_context") or {},
                        },
                        "b": {
                            "unit_key": str(ub.get("unit_key") or ""),
                            "unit_type": str(ub.get("unit_type") or ""),
                            "history_id": (ub.get("metadata") or {}).get("history_id"),
                            "text": _short(ub.get("extracted_text") or ub.get("normalized_text") or ub.get("content")),
                            "source_context": ub.get("source_context") or {},
                        },
                    }
                )

            best_pairs.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
            best_pairs = best_pairs[: max(0, int(top_pairs))]

            stats: dict[str, Any] = {}
            try:
                arr = np.asarray(best_scores, dtype=np.float32)
                stats = {
                    "count": int(arr.shape[0]),
                    "min": float(np.min(arr)),
                    "p50": float(np.quantile(arr, 0.50)),
                    "p80": float(np.quantile(arr, 0.80)),
                    "p90": float(np.quantile(arr, 0.90)),
                    "p95": float(np.quantile(arr, 0.95)),
                    "max": float(np.max(arr)),
                    "mean": float(np.mean(arr)),
                }
            except Exception:
                stats = {}

            self._send_json(
                200,
                {
                    "ok": True,
                    "system_id": sid_filter,
                    "embedding_model": graph.get("embedding_model") or "",
                    "units": len(units0),
                    "embeddings": int(Xn.shape[0]),
                    "stats": stats,
                    "pairs": best_pairs,
                },
            )
            return

        # ---- 闇€姹傜綉缁滃簱锛氱粺璁″璐︼紙瀹氫綅鍐欏叆鐨?history_id锛?---
        if path_clean in ["/api/requirement/network/counts", "/api/requirement-network/counts"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            try:
                limit = int(payload.get("limit", 200))
            except Exception:
                limit = 200
            if not _use_mysql() or not _db_mysql or not hasattr(_db_mysql, "list_requirement_network_counts"):
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                rows = _db_mysql.list_requirement_network_counts(system_id=sid_filter, limit=limit)
            except Exception as e:
                self._send_json(500, {"error": f"read counts failed: {e}"})
                return
            self._send_json(200, {"ok": True, "rows": rows})
            return

        # ---- 闇€姹傚悜閲忥細鐩镐技搴﹁涔夌綉缁滐紙浣欏鸡闃堝€煎缓杈癸級----
        if path_clean in ["/api/requirement/viz/similarity-graph", "/api/requirement-network/viz/similarity-graph"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            raw_hid = payload.get("history_id")
            try:
                hid_i = int(raw_hid)
            except Exception:
                self._send_json(400, {"error": "history_id required"})
                return
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            th = payload.get("thresholds")
            thresholds = th if isinstance(th, dict) else None
            try:
                top_k_per_node = int(payload.get("top_k_per_node", 16))
            except Exception:
                top_k_per_node = 16
            try:
                max_nodes = int(payload.get("max_nodes", 600))
            except Exception:
                max_nodes = 600
            if not _use_mysql() or not _db_mysql or not hasattr(_db_mysql, "read_requirement_network_graph"):
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                from backend.services.visualization_service import build_similarity_graph
            except Exception:
                self._send_json(500, {"error": "visualization_service is unavailable."})
                return
            try:
                graph = _db_mysql.read_requirement_network_graph(history_id=hid_i, system_id=sid_filter)
            except Exception as e:
                self._send_json(500, {"error": f"read graph failed: {e}"})
                return
            units = graph.get("units") or []
            emb_map: dict[str, list[float]] = {}
            for u in units:
                if not isinstance(u, dict):
                    continue
                uk = str(u.get("unit_key") or "").strip()
                emb = u.get("embedding")
                if uk and isinstance(emb, list) and emb:
                    emb_map[uk] = emb
            try:
                nodes, edges = build_similarity_graph(
                    units,
                    emb_map,
                    thresholds=thresholds,
                    top_k_per_node=top_k_per_node,
                    max_nodes=max_nodes,
                )
            except Exception as e:
                self._send_json(500, {"error": f"build similarity graph failed: {e}"})
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "history_id": hid_i,
                    "nodes": nodes,
                    "edges": edges,
                    "embedding_model": graph.get("embedding_model") or "",
                    "meta": {"top_k_per_node": top_k_per_node, "max_nodes": max_nodes},
                },
            )
            return

        # ---- 闇€姹傚悜閲忥細璁板綍绾х浉浼煎害锛堝 history 鑱氬悎鍧囧€煎悜閲?鈫?浣欏鸡鐩镐技锛?---
        if path_clean in [
            "/api/requirement/viz/record-similarity",
            "/api/requirement-network/viz/record-similarity",
        ]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            ids_raw = payload.get("history_ids")
            if not isinstance(ids_raw, list) or not ids_raw:
                self._send_json(400, {"error": "history_ids (list) required"})
                return
            sid_raw = payload.get("system_id")
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            if not _use_mysql() or not _db_mysql:
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                import numpy as np
                import math
            except Exception:
                self._send_json(500, {"error": "numpy is unavailable."})
                return

            # embedding allowlist
            embed_allow_types = [
                "requirement_rule",
                "interaction_rule",
                "data_upstream",
                "data_downstream",
                "data_logic_relation",
                "data_element",
                "cross_page_link",
                "vector_analysis_rule",
            ]

            # 鎵归噺璇诲彇
            rows = []
            if hasattr(_db_mysql, "read_requirement_network_for_search_many"):
                try:
                    rows = _db_mysql.read_requirement_network_for_search_many(
                        history_ids=[int(x) for x in ids_raw if str(x).strip()],
                        unit_types=embed_allow_types,
                        system_id=sid_filter,
                    )
                except Exception:
                    rows = []
            else:
                # fallback: query one-by-one when batch API is unavailable
                rows = []
                for x in ids_raw[:50]:
                    try:
                        hid = int(x)
                    except Exception:
                        continue
                    try:
                        part = _db_mysql.read_requirement_network_for_search(
                            history_id=hid,
                            unit_types=embed_allow_types,
                            system_id=sid_filter,
                        )
                    except Exception:
                        part = []
                    rows.extend(part or [])

            # 按 history 聚合向量均值
            vecs_by_hid: dict[int, list[dict[str, Any]]] = {}
            for r in rows:
                if not isinstance(r, dict):
                    continue
                try:
                    hid = int(r.get("history_id") or 0)
                except Exception:
                    continue
                emb = r.get("embedding")
                if hid <= 0 or not isinstance(emb, list) or not emb:
                    continue
                try:
                    v = [float(xx) for xx in emb]
                except Exception:
                    continue
                if len(v) < 2:
                    continue
                vecs_by_hid.setdefault(hid, []).append(
                    {
                        "embedding": v,
                        "unit_type": str(r.get("unit_type") or ""),
                        "content": str(r.get("content") or ""),
                    }
                )

            requested: list[int] = []
            for x in ids_raw:
                try:
                    hid = int(x)
                except Exception:
                    continue
                if hid > 0 and hid not in requested:
                    requested.append(hid)
            requested = requested[:80]

            # --- 加权策略（缓解「通用模板句抬高相似度」）---
            # 用 token 的 IDF（在当前选中的 records 范围内）做 unit 权重，得到记录级「加权均值向量」
            # 跨页面但共享关键实体/字段（如考生信息）会更突出，而「权限/查询/导出」等通用词权重偏低
            token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
            stop_tokens = {
                "鏉冮檺",
                "鏌ヨ",
                "鎼滅储",
                "瀵煎嚭",
                "瀵煎叆",
                "鍒楄〃",
                "琛ㄦ牸",
                "椤甸潰",
                "鍔熻兘",
                "鎿嶄綔",
                "鏀寔",
                "灞曠ず",
                "鐢熸垚",
                "鏉′欢",
                "缁撴灉",
                "鐢ㄦ埛",
                "绯荤粺",
                "鏁版嵁",
            }

            def _tokens_for_weight(text: str) -> set[str]:
                raw = [m.group(0) for m in token_re.finditer(str(text or ""))]
                out: set[str] = set()
                for t2 in raw:
                    tt = t2.strip()
                    if not tt or len(tt) < 2:
                        continue
                    if tt in stop_tokens:
                        continue
                    out.add(tt)
                return out

            # DF锛歵oken 鍑虹幇浜庡灏戞潯 unit锛堝湪鎵€鏈夐€変腑 records 鐨?unit 鑼冨洿鍐咃級
            df: dict[str, int] = {}
            total_units = 0
            for hid in requested:
                for it in (vecs_by_hid.get(hid) or []):
                    toks = _tokens_for_weight(str(it.get("content") or ""))
                    if not toks:
                        continue
                    total_units += 1
                    for tk in toks:
                        df[tk] = int(df.get(tk, 0) or 0) + 1

            def _idf(tk: str) -> float:
                # 骞虫粦 IDF
                return float(math.log((total_units + 1.0) / (float(df.get(tk, 0) or 0) + 1.0)) + 1.0)

            means: list[list[float]] = []
            kept_ids: list[int] = []
            meta_rows: list[dict[str, Any]] = []
            for hid in requested:
                items = vecs_by_hid.get(hid) or []
                if not items:
                    meta_rows.append({"history_id": hid, "unit_count": 0, "note": "no_vectors"})
                    continue
                # unit 权重：token 的 IDF 求和，裁到合理范围；无 token 的 unit 给很小权重
                vec_list: list[list[float]] = []
                w_list: list[float] = []
                top_tokens_score: dict[str, float] = {}
                for it in items:
                    embv = it.get("embedding")
                    if not isinstance(embv, list) or not embv:
                        continue
                    vec_list.append([float(x) for x in embv])
                    toks = _tokens_for_weight(str(it.get("content") or ""))
                    if not toks:
                        w = 0.2
                    else:
                        w = 0.0
                        for tk in toks:
                            sc = _idf(tk)
                            w += sc
                            # 璁板綍 token 璐＄尞锛堢敤浜庤В閲婏級
                            top_tokens_score[tk] = float(top_tokens_score.get(tk, 0.0) + sc)
                        w = max(0.2, min(6.0, w))
                    w_list.append(float(w))

                if not vec_list:
                    meta_rows.append({"history_id": hid, "unit_count": 0, "note": "no_vectors"})
                    continue

                mat = np.asarray(vec_list, dtype=np.float64)
                wv = np.asarray(w_list, dtype=np.float64).reshape((-1, 1))
                m = np.sum(mat * wv, axis=0) / max(float(np.sum(wv)), 1e-12)
                norm = float(np.linalg.norm(m))
                if norm < 1e-12:
                    meta_rows.append({"history_id": hid, "unit_count": int(mat.shape[0]), "note": "zero_norm"})
                    continue
                m = (m / norm).tolist()
                means.append(m)
                kept_ids.append(hid)
                # 输出 top tokens 便于解释「为什么相似」
                top_toks = sorted(top_tokens_score.items(), key=lambda kv: float(kv[1]), reverse=True)[:8]
                meta_rows.append(
                    {
                        "history_id": hid,
                        "unit_count": int(mat.shape[0]),
                        "note": "",
                        "top_tokens": [k for k, _v in top_toks if k],
                    }
                )

            if len(kept_ids) < 2:
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "history_ids": requested,
                        "kept_ids": kept_ids,
                        "meta": meta_rows,
                        "matrix": [],
                        "pairs": [],
                        "note": "not_enough_records",
                    },
                )
                return

            M = np.asarray(means, dtype=np.float64)
            sim = M @ M.T  # (n,n) cosine since normalized
            n = int(sim.shape[0])

            # 输出矩阵 + pair 排序（上三角）
            matrix: list[list[float]] = []
            for i in range(n):
                row = []
                for j in range(n):
                    row.append(float(sim[i, j]))
                matrix.append(row)

            pairs: list[dict[str, Any]] = []
            for i in range(n):
                for j in range(i + 1, n):
                    pairs.append(
                        {
                            "a": kept_ids[i],
                            "b": kept_ids[j],
                            "similarity": float(sim[i, j]),
                        }
                    )
            pairs.sort(key=lambda x: float(x.get("similarity") or 0.0), reverse=True)
            pairs = pairs[: int(payload.get("top_pairs", 30) or 30)]

            self._send_json(
                200,
                {
                    "ok": True,
                    "history_ids": requested,
                    "kept_ids": kept_ids,
                    "unit_types": embed_allow_types,
                    "meta": meta_rows,
                    "matrix": matrix,
                    "pairs": pairs,
                },
            )
            return

        # ---- 闇€姹傚悜閲忥細妫€绱㈣皟璇曪紙query 鈫?topK锛?---
        if path_clean in ["/api/requirement/debug/vector-query", "/api/requirement-network/debug/vector-query"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            query = str(payload.get("query") or "").strip()
            if not query:
                self._send_json(400, {"error": "query required"})
                return
            try:
                top_k = int(payload.get("top_k", 12))
            except Exception:
                top_k = 12
            try:
                low_th = float(payload.get("low_score_threshold", 0.5))
            except Exception:
                low_th = 0.5
            hid_raw = payload.get("history_id")
            sid_raw = payload.get("system_id")
            hid_filter = None
            if hid_raw not in (None, "", "all", "ALL"):
                try:
                    hid_filter = int(hid_raw)
                except Exception:
                    hid_filter = None
            sid_filter = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            if not _use_mysql() or not _db_mysql:
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
                return
            try:
                from backend.embeddings_service import embed_one
                from backend.services.debug_query_service import debug_vector_query
            except Exception:
                try:
                    from embeddings_service import embed_one  # type: ignore
                    from services.debug_query_service import debug_vector_query  # type: ignore
                except Exception:
                    self._send_json(500, {"error": "embedding/debug modules unavailable."})
                    return
            try:
                q_vec, _model = embed_one(query)
            except Exception as e:
                self._send_json(500, {"error": f"embedding failed: {e}"})
                return
            if not q_vec:
                self._send_json(500, {"error": "empty query embedding"})
                return
            try:
                candidates = _db_mysql.read_requirement_network_for_search(
                    history_id=hid_filter,
                    system_id=sid_filter,
                )
            except Exception as e:
                self._send_json(500, {"error": f"read network failed: {e}"})
                return
            if not candidates:
                dbg = debug_vector_query(query, q_vec, [], top_k=top_k, low_score_threshold=low_th)
                dbg["embedding_model"] = _model
                dbg["ok"] = True
                dbg["note"] = "network_not_built"
                self._send_json(200, dbg)
                return
            dbg = debug_vector_query(query, q_vec, candidates, top_k=top_k, low_score_threshold=low_th)
            dbg["embedding_model"] = _model
            dbg["ok"] = True
            self._send_json(200, dbg)
            return

        # ---- 闇€姹傜綉缁滃簱锛氭瀯寤猴紙瑕嗙洊寮忥級 ----
        if path_clean in ["/api/requirement-network/build", "/api/requirement/network/build"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}
            if not _use_mysql() or not _db_mysql:
                self._send_json(500, {"error": "MySQL 未启用或不可用，无法构建需求网络/向量库，请检查 config 与数据库连接"})
                return

            history_id = payload.get("history_id")
            # system_id：按系统隔离建库；record 无 system_id 时可配合默认系统兜底
            sid_raw = payload.get("system_id")
            sid_filter: int | None = None
            if sid_raw not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(sid_raw)
                except Exception:
                    sid_filter = None
            default_system_id: int | None = None
            if sid_filter is None and _db_mysql is not None and hasattr(_db_mysql, "read_systems"):
                try:
                    systems = _db_mysql.read_systems()
                    for s in systems:
                        if str(s.get("name") or "").strip() == "榛樿绯荤粺":
                            default_system_id = int(s.get("id"))
                            break
                    if default_system_id is None and systems:
                        default_system_id = int(systems[0].get("id"))
                except Exception:
                    default_system_id = None
            analysis_result_text = str(payload.get("analysis_result_text") or "").strip()
            force = str(payload.get("force", 1))
            # 榛樿鍏ㄩ噺寤哄簱锛岀‘淇濆寘鍚法椤甸潰鑱斿姩澧炲己鍗曞厓
            build_scope = str(payload.get("build_scope") or "all").strip().lower()
            unit_limit = int(payload.get("unit_limit", 0) or 0)  # 0 琛ㄧず涓嶉檺鍒讹紝涓昏鐢ㄤ簬璋冭瘯
            embed_model = str(payload.get("embedding_model") or "").strip() or embedding_model(_read_config())

            try:
                if history_id not in [None, "", "all", "ALL"]:
                    try:
                        hid_i = int(history_id)
                    except Exception:
                        self._send_json(400, {"error": "Invalid history_id"})
                        return
                    raw = _read_history_one(hid_i, system_id=sid_filter)
                    if not raw:
                        self._send_json(404, {"error": "history_id not found"})
                        return
                    records = [_normalize_record(raw)]
                else:
                    records = [_normalize_record(x) for x in _read_history(system_id=sid_filter)]
            except Exception as e:
                self._send_json(500, {"error": f"读取历史记录失败: {e}"})
                return

            allow_global_analysis_override = bool(
                analysis_result_text and history_id not in [None, "", "all", "ALL"]
            )
            global_analysis_ignored = bool(analysis_result_text and not allow_global_analysis_override)
            build_summaries: list[dict[str, Any]] = []

            # lazy import: 閬垮厤鍚姩鏃跺姞杞?embedding 妯″瀷
            try:
                from backend.requirement_network import build_atomic_units_and_edges
                from backend.embeddings_service import embed_texts
            except Exception:
                # 鍦ㄩ儴鍒嗚繍琛屾柟寮忎笅锛宻imple_server.py 鎵€鍦ㄧ洰褰曚細浣滀负 sys.path 鏍?                from requirement_network import build_atomic_units_and_edges  # type: ignore
                from embeddings_service import embed_texts  # type: ignore

            def _stable_unit_key(prefix: str, raw: str) -> str:
                s = str(raw or "").strip() or "empty"
                return f"{prefix}:{hashlib.sha1(s.encode('utf-8')).hexdigest()[:10]}"

            def _is_related_text(a: str, b: str) -> bool:
                sa = str(a or "").strip()
                sb = str(b or "").strip()
                if not sa or not sb:
                    return False
                if sa == sb:
                    return True
                if len(sa) >= 2 and sa in sb:
                    return True
                if len(sb) >= 2 and sb in sa:
                    return True
                return False

            def _extract_record_signals(rec: dict[str, Any]) -> dict[str, Any]:
                hid = int(rec.get("id") or 0)
                menu_path = _breadcrumb_for_record(rec)
                actions: set[str] = set()
                fields: set[str] = set()
                results: set[str] = set()

                rows = rec.get("analysis_style_table")
                if isinstance(rows, list):
                    for row in rows[:300]:
                        if not isinstance(row, dict):
                            continue
                        attr = str(row.get("attribute") or "").strip()
                        el = str(row.get("element") or "").strip()
                        req = str(row.get("requirement") or "").strip()
                        txt = f"{el} {req}".strip()
                        if not txt:
                            continue
                        if ("按钮" in attr) or any(
                            x in txt
                            for x in [
                                "提交",
                                "保存",
                                "删除",
                                "新增",
                                "查询",
                                "导入",
                                "导出",
                                "确定",
                                "取消",
                                "审批",
                                "下载",
                            ]
                        ):
                            actions.add(el or txt[:40])
                        elif ("表格" in attr) or ("列表" in attr) or any(x in txt for x in ["表格", "列表", "结果", "统计"]):
                            results.add(el or txt[:40])
                        else:
                            fields.add(el or txt[:40])

                ad = rec.get("analysis_data")
                if isinstance(ad, dict):
                    cf = ad.get("current_function")
                    if isinstance(cf, dict):
                        for x in (cf.get("core_actions") if isinstance(cf.get("core_actions"), list) else []):
                            sx = str(x or "").strip()
                            if sx:
                                actions.add(sx)
                        for x in (cf.get("key_fields") if isinstance(cf.get("key_fields"), list) else []):
                            sx = str(x or "").strip()
                            if sx:
                                fields.add(sx)
                        for x in (cf.get("result_views") if isinstance(cf.get("result_views"), list) else []):
                            sx = str(x or "").strip()
                            if sx:
                                results.add(sx)

                    for item in (ad.get("downstream_impacts") if isinstance(ad.get("downstream_impacts"), list) else [])[:80]:
                        if not isinstance(item, dict):
                            continue
                        sx = str(item.get("action") or "").strip()
                        tx = str(item.get("target") or "").strip()
                        if sx:
                            actions.add(sx)
                        if tx:
                            results.add(tx)

                    for item in (ad.get("upstream_dependencies") if isinstance(ad.get("upstream_dependencies"), list) else [])[:80]:
                        if not isinstance(item, dict):
                            continue
                        ox = str(item.get("data_object") or "").strip()
                        if ox:
                            fields.add(ox)

                req_content = str(rec.get("analysis_content") or "").strip()
                req_key = _stable_unit_key("req_content", req_content[:2000]) if req_content else ""
                return {
                    "history_id": hid,
                    "menu_path": menu_path,
                    "actions": list(actions)[:60],
                    "fields": list(fields)[:80],
                    "results": list(results)[:60],
                    "req_key": req_key,
                }

            signals_by_history: dict[int, dict[str, Any]] = {}
            for rec in records:
                try:
                    hid = int(rec.get("id") or 0)
                except Exception:
                    hid = 0
                if hid <= 0:
                    continue
                signals_by_history[hid] = _extract_record_signals(rec)

            generated = 0
            errors: list[dict[str, Any]] = []
            total = len(records)

            for r in records:
                hid = r.get("id")
                if hid is None:
                    continue
                hid_i = int(hid)
                try:
                    # 鑻ユ湭寮哄埗瑕嗙洊涓斿凡鏈夌綉缁滄暟鎹垯璺宠繃
                    if str(force) != "1":
                        existing = _db_mysql.read_requirement_network_for_search(history_id=hid_i)
                        if existing:
                            continue

                    # Choose per-record analysis source.
                    final_text_for_record = (
                        analysis_result_text
                        if allow_global_analysis_override
                        else str(r.get("vector_analysis_text") or "").strip()
                    )
                    if final_text_for_record:
                        r["_vector_analysis_text"] = final_text_for_record
                    elif build_scope in ["final_only", "final", "result_only", "vector_only"]:
                        errors.append({"history_id": hid_i, "error": "vector_analysis_text is empty; cannot build network"})
                        continue

                    # system 闅旂鍏滃簳瑕嗙洊
                    if r.get("system_id") in (None, "", "null"):
                        if sid_filter is not None:
                            r["system_id"] = sid_filter
                        elif default_system_id is not None:
                            r["system_id"] = default_system_id
                    if build_scope in ["final_only", "final", "result_only", "vector_only"]:
                        r = dict(r)
                        r["analysis_style_table"] = []
                        r["analysis_style"] = ""
                        r["analysis_content"] = ""
                        r["analysis_interaction"] = ""
                        # Parse data hints from final analysis text when in final-only mode.
                        def _parse_final_text_analysis_data(text: str) -> dict[str, Any]:
                            t = str(text or "").strip()
                            if not t:
                                return {}
                            upstream: list[dict[str, Any]] = []
                            downstream: list[dict[str, Any]] = []
                            relations: list[dict[str, Any]] = []
                            lines = [ln.strip() for ln in t.splitlines() if ln.strip()][:800]
                            for ln in lines:
                                low = ln.lower()
                                if any(k in low for k in ["upstream", "input", "source"]):
                                    upstream.append({"source": "final_text", "data_object": ln[:120], "trigger": "final_text", "rule": ln[:300]})
                                if any(k in low for k in ["downstream", "output", "impact", "result"]):
                                    downstream.append({"target": ln[:120], "action": "final_text", "impact": ln[:300]})
                            if upstream and downstream:
                                relations.append({"from": upstream[0].get("data_object"), "to": downstream[0].get("target"), "relation": "data_flow", "detail": "derived from final_text"})
                            out: dict[str, Any] = {}
                            if upstream:
                                out["upstream_dependencies"] = upstream[:120]
                            if downstream:
                                out["downstream_impacts"] = downstream[:120]
                            if relations:
                                out["data_logic_relations"] = relations[:200]
                            return out

                        r["analysis_data"] = _parse_final_text_analysis_data(r.get("_vector_analysis_text") or "")
                        # final-only：避免 manual 里 page_elements 再生成 element 单元，此处一并清空
                        r["manual"] = {"page_type": "", "page_elements": []}
                    units, edges = build_atomic_units_and_edges(r)

                    # ---- 璺ㄩ〉闈㈣仈鍔ㄥ寮猴細鏄惧紡浜у嚭 cross_page_link 鍗曞厓涓庤竟 ----
                    if build_scope not in ["final_only", "final", "result_only", "vector_only"]:
                        curr_sig = signals_by_history.get(hid_i) or {}
                        source_req_key = str(curr_sig.get("req_key") or "").strip()
                        cross_added = 0
                        for other_hid, other_sig in signals_by_history.items():
                            if other_hid == hid_i:
                                continue
                            if cross_added >= 10:
                                break
                            other_fields = [str(x) for x in (other_sig.get("fields") or [])]
                            other_results = [str(x) for x in (other_sig.get("results") or [])]
                            other_targets = other_fields + other_results
    
                            matched_action = ""
                            matched_target = ""
                            relation_type = "cross_page_trigger"
                            for act in [str(x) for x in (curr_sig.get("actions") or [])]:
                                hit = next((t for t in other_targets if _is_related_text(act, t)), "")
                                if hit:
                                    matched_action = act
                                    matched_target = hit
                                    break
    
                            if not matched_action:
                                # 鍏滃簳锛氬嵆浣挎殏鏈懡涓悓鍚嶅厓绱狅紝涔熶繚鐣欌€滃綋鍓嶉〉闈㈠姩浣?-> 鐩爣椤甸潰缁撴灉/瀛楁鈥濈殑鍊欓€夎仈鍔ㄨ涔夈€?
                                acts = [str(x) for x in (curr_sig.get("actions") or []) if str(x).strip()]
                                tgts = [str(x) for x in other_targets if str(x).strip()]
                                if acts and tgts:
                                    matched_action = acts[0]
                                    matched_target = tgts[0]
                                    relation_type = "cross_page_assumed"
                                else:
                                    continue
    
                            src_menu = str(curr_sig.get("menu_path") or f"history:{hid_i}")
                            tgt_menu = str(other_sig.get("menu_path") or f"history:{other_hid}")
                            link_raw = f"{hid_i}|{other_hid}|{matched_action}|{matched_target}|{src_menu}|{tgt_menu}"
                            cross_key = _stable_unit_key("cross_page", link_raw)
                            cross_content = f"Cross-page link: [{src_menu}] action [{matched_action}] triggers [{tgt_menu}] target [{matched_target}]"
                            units.append(
                                {
                                    "unit_key": cross_key,
                                    "unit_type": "cross_page_link",
                                    "content": _clamp_unit_embed_text(cross_content),
                                    "metadata": {
                                        "history_id": hid_i,
                                        "source_history_id": hid_i,
                                        "target_history_id": other_hid,
                                        "source_menu": src_menu,
                                        "target_menu": tgt_menu,
                                        "matched_action": matched_action,
                                        "matched_target": matched_target,
                                        "relation_type": relation_type,
                                    },
                                }
                            )
                            if source_req_key:
                                edges.append(
                                    {
                                        "from_unit_key": source_req_key,
                                        "to_unit_key": cross_key,
                                        "relation_type": relation_type,
                                        "metadata": {"history_id": hid_i, "target_history_id": other_hid},
                                    }
                                )
                            target_req_key = str(other_sig.get("req_key") or "").strip()
                            if target_req_key:
                                edges.append(
                                    {
                                        "from_unit_key": cross_key,
                                        "to_unit_key": target_req_key,
                                        "relation_type": "cross_page_dependency",
                                        "metadata": {"history_id": hid_i, "target_history_id": other_hid},
                                    }
                                )
                                cross_added += 1

                    if unit_limit and len(units) > unit_limit:
                        units = units[:unit_limit]

                    try:
                        from backend.services.unit_content_clean import filter_units_and_edges
                    except Exception:
                        from services.unit_content_clean import filter_units_and_edges  # type: ignore

                    units, edges = filter_units_and_edges(units, edges)

                    # embedding 鍙 content 鍋氭埅鏂紝淇濊瘉鍚戦噺妫€绱笉浼氳瓒呴暱鏂囨湰鎷栨參
                    texts: list[str] = []
                    unit_keys: list[str] = []
                    for u in units:
                        if not isinstance(u, dict):
                            continue
                        uk = str(u.get("unit_key") or "").strip()
                        c = str(u.get("content") or "").strip()
                        ut = str(u.get("unit_type") or "").strip()
                        if not uk or not c:
                            continue
                        # ---- 鍚戦噺闅旂锛氫粎瀵光€滈€昏緫闇€姹傜浉鍏斥€濆崟鍏冨仛 embedding ----
                        # 浣犳寚瀹氱殑鑼冨洿锛氫笂涓嬫父鏁版嵁鑱斿姩 / 琛ㄦ牸鏁版嵁褰卞搷 / 闇€姹傝法椤甸潰鑱斿姩 / 浜や簰涔熺畻
                        # 闈為€昏緫绫伙紙濡?vector_summary / 璇存槑鎬ф憳瑕?/ 鏍峰紡琛ㄧ鐗囷級浠嶅啓鍏?requirement_units锛屼絾涓嶅啓鍚戦噺
                        embed_allow_types = {
                            "requirement_rule",
                            "interaction_rule",
                            "data_upstream",
                            "data_downstream",
                            "data_logic_relation",
                            "data_element",
                            "cross_page_link",
                            "vector_analysis_rule",
                        }
                        if ut and ut not in embed_allow_types:
                            continue
                        texts.append(_clamp_unit_embed_text(c))
                        unit_keys.append(uk)

                    embeddings_list, used_model = ([], embed_model)
                    if texts:
                        embeddings_list, used_model = embed_texts(texts, model_name=embed_model or None)

                    embeddings: dict[str, list[float]] = {}
                    for uk, vec in zip(unit_keys, embeddings_list):
                        if isinstance(vec, list) and vec:
                            embeddings[uk] = vec

                    _rec_sys_id = rec.get("system_id")
                    _db_mysql.write_requirement_network(
                        hid_i,
                        units=units,
                        edges=edges,
                        embeddings=embeddings,
                        embedding_model=used_model or embed_model or "",
                        system_id=int(_rec_sys_id) if _rec_sys_id is not None else None,
                    )
                    type_counter: dict[str, int] = {}
                    for unit in units:
                        if not isinstance(unit, dict):
                            continue
                        unit_type_name = str(unit.get("unit_type") or "other").strip() or "other"
                        type_counter[unit_type_name] = int(type_counter.get(unit_type_name, 0) or 0) + 1
                    top_types = sorted(type_counter.items(), key=lambda item: item[1], reverse=True)[:6]
                    summary_lines = [
                        f"file: {str(r.get('file_name') or f'history:{hid_i}')}" ,
                        f"breadcrumb: {str(_breadcrumb_for_record(r) or 'unknown')}" ,
                        f"units: {len(units)}",
                        f"edges: {len(edges)}",
                        f"embeddings: {len(embeddings)}",
                    ]
                    if top_types:
                        summary_lines.append("top unit types: " + ", ".join(f"{name} x {count}" for name, count in top_types))
                    if analysis_result_text:
                        summary_lines.append(f"建库输入摘要: {analysis_result_text[:280]}")
                    build_summaries.append(
                        {
                            "history_id": hid_i,
                            "summary": "\n".join(summary_lines),
                            "unit_count": len(units),
                            "edge_count": len(edges),
                            "embedding_count": len(embeddings),
                            "unit_types": [{"name": name, "count": count} for name, count in top_types],
                        }
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
                    "build_results": build_summaries[:20],
                    "build_summary": (build_summaries[0]["summary"] if len(build_summaries) == 1 else ""),
                    "meta": {
                        "allow_global_analysis_override": allow_global_analysis_override,
                        "global_analysis_ignored": global_analysis_ignored,
                    },
                },
            )
            return

        # ---- 闇€姹傜綉缁滃簱锛氬悜閲忔绱?----
        if path_clean in ["/api/requirement-network/search", "/api/requirement/network/search"]:
            try:
                payload = _parse_json_body(self)
            except Exception:
                payload = {}

            # 鍏煎锛氶儴鍒嗗鎴风 JSON body 瑙ｆ瀽涓嶇ǔ瀹氭椂锛屽厑璁镐粠 URL query 鍙傛暟璇诲彇
            query = str(payload.get("query") or (qs.get("query") or [None])[0] or "").strip()
            top_k = int(payload.get("top_k", (qs.get("top_k") or [8])[0]) or 8)
            unit_type = payload.get("unit_type") or (qs.get("unit_type") or [None])[0]
            unit_types_raw = payload.get("unit_types")
            if unit_types_raw is None and qs.get("unit_types"):
                unit_types_raw = (qs.get("unit_types") or [None])[0]
            unit_types_list: list[str] | None = None
            if isinstance(unit_types_raw, list):
                unit_types_list = [str(x).strip() for x in unit_types_raw if str(x).strip()]
            elif isinstance(unit_types_raw, str) and unit_types_raw.strip():
                unit_types_list = [x.strip() for x in unit_types_raw.split(",") if x.strip()]
            history_id = payload.get("history_id") or (qs.get("history_id") or [None])[0]
            search_system_id = payload.get("system_id") or (qs.get("system_id") or [None])[0]

            if not query:
                self._send_json(400, {"error": "query required"})
                return

            if not _use_mysql() or not _db_mysql:
                self._send_json(500, {"error": "MySQL is disabled or unavailable."})
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
                sid_filter = None
                if search_system_id not in [None, "", "all", "ALL"]:
                    try:
                        sid_filter = int(search_system_id)
                    except (ValueError, TypeError):
                        sid_filter = None
                candidates = _db_mysql.read_requirement_network_for_search(
                    history_id=hid_filter,
                    unit_type=unit_type if not unit_types_list else None,
                    unit_types=unit_types_list,
                    system_id=sid_filter,
                )
            except Exception as e:
                self._send_json(500, {"error": f"read network failed: {e}"})
                return

            if not candidates:
                self._send_json(200, {"ok": True, "results": [], "note": "network_not_built"})
                return

            results = _cosine_search(query_vec, candidates, top_k=top_k)
            results = _rerank_results(query, results)
            self._send_json(200, {"ok": True, "results": results, "embedding_model": used_model})
            return

        if path == "/api/cases/generate":
            if not _auth_require_any(self, ("menu.case.management",)):
                return
            hid = (qs.get("history_id") or [None])[0]
            req_system_id = (qs.get("system_id") or [None])[0]
            sid_filter = None
            if req_system_id not in (None, "", "all", "ALL"):
                try:
                    sid_filter = int(req_system_id)
                except Exception:
                    self._send_json(400, {"error": "Invalid system_id"})
                    return
            if not hid:
                self._send_json(400, {"error": "history_id required"})
                return
            force = (qs.get("force") or ["0"])[0]
            try:
                hid_i = int(hid)
            except Exception:
                self._send_json(400, {"error": "Invalid history_id"})
                return
            history = _read_history(system_id=sid_filter)
            record = next((x for x in history if int(x.get("id", -1)) == hid_i), None)
            if not record:
                self._send_json(404, {"error": "History record not found"})
                return

            record = _normalize_record(record)
            # Always read full case set before write-back.
            raw_cases = _read_cases()
            cases = [x for x in (raw_cases if isinstance(raw_cases, list) else []) if isinstance(x, dict)]
            existed = [x for x in cases if int(x.get("history_id") or 0) == hid_i]
            if existed and str(force) != "1":
                self._send_json(
                    409,
                    {
                        "error": (
                            f"该截图已生成过用例（共 {len(existed)} 条）。"
                            "是否删除旧用例并重新生成？"
                        ),
                        "existing_count": len(existed),
                    },
                )
                return
            try:
                generated = _generate_cases_from_history(record)
            except Exception as e:
                self._send_json(502, {"error": str(e) or "LLM 生成失败，请检查配置后重试"})
                return
            if existed and str(force) == "1":
                cases = [x for x in cases if int(x.get("history_id") or 0) != hid_i]

            gen_sys_id = sid_filter if sid_filter is not None else record.get("system_id")

            first_id = _next_case_id()
            for i, c in enumerate(generated):
                c["id"] = first_id + i
                if gen_sys_id is not None:
                    c["system_id"] = gen_sys_id
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
                    "step_expected": payload.get("step_expected", []),
                    "priority": payload.get("priority"),
                    "status": payload.get("status", "draft"),
                    "run_notes": payload.get("run_notes", ""),
                    "last_run_at": payload.get("last_run_at", ""),
                    "executor_id": None,
                    "executor_name": "",
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
            )
            _merge_case_executor_from_payload(case, payload)
            cases.insert(0, case)
            _write_cases(cases)
            self._send_json(201, case)
            return

        if path in ("/api/upload", "/api/upload/asset"):
            # fallthrough to existing upload implementation below
            pass
        else:
            self._send_text(404, "Not found")
            return

        # ----- existing upload implementation (supports /api/upload and /api/upload/asset) -----
        upload_mode = "history" if path == "/api/upload" else "asset"
        if upload_mode == "history":
            # 上传截图并写入 screenshot_history（原行为）
            if not _auth_require_any(self, ("action.upload",)):
                return
        else:
            # 上传「任意资产文件」（如用例执行截图），不写入 screenshot_history
            if not _auth_require_any(self, ("action.upload", "action.case.execute")):
                return

        # 此处不再强制 self.path == "/api/upload"，而是复用 multipart 解析逻辑

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
        filename = filename.strip()
        if not _is_valid_filename(filename):
            self._send_json(400, {"error": "鏂囦欢鍚嶄笉鍚堟硶"})
            return

        content_start = file_part.find(b"\r\n\r\n") + 4
        content_end = file_part.rfind(b"\r\n")
        file_content = file_part[content_start:content_end]

        upload_system_id = (qs.get("system_id") or [None])[0]
        if upload_system_id is not None:
            try:
                upload_system_id = int(upload_system_id)
            except (ValueError, TypeError):
                upload_system_id = None

        if upload_mode == "asset":
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            stored_name = _build_storage_filename(filename)
            file_path = UPLOAD_DIR / stored_name
            while file_path.exists():
                stored_name = _build_storage_filename(filename)
                file_path = UPLOAD_DIR / stored_name
            with file_path.open("wb") as f:
                f.write(file_content)

            file_url = f"/uploads/{stored_name}"
            self._send_json(
                201,
                {
                    "file_url": file_url,
                    "stored_name": stored_name,
                    "original_name": filename,
                    "uploaded_at": _now_iso(),
                },
            )
            return

        # Handle ZIP batch upload
        if str(filename).lower().endswith(".zip"):
            if len(file_content) > _MAX_ZIP_UPLOAD_BYTES:
                self._send_json(400, {"error": f"ZIP package too large (max {_MAX_ZIP_UPLOAD_BYTES // (1024 * 1024)}MB)"})
                return
            try:
                batch = _history_records_from_zip_bytes(file_content, upload_system_id)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            first = batch[0]
            resp = dict(first)
            resp["batch"] = True
            resp["batch_count"] = len(batch)
            resp["records"] = batch
            self._send_json(201, resp)
            return

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_name = _build_storage_filename(filename)
        file_path = UPLOAD_DIR / stored_name
        while file_path.exists():
            stored_name = _build_storage_filename(filename)
            file_path = UPLOAD_DIR / stored_name
        with file_path.open("wb") as f:
            f.write(file_content)

        file_url = f"/uploads/{stored_name}"
        items = _read_history()
        system_name, menu_structure = _parse_menu_from_filename(filename)
        rid = _next_history_id()
        record = {
            "id": rid,
            "file_name": filename,
            "file_url": file_url,
            "system_name": system_name,
            "menu_structure": menu_structure,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "analysis": "",
            "system_id": upload_system_id,
        }
        items.insert(0, record)
        _write_history(items)
        self._send_json(201, record)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if not _auth_gate(self, "PUT", path, qs):
            return

        if callable(_api_history_cases_put):
            handled = _api_history_cases_put(
                self,
                path=path,
                deps={
                    "read_cases": _read_cases,
                    "write_cases": _write_cases,
                    "normalize_case": _normalize_case,
                    "read_history": _read_history,
                    "write_history": _write_history,
                    "now_iso": _now_iso,
                    "is_valid_filename": _is_valid_filename,
                    "parse_menu_from_filename": _parse_menu_from_filename,
                    "manual_from_legacy_fields_buttons": _manual_from_legacy_fields_buttons,
                    "legacy_buttons_fields_from_elements": _legacy_buttons_fields_from_elements,
                },
            )
            if handled:
                return

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
            if "priority" in payload:
                case["priority"] = _normalize_case_priority(payload.get("priority"))
            if "steps" in payload and isinstance(payload["steps"], list):
                case["steps"] = [str(x) for x in payload["steps"] if str(x).strip()]
            if "step_expected" in payload and isinstance(payload.get("step_expected"), list):
                case["step_expected"] = [str(x) if x is not None else "" for x in (payload.get("step_expected") or [])]
            if "history_id" in payload:
                case["history_id"] = payload["history_id"]
            if "run_attachments" in payload and isinstance(payload.get("run_attachments"), list):
                cleaned = []
                for it in payload.get("run_attachments") or []:
                    if isinstance(it, str):
                        u = it.strip()
                        if u:
                            cleaned.append({"file_url": u})
                        continue
                    if not isinstance(it, dict):
                        continue
                    fu = str(it.get("file_url") or it.get("url") or "").strip()
                    if not fu:
                        continue
                    cleaned.append(
                        {
                            "file_url": fu,
                            "original_name": str(it.get("original_name") or it.get("name") or "")[:256],
                            "uploaded_at": str(it.get("uploaded_at") or it.get("created_at") or "")[:64],
                        }
                    )
                case["run_attachments"] = cleaned
            _merge_case_executor_from_payload(case, payload)
            _align_step_expected_to_steps(case)
            case["updated_at"] = _now_iso()
            cases[idx] = case
            _write_cases(cases)
            self._send_json(200, case)
            return

        if not path.startswith("/api/history/"):
            self._send_text(404, "Not found")
            return
        # 鍙帴鍙?PUT /api/history/{id}锛堝崟娈垫暟瀛?id锛夛紝閬垮厤 int("5/")銆乮nt("5/extra") 鎶涢敊
        _rest_put = path[len("/api/history/") :].strip("/")
        _parts_put = [p for p in _rest_put.split("/") if p]
        if len(_parts_put) != 1:
            self._send_json(400, {"error": "Invalid path"})
            return
        try:
            rid = int(_parts_put[0])
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
            # 鍏佽鏀瑰睍绀烘枃浠跺悕锛堣仈鍔ㄦ洿鏂拌彍鍗曞眰绾э紝涓嶅啀閲嶅懡鍚嶅疄闄呰惤鐩樻枃浠讹級
            if "file_name" in payload and isinstance(payload["file_name"], str):
                new_file_name = payload["file_name"].strip()
                old_file_name = record.get("file_name")
                if isinstance(old_file_name, str) and new_file_name:
                    if not _is_valid_filename(new_file_name):
                        self._send_json(400, {"error": "Invalid file name"})
                        return
                    duplicated = any(
                        int(x.get("id", -1)) != rid and str(x.get("file_name") or "").strip() == new_file_name
                        for x in items
                        if isinstance(x, dict)
                    )
                    if duplicated:
                        self._send_json(409, {"error": "鏂囦欢鍚嶅凡瀛樺湪"})
                        return
                    record["file_name"] = new_file_name
                    # File name changes imply menu changes (current project convention)
                    record["system_name"], record["menu_structure"] = _parse_menu_from_filename(new_file_name)
                    file_name_changed = True

            # 鍏佽瑕嗙洊鑿滃崟缁撴瀯锛堢敤浜庢墜鍔ㄤ慨姝ｏ級
            if "menu_structure" in payload and isinstance(payload["menu_structure"], list):
                # if file_name changed, keep parsed menu structure from filename
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

            # 鍏佽淇濆瓨/鏇存柊鍒嗘瀽缁撴灉锛堢敤浜庡悗缁汉宸ョ紪杈戯級
            if "analysis" in payload and isinstance(payload["analysis"], str):
                record["analysis"] = payload["analysis"]
            if "analysis_style" in payload and isinstance(payload["analysis_style"], str):
                record["analysis_style"] = payload["analysis_style"]
            if "analysis_content" in payload and isinstance(payload["analysis_content"], str):
                record["analysis_content"] = payload["analysis_content"]
            if "analysis_interaction" in payload and isinstance(payload["analysis_interaction"], str):
                record["analysis_interaction"] = payload["analysis_interaction"]
            if "analysis_data" in payload and isinstance(payload["analysis_data"], (dict, list, str)):
                record["analysis_data"] = payload["analysis_data"]
            if "vector_analysis_text" in payload and isinstance(payload["vector_analysis_text"], str):
                record["vector_analysis_text"] = payload["vector_analysis_text"]
            if "vector_build_summary" in payload and isinstance(payload["vector_build_summary"], str):
                record["vector_build_summary"] = payload["vector_build_summary"]
            if "vector_built_at" in payload and isinstance(payload["vector_built_at"], str):
                record["vector_built_at"] = payload["vector_built_at"].strip()
            if "analysis_style_table" in payload and isinstance(payload["analysis_style_table"], list):
                cleaned_rows: list[dict[str, Any]] = []
                for row in payload["analysis_style_table"]:
                    if not isinstance(row, dict):
                        continue
                    el = str(row.get("element") or "").strip()
                    req = str(row.get("requirement") or "")
                    attr = str(row.get("attribute") or "").strip()
                    if not attr:
                        attrs_raw = row.get("attributes")
                        if isinstance(attrs_raw, list) and attrs_raw:
                            attr = str(attrs_raw[0] or "").strip()
                        elif isinstance(attrs_raw, str) and attrs_raw.strip():
                            attr = attrs_raw.replace("，", ",").split(",")[0].strip()
                    if not attr:
                        attr = "attribute"
                    cleaned_rows.append({"element": el, "attribute": attr, "requirement": req})
                record["analysis_style_table"] = cleaned_rows
            # 淇濆瓨鎵嬪姩琛ュ綍锛堢粨鏋勫寲锛岀敤浜庡姩鎬佺敓鎴愮敤渚嬶級
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
        qs = parse_qs(parsed.query)
        if not _auth_gate(self, "DELETE", path, qs):
            return

        if callable(_api_history_cases_delete):
            handled = _api_history_cases_delete(
                self,
                path=path,
                deps={
                    "read_cases": _read_cases,
                    "write_cases": _write_cases,
                    "read_history": _read_history,
                    "write_history": _write_history,
                    "now_iso": _now_iso,
                    "normalize_record": _normalize_record,
                    "extract_upload_stored_name": _extract_upload_stored_name,
                    "upload_dir": UPLOAD_DIR,
                    "db_mysql": _db_mysql,
                    "use_mysql": _use_mysql,
                },
            )
            if handled:
                return

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

        rest = path[len("/api/history/") :].strip("/")
        if not rest:
            self._send_json(400, {"error": "Invalid path"})
            return
        parts = [p for p in rest.split("/") if p]

        # DELETE /api/history/<id>/analysis-style-table/<row_index>
        if len(parts) == 3 and parts[1] == "analysis-style-table":
            try:
                rid = int(parts[0])
                row_index = int(parts[2])
            except Exception:
                self._send_json(400, {"error": "Invalid id or row index"})
                return
            items = _read_history()
            hi = next((i for i, x in enumerate(items) if int(x.get("id", -1)) == rid), None)
            if hi is None:
                self._send_json(404, {"error": "Not found"})
                return
            record = _normalize_record(dict(items[hi]))
            table = record.get("analysis_style_table")
            if not isinstance(table, list):
                table = []
            if row_index < 0 or row_index >= len(table):
                self._send_json(400, {"error": "Invalid row index"})
                return
            table = table[:row_index] + table[row_index + 1 :]
            record["analysis_style_table"] = table
            record["updated_at"] = _now_iso()
            items[hi] = record
            _write_history(items)
            self._send_json(200, record)
            return

        if len(parts) != 1:
            self._send_text(404, "Not found")
            return
        try:
            rid = int(parts[0])
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
            stored_name = _extract_upload_stored_name(record.get("file_url"))
            if not stored_name:
                # 鍏煎鏃ц褰曪細file_url 涓虹┖鏃跺洖閫€ file_name
                file_name = record.get("file_name")
                stored_name = str(file_name or "").strip() if isinstance(file_name, str) else ""
            if stored_name:
                p = UPLOAD_DIR / stored_name
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

