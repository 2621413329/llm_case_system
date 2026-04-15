"""登录、会话、权限配置 API（依赖 MySQL 用户表）。"""

from __future__ import annotations

import json
from typing import Any


def _json_body(handler: Any) -> dict[str, Any]:
    n = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(n) if n > 0 else b"{}"
    try:
        o = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return o if isinstance(o, dict) else {}


def _read_auth_cfg(read_config: Any) -> dict[str, bool]:
    cfg = read_config() if callable(read_config) else {}
    a = cfg.get("auth") if isinstance(cfg.get("auth"), dict) else {}
    return {
        "enabled": bool(a.get("enabled", True)),
        "require_login": bool(a.get("require_login", False)),
        "allow_register": bool(a.get("allow_register", True)),
    }


def handle_get(
    handler: Any,
    *,
    path: str,
    deps: dict[str, Any],
) -> bool:
    read_config = deps.get("read_config")
    use_mysql = deps.get("use_mysql")
    db_mysql = deps.get("db_mysql")

    p = path.rstrip("/") or "/"
    if p != "/api/auth/config":
        return False

    if p == "/api/auth/config":
        ac = _read_auth_cfg(read_config)
        mysql_ok = bool(callable(use_mysql) and use_mysql() and db_mysql)
        handler._send_json(
            200,
            {
                "enabled": ac["enabled"] and mysql_ok,
                "require_login": ac["require_login"] and mysql_ok,
                "allow_register": ac["allow_register"] and mysql_ok,
                "mysql": mysql_ok,
            },
        )
        return True


def _extract_token(handler: Any) -> str:
    h = handler.headers.get("Authorization") or ""
    if isinstance(h, str) and h.lower().startswith("bearer "):
        return h[7:].strip()
    x = handler.headers.get("X-Session-Token") or ""
    return str(x).strip() if x else ""


def handle_post(handler: Any, *, path: str, deps: dict[str, Any]) -> bool:
    p = path.rstrip("/") or "/"
    if p not in ("/api/auth/login", "/api/auth/logout", "/api/auth/register"):
        return False

    read_config = deps.get("read_config")
    use_mysql = deps.get("use_mysql")
    db_mysql = deps.get("db_mysql")

    ac = _read_auth_cfg(read_config)
    mysql_ok = bool(callable(use_mysql) and use_mysql() and db_mysql)
    if not ac["enabled"] or not mysql_ok:
        handler._send_json(503, {"error": "认证未启用或未使用 MySQL"})
        return True

    if p == "/api/auth/register":
        if not ac["allow_register"]:
            handler._send_json(403, {"error": "管理员已关闭自助注册"})
            return True
        if not db_mysql or not hasattr(db_mysql, "auth_register"):
            handler._send_json(503, {"error": "注册服务不可用"})
            return True
        body = _json_body(handler)
        u = str(body.get("username") or "").strip()
        pw = str(body.get("password") or "")
        dn = str(body.get("display_name") or body.get("name") or "").strip()
        out, err = db_mysql.auth_register(u, pw, dn)
        if err:
            handler._send_json(400, {"error": err})
            return True
        handler._send_json(200, out)
        return True

    if p == "/api/auth/login":
        body = _json_body(handler)
        u = str(body.get("username") or "").strip()
        pw = str(body.get("password") or "")
        if not u or not pw:
            handler._send_json(400, {"error": "username and password required"})
            return True
        out = db_mysql.auth_login(u, pw)
        if not out:
            handler._send_json(401, {"error": "用户名或密码错误"})
            return True
        handler._send_json(200, out)
        return True

    # logout：须携带有效 token
    tok = _extract_token(handler) or str(_json_body(handler).get("token") or "").strip()
    if not tok:
        handler._send_json(401, {"error": "请登录"})
        return True
    user = db_mysql.auth_validate_token(tok) if hasattr(db_mysql, "auth_validate_token") else None
    if not user:
        handler._send_json(401, {"error": "请登录"})
        return True
    db_mysql.auth_logout(tok)
    handler._send_json(200, {"ok": True})
    return True
