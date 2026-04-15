from __future__ import annotations

import json
from typing import Any


def _read_json_body(handler: Any) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _permission_codes(handler: Any) -> set[str]:
    user = getattr(handler, "_auth_user", None)
    perms = user.get("permissions") if isinstance(user, dict) else []
    return {str(x) for x in perms if x}


def _has_permission(handler: Any, code: str) -> bool:
    perms = _permission_codes(handler)
    return "*" in perms or code in perms


def _require_permission(handler: Any, code: str) -> bool:
    if _has_permission(handler, code):
        return True
    handler._send_json(403, {"error": "没有权限"})
    return False


def handle_get(handler: Any, *, path: str, deps: dict[str, Any]) -> bool:
    read_systems = deps["read_systems"]
    read_system_by_id = deps["read_system_by_id"]

    if path == "/api/systems":
        # 系统列表：允许“系统列表”能力或与系统隔离相关的业务权限访问（用于普通用户选择系统）
        if not (
            _has_permission(handler, "menu.system")
            or _has_permission(handler, "menu.system.list")
            or _has_permission(handler, "menu.case.management")
            or _has_permission(handler, "menu.case.execution")
            or _has_permission(handler, "menu.case")
            or _has_permission(handler, "menu.analysis")
            or _has_permission(handler, "menu.analysis.upload")
            or _has_permission(handler, "menu.analysis.requirement_library")
            or _has_permission(handler, "menu.preview")
            or _has_permission(handler, "menu.preview.gallery")
        ):
            handler._send_json(403, {"error": "没有权限"})
            return True
        items = read_systems()
        handler._send_json(200, items)
        return True

    if path.startswith("/api/systems/"):
        if not (
            _has_permission(handler, "menu.system")
            or _has_permission(handler, "menu.system.list")
            or _has_permission(handler, "menu.case.management")
            or _has_permission(handler, "menu.case.execution")
            or _has_permission(handler, "menu.case")
            or _has_permission(handler, "menu.analysis")
            or _has_permission(handler, "menu.analysis.upload")
            or _has_permission(handler, "menu.analysis.requirement_library")
            or _has_permission(handler, "menu.preview")
            or _has_permission(handler, "menu.preview.gallery")
        ):
            handler._send_json(403, {"error": "没有权限"})
            return True
        rest = path[len("/api/systems/"):].strip("/")
        if not rest or "/" in rest:
            return False
        try:
            sid = int(rest)
        except Exception:
            return False
        item = read_system_by_id(sid)
        if not item:
            handler._send_json(404, {"error": "System not found"})
            return True
        handler._send_json(200, item)
        return True

    return False


def handle_post(handler: Any, *, path: str, deps: dict[str, Any]) -> bool:
    path_clean = path.rstrip("/") or "/"
    read_systems = deps["read_systems"]
    read_system_by_id = deps["read_system_by_id"]
    create_system = deps["create_system"]
    update_system = deps["update_system"]
    delete_system = deps["delete_system"]
    now_iso = deps["now_iso"]

    if path_clean == "/api/systems/list":
        # 系统列表：允许“系统列表”能力或与系统隔离相关的业务权限访问（用于普通用户选择系统）
        if not (
            _has_permission(handler, "menu.system")
            or _has_permission(handler, "menu.system.list")
            or _has_permission(handler, "menu.case.management")
            or _has_permission(handler, "menu.case.execution")
            or _has_permission(handler, "menu.case")
            or _has_permission(handler, "menu.analysis")
            or _has_permission(handler, "menu.analysis.upload")
            or _has_permission(handler, "menu.analysis.requirement_library")
            or _has_permission(handler, "menu.preview")
            or _has_permission(handler, "menu.preview.gallery")
        ):
            handler._send_json(403, {"error": "没有权限"})
            return True
        items = read_systems()
        handler._send_json(200, items)
        return True

    if path_clean == "/api/systems/detail":
        if not (
            _has_permission(handler, "menu.system")
            or _has_permission(handler, "menu.system.list")
            or _has_permission(handler, "menu.case.management")
            or _has_permission(handler, "menu.case.execution")
            or _has_permission(handler, "menu.case")
            or _has_permission(handler, "menu.analysis")
            or _has_permission(handler, "menu.analysis.upload")
            or _has_permission(handler, "menu.analysis.requirement_library")
            or _has_permission(handler, "menu.preview")
            or _has_permission(handler, "menu.preview.gallery")
        ):
            handler._send_json(403, {"error": "没有权限"})
            return True
        payload = _read_json_body(handler)
        sid_raw = payload.get("id")
        if sid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            sid = int(sid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        item = read_system_by_id(sid)
        if not item:
            handler._send_json(404, {"error": "System not found"})
            return True
        handler._send_json(200, item)
        return True

    if path_clean == "/api/systems/create":
        # 创建系统需要更高权限：只读用户应仅能“选择系统”，不能创建/编辑/删除
        # 仅同时拥有 menu.system 且 menu.system.list 的用户才能创建/编辑/删除
        if not (_has_permission(handler, "menu.system") and _has_permission(handler, "menu.system.list")):
            return True
        payload = _read_json_body(handler)
        name = str(payload.get("name") or "").strip()
        if not name:
            handler._send_json(400, {"error": "name required"})
            return True
        existing = read_systems()
        if any(s.get("name") == name for s in existing):
            handler._send_json(409, {"error": "系统名称已存在"})
            return True
        description = str(payload.get("description") or "")
        ts = now_iso()
        result = create_system(name, description, ts, ts)
        if result is None:
            handler._send_json(500, {"error": "创建系统失败"})
            return True
        handler._send_json(201, result)
        return True

    if path_clean == "/api/systems/update":
        if not (_has_permission(handler, "menu.system") and _has_permission(handler, "menu.system.list")):
            return True
        payload = _read_json_body(handler)
        sid_raw = payload.get("id")
        if sid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            sid = int(sid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        item = read_system_by_id(sid)
        if not item:
            handler._send_json(404, {"error": "System not found"})
            return True
        name = payload.get("name")
        if name is not None:
            name = str(name).strip()
            if not name:
                handler._send_json(400, {"error": "name cannot be empty"})
                return True
            existing = read_systems()
            if any(s.get("name") == name and s.get("id") != sid for s in existing):
                handler._send_json(409, {"error": "系统名称已存在"})
                return True
        description = payload.get("description")
        if description is not None:
            description = str(description)
        result = update_system(sid, name=name, description=description, updated_at=now_iso())
        if result is None:
            handler._send_json(500, {"error": "更新系统失败"})
            return True
        handler._send_json(200, result)
        return True

    if path_clean == "/api/systems/delete":
        if not (_has_permission(handler, "menu.system") and _has_permission(handler, "menu.system.list")):
            return True
        payload = _read_json_body(handler)
        sid_raw = payload.get("id")
        if sid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            sid = int(sid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        item = read_system_by_id(sid)
        if not item:
            handler._send_json(404, {"error": "System not found"})
            return True
        ok = delete_system(sid)
        if not ok:
            handler._send_json(500, {"error": "删除系统失败"})
            return True
        handler._send_json(200, {"message": "System deleted successfully"})
        return True

    return False
