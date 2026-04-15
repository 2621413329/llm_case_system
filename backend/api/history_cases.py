from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from backend.services.normalize import (
        align_step_expected_to_steps,
        merge_case_executor_from_payload,
        normalize_case_priority,
    )
except Exception:
    from services.normalize import (  # type: ignore
        align_step_expected_to_steps,
        merge_case_executor_from_payload,
        normalize_case_priority,
    )


def _read_json_body_strict(handler: Any) -> tuple[bool, dict[str, Any] | None]:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return False, None
    if not isinstance(payload, dict):
        return False, None
    return True, payload


def _int_or_none(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _row_matches_system_id(row: dict[str, Any], sid: int) -> bool:
    """与 JSON/MySQL 中 system_id 可能为 str/int 的情况兼容，且排除未绑定系统的记录。"""
    rid = _int_or_none(row.get("system_id"))
    return rid is not None and rid == int(sid)


def _permission_codes(handler: Any) -> set[str]:
    user = getattr(handler, "_auth_user", None)
    perms = user.get("permissions") if isinstance(user, dict) else []
    return {str(x) for x in perms if x}


def _has_permission(handler: Any, code: str) -> bool:
    perms = _permission_codes(handler)
    return "*" in perms or code in perms


def _require_any_permission(handler: Any, codes: tuple[str, ...] | list[str]) -> bool:
    if any(_has_permission(handler, code) for code in codes):
        return True
    handler._send_json(403, {"error": "没有权限"})
    return False


def _case_update_is_execution_only(payload: dict[str, Any]) -> bool:
    allowed = {"id", "status", "run_notes", "run_attachments", "run_records", "last_run_at", "executor_name", "executor_id"}
    return all(str(k) in allowed for k in payload.keys())


def _delete_style_row(
    handler: Any,
    *,
    rid: int,
    row_index: int,
    read_history: Any,
    write_history: Any,
    normalize_record: Any,
    now_iso: Any,
) -> None:
    items = read_history()
    hi = next((i for i, x in enumerate(items) if int(x.get("id", -1)) == rid), None)
    if hi is None:
        handler._send_json(404, {"error": "Not found"})
        return
    record = normalize_record(dict(items[hi]))
    table = record.get("analysis_style_table")
    if not isinstance(table, list):
        table = []
    if row_index < 0 or row_index >= len(table):
        handler._send_json(400, {"error": "Invalid row index"})
        return
    table = table[:row_index] + table[row_index + 1 :]
    record["analysis_style_table"] = table
    record["updated_at"] = now_iso()
    items[hi] = record
    write_history(items)
    handler._send_json(200, record)


def _cleanup_requirement_network_for_history(*, history_id: int, deps: dict[str, Any]) -> None:
    """
    删除某个截图记录对应的向量库数据（requirement_units/edges/embeddings）。
    仅在 MySQL 可用时执行；失败不抛出，避免影响主删除流程。
    """
    try:
        use_mysql_fn = deps.get("use_mysql")
        db_mysql = deps.get("db_mysql")
        if not callable(use_mysql_fn) or not use_mysql_fn():
            return
        if not db_mysql or not hasattr(db_mysql, "get_connection"):
            return
        conn = db_mysql.get_connection()  # type: ignore[attr-defined]
        if conn is None:
            return
        cur = None
        try:
            cur = conn.cursor()
            hid = int(history_id)
            cur.execute("DELETE FROM requirement_embeddings WHERE history_id=%s", (hid,))
            cur.execute("DELETE FROM requirement_edges WHERE history_id=%s", (hid,))
            cur.execute("DELETE FROM requirement_units WHERE history_id=%s", (hid,))
            try:
                conn.commit()
            except Exception:
                pass
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        # 向量清理失败不阻断截图删除
        return


def handle_get(handler: Any, *, path: str, qs: dict[str, Any], deps: dict[str, Any]) -> bool:
    read_history = deps["read_history"]
    write_history = deps["write_history"]
    normalize_record = deps["normalize_record"]
    read_cases = deps["read_cases"]
    normalize_case = deps["normalize_case"]

    if path == "/api/history":
        items = read_history()
        changed = False
        normalized = []
        for r in items:
            before = json.dumps(r, ensure_ascii=False, sort_keys=True)
            nr = normalize_record(r)
            after = json.dumps(nr, ensure_ascii=False, sort_keys=True)
            if before != after:
                changed = True
            normalized.append(nr)
        if changed:
            write_history(normalized)
        handler._send_json(200, normalized)
        return True

    if path.startswith("/api/history/"):
        rest = path[len("/api/history/") :].strip("/")
        parts = [p for p in rest.split("/") if p]
        if len(parts) != 1:
            handler._send_json(400, {"error": "Invalid path"})
            return True
        try:
            rid = int(parts[0])
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        items = read_history()
        found = next((x for x in items if int(x.get("id", -1)) == rid), None)
        if not found:
            handler._send_json(404, {"error": "Not found"})
            return True
        handler._send_json(200, normalize_record(found))
        return True

    if path == "/api/cases":
        if not _require_any_permission(handler, ("menu.case.management", "menu.case.execution")):
            return True
        items = [normalize_case(x) for x in read_cases()]
        hid = (qs.get("history_id") or [None])[0]
        if hid:
            try:
                hid_i = int(hid)
                items = [x for x in items if int(x.get("history_id") or 0) == hid_i]
            except Exception:
                pass
        handler._send_json(200, items)
        return True

    if path.startswith("/api/cases/"):
        if not _require_any_permission(handler, ("menu.case.management", "menu.case.execution")):
            return True
        rest = path[len("/api/cases/") :].strip("/")
        # 仅匹配 /api/cases/{id}，避免误拦截 /api/cases/generate/sse 等子路由
        if "/" in rest or not rest:
            return False
        try:
            cid = int(rest)
        except Exception:
            return False
        items = read_cases()
        found = next((x for x in items if int(x.get("id", -1)) == cid), None)
        if not found:
            handler._send_json(404, {"error": "Not found"})
            return True
        handler._send_json(200, normalize_case(found))
        return True

    return False


def handle_post(handler: Any, *, path: str, deps: dict[str, Any]) -> bool:
    path_clean = path.rstrip("/") or "/"
    parse_json_body = deps["parse_json_body"]
    read_history = deps["read_history"]
    write_history = deps["write_history"]
    normalize_record = deps["normalize_record"]
    now_iso = deps["now_iso"]
    next_history_id = deps["next_history_id"]
    parse_menu_from_filename = deps["parse_menu_from_filename"]
    is_valid_filename = deps["is_valid_filename"]
    read_cases = deps["read_cases"]
    write_cases = deps["write_cases"]
    normalize_case = deps["normalize_case"]
    next_case_id = deps["next_case_id"]
    manual_from_legacy_fields_buttons = deps["manual_from_legacy_fields_buttons"]
    legacy_buttons_fields_from_elements = deps["legacy_buttons_fields_from_elements"]
    extract_upload_stored_name = deps["extract_upload_stored_name"]
    upload_dir: Path = deps["upload_dir"]

    def _history_list() -> list[dict[str, Any]]:
        items = read_history()
        changed = False
        normalized = []
        for r in items:
            before = json.dumps(r, ensure_ascii=False, sort_keys=True)
            nr = normalize_record(r)
            after = json.dumps(nr, ensure_ascii=False, sort_keys=True)
            if before != after:
                changed = True
            normalized.append(nr)
        if changed:
            write_history(normalized)
        return normalized

    def _update_case(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        out = normalize_case(case)
        for k in ["title", "preconditions", "expected", "status", "run_notes", "last_run_at"]:
            if k in payload and isinstance(payload[k], str):
                out[k] = payload[k]
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
            out["run_attachments"] = cleaned
        if "run_records" in payload and isinstance(payload.get("run_records"), list):
            cleaned_records: list[dict[str, Any]] = []
            for it in payload.get("run_records") or []:
                if not isinstance(it, dict):
                    continue
                name = str(it.get("operator_name") or it.get("executor_name") or "").strip()[:128]
                try:
                    op_id_raw = it.get("operator_id")
                    op_id = int(op_id_raw) if op_id_raw not in (None, "") else None
                except Exception:
                    op_id = None
                ts = str(it.get("operation_time") or it.get("time") or "").strip()[:64]
                msg = str(it.get("message") or it.get("msg") or "").strip()
                if not msg:
                    continue
                cleaned_records.append(
                    {
                        "operator_name": name,
                        "operator_id": op_id,
                        "operation_time": ts,
                        "message": msg[:2048],
                    }
                )
            out["run_records"] = cleaned_records
        if "steps" in payload and isinstance(payload["steps"], list):
            out["steps"] = [str(x) for x in payload["steps"] if str(x).strip()]
        if "step_expected" in payload and isinstance(payload.get("step_expected"), list):
            out["step_expected"] = [str(x) if x is not None else "" for x in (payload.get("step_expected") or [])]
        if "history_id" in payload:
            out["history_id"] = payload["history_id"]
        if "priority" in payload:
            out["priority"] = normalize_case_priority(payload.get("priority"))
        merge_case_executor_from_payload(out, payload)
        align_step_expected_to_steps(out)
        out["updated_at"] = now_iso()
        return out

    def _update_history_record(items: list[dict[str, Any]], rid: int, payload: dict[str, Any]) -> tuple[bool, int, dict[str, Any] | None]:
        idx = next((i for i, x in enumerate(items) if int(x.get("id", -1)) == rid), None)
        if idx is None:
            return False, 404, None
        record = items[idx]
        file_name_changed = False

        if "file_name" in payload and isinstance(payload["file_name"], str):
            new_file_name = payload["file_name"].strip()
            old_file_name = record.get("file_name")
            if isinstance(old_file_name, str) and new_file_name:
                if not is_valid_filename(new_file_name):
                    return False, 400, {"error": "Invalid file name"}  # type: ignore[return-value]
                duplicated = any(
                    int(x.get("id", -1)) != rid and str(x.get("file_name") or "").strip() == new_file_name
                    for x in items
                    if isinstance(x, dict)
                )
                if duplicated:
                    return False, 409, {"error": "文件名已存在"}  # type: ignore[return-value]
                record["file_name"] = new_file_name
                record["system_name"], record["menu_structure"] = parse_menu_from_filename(new_file_name)
                file_name_changed = True

        if "menu_structure" in payload and isinstance(payload["menu_structure"], list):
            if not file_name_changed:
                cleaned = []
                for item in payload["menu_structure"]:
                    if not isinstance(item, dict):
                        continue
                    level = item.get("level")
                    name = item.get("name")
                    if isinstance(level, int) and isinstance(name, str):
                        cleaned.append({"level": level, "name": name})
                record["menu_structure"] = cleaned

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
        if "vector_built_at" in payload and isinstance(payload["vector_built_at"], str):
            record["vector_built_at"] = payload["vector_built_at"].strip()
        if "vector_analysis_text" in payload and isinstance(payload["vector_analysis_text"], str):
            record["vector_analysis_text"] = payload["vector_analysis_text"]
        if "vector_build_summary" in payload and isinstance(payload["vector_build_summary"], str):
            record["vector_build_summary"] = payload["vector_build_summary"]
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
                    attr = "其他"
                cleaned_rows.append({"element": el, "attribute": attr, "requirement": req})
            record["analysis_style_table"] = cleaned_rows
        if "manual" in payload and isinstance(payload["manual"], dict):
            m = manual_from_legacy_fields_buttons(payload["manual"])
            lb, lf = legacy_buttons_fields_from_elements(m)
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

        record["updated_at"] = now_iso()
        items[idx] = record
        return True, 200, record

    if path_clean == "/api/history/style-table-row/delete":
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        raw_hid = payload.get("history_id")
        if raw_hid is None:
            raw_hid = payload.get("historyId")
        if raw_hid is None:
            handler._send_json(400, {"error": "history_id required"})
            return True
        try:
            rid = int(raw_hid)
        except Exception:
            handler._send_json(400, {"error": "Invalid history_id"})
            return True
        raw_ri = payload.get("row_index")
        if raw_ri is None:
            raw_ri = payload.get("id")
        if raw_ri is None:
            handler._send_json(400, {"error": "row_index or id required"})
            return True
        try:
            row_index = int(raw_ri)
        except Exception:
            handler._send_json(400, {"error": "Invalid row index"})
            return True
        _delete_style_row(
            handler,
            rid=rid,
            row_index=row_index,
            read_history=read_history,
            write_history=write_history,
            normalize_record=normalize_record,
            now_iso=now_iso,
        )
        return True

    suffix = "/analysis-style-table/delete"
    if path_clean.startswith("/api/history/") and path_clean.endswith(suffix):
        mid = path_clean[len("/api/history/") : -len(suffix)].strip("/")
        if not mid or "/" in mid:
            handler._send_json(400, {"error": "Invalid path"})
            return True
        try:
            rid = int(mid)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        raw_ri = payload.get("row_index")
        if raw_ri is None:
            raw_ri = payload.get("id")
        if raw_ri is None:
            handler._send_json(400, {"error": "row_index or id required"})
            return True
        try:
            row_index = int(raw_ri)
        except Exception:
            handler._send_json(400, {"error": "Invalid row index"})
            return True
        _delete_style_row(
            handler,
            rid=rid,
            row_index=row_index,
            read_history=read_history,
            write_history=write_history,
            normalize_record=normalize_record,
            now_iso=now_iso,
        )
        return True

    if path == "/api/cases":
        if not _require_any_permission(handler, ("menu.case.management",)):
            return True
        ok, payload = _read_json_body_strict(handler)
        if not ok or payload is None:
            handler._send_json(400, {"error": "Invalid JSON"})
            return True
        cases = read_cases()
        cid = next_case_id()
        case = normalize_case(
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
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )
        merge_case_executor_from_payload(case, payload)
        cases.insert(0, case)
        write_cases(cases)
        handler._send_json(201, case)
        return True

    # ---- 新增：统一 POST 风格接口（增删改查）----
    if path_clean == "/api/history/list":
        payload = parse_json_body(handler)
        items = _history_list()
        if isinstance(payload, dict) and payload.get("id") is not None:
            try:
                rid = int(payload.get("id"))
                items = [x for x in items if int(x.get("id", -1)) == rid]
            except Exception:
                handler._send_json(400, {"error": "Invalid id"})
                return True
        if isinstance(payload, dict) and payload.get("system_id") is not None:
            try:
                sid = int(payload.get("system_id"))
                items = [x for x in items if _row_matches_system_id(x, sid)]
            except Exception:
                pass
        handler._send_json(200, items)
        return True

    if path_clean == "/api/history/detail":
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        rid_raw = payload.get("id")
        if rid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            rid = int(rid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        items = _history_list()
        found = next((x for x in items if int(x.get("id", -1)) == rid), None)
        if not found:
            handler._send_json(404, {"error": "Not found"})
            return True
        handler._send_json(200, found)
        return True

    if path_clean == "/api/history/create":
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        file_name = str(payload.get("file_name") or "").strip()
        if not file_name:
            handler._send_json(400, {"error": "file_name required"})
            return True
        if not is_valid_filename(file_name):
            handler._send_json(400, {"error": "Invalid file name"})
            return True
        items = read_history()
        duplicated = any(str(x.get("file_name") or "").strip() == file_name for x in items if isinstance(x, dict))
        if duplicated:
            handler._send_json(409, {"error": "文件名已存在"})
            return True
        rid = next_history_id()
        system_name, menu_structure = parse_menu_from_filename(file_name)
        sys_id = payload.get("system_id")
        if sys_id is not None:
            try:
                sys_id = int(sys_id)
            except (ValueError, TypeError):
                sys_id = None
        record = normalize_record(
            {
                "id": rid,
                "file_name": file_name,
                "file_url": str(payload.get("file_url") or ""),
                "system_name": str(payload.get("system_name") or system_name or "默认系统"),
                "menu_structure": payload.get("menu_structure") if isinstance(payload.get("menu_structure"), list) else menu_structure,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "analysis": str(payload.get("analysis") or ""),
                "system_id": sys_id,
            }
        )
        items.insert(0, record)
        write_history(items)
        handler._send_json(201, record)
        return True

    if path_clean == "/api/history/update":
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        rid_raw = payload.get("id")
        if rid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            rid = int(rid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        items = read_history()
        ok_update, status, record_or_error = _update_history_record(items, rid, payload)
        if not ok_update:
            if isinstance(record_or_error, dict):
                handler._send_json(status, record_or_error)
            else:
                handler._send_json(status, {"error": "Not found"})
            return True
        write_history(items)
        handler._send_json(200, record_or_error)
        return True

    if path_clean == "/api/history/delete":
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        rid_raw = payload.get("id")
        if rid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            rid = int(rid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        items = read_history()
        record = next((x for x in items if int(x.get("id", -1)) == rid), None)
        if not record:
            handler._send_json(404, {"error": "Not found"})
            return True
        items = [x for x in items if int(x.get("id", -1)) != rid]
        write_history(items)
        _cleanup_requirement_network_for_history(history_id=rid, deps=deps)
        try:
            stored_name = extract_upload_stored_name(record.get("file_url"))
            if not stored_name:
                file_name = record.get("file_name")
                stored_name = str(file_name or "").strip() if isinstance(file_name, str) else ""
            if stored_name:
                p = upload_dir / stored_name
                if p.exists() and p.is_file():
                    p.unlink()
        except Exception:
            pass
        handler._send_json(200, {"message": "History record deleted successfully"})
        return True

    if path_clean == "/api/cases/list":
        if not _require_any_permission(handler, ("menu.case.management", "menu.case.execution")):
            return True
        payload = parse_json_body(handler)
        items = [normalize_case(x) for x in read_cases()]
        if isinstance(payload, dict) and payload.get("history_id") is not None:
            try:
                hid = int(payload.get("history_id"))
                items = [x for x in items if int(x.get("history_id") or 0) == hid]
            except Exception:
                handler._send_json(400, {"error": "Invalid history_id"})
                return True
        if isinstance(payload, dict) and payload.get("system_id") is not None:
            try:
                sid = int(payload.get("system_id"))
                items = [x for x in items if _row_matches_system_id(x, sid)]
            except Exception:
                pass
        handler._send_json(200, items)
        return True

    if path_clean == "/api/cases/detail":
        if not _require_any_permission(handler, ("menu.case.management", "menu.case.execution")):
            return True
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        cid_raw = payload.get("id")
        if cid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            cid = int(cid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        items = read_cases()
        found = next((x for x in items if int(x.get("id", -1)) == cid), None)
        if not found:
            handler._send_json(404, {"error": "Not found"})
            return True
        handler._send_json(200, normalize_case(found))
        return True

    if path_clean == "/api/cases/create":
        if not _require_any_permission(handler, ("menu.case.management",)):
            return True
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        cases = read_cases()
        cid = next_case_id()
        case_sys_id = payload.get("system_id")
        if case_sys_id is not None:
            try:
                case_sys_id = int(case_sys_id)
            except (ValueError, TypeError):
                case_sys_id = None
        case = normalize_case(
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
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "system_id": case_sys_id,
            }
        )
        merge_case_executor_from_payload(case, payload)
        cases.insert(0, case)
        write_cases(cases)
        handler._send_json(201, case)
        return True

    if path_clean == "/api/cases/update":
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        if _case_update_is_execution_only(payload):
            if not _require_any_permission(handler, ("action.case.execute",)):
                return True
        elif not _require_any_permission(handler, ("menu.case.management", "action.case.edit")):
            return True
        cid_raw = payload.get("id")
        if cid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            cid = int(cid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        cases = read_cases()
        idx = next((i for i, x in enumerate(cases) if int(x.get("id", -1)) == cid), None)
        if idx is None:
            handler._send_json(404, {"error": "Not found"})
            return True
        case = _update_case(cases[idx], payload)
        cases[idx] = case
        write_cases(cases)
        handler._send_json(200, case)
        return True

    if path_clean == "/api/cases/delete":
        if not _require_any_permission(handler, ("action.case.delete",)):
            return True
        payload = parse_json_body(handler)
        if not isinstance(payload, dict):
            handler._send_json(400, {"error": "Invalid payload"})
            return True
        cid_raw = payload.get("id")
        if cid_raw is None:
            handler._send_json(400, {"error": "id required"})
            return True
        try:
            cid = int(cid_raw)
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        cases = read_cases()
        if not any(int(x.get("id", -1)) == cid for x in cases):
            handler._send_json(404, {"error": "Not found"})
            return True
        cases = [x for x in cases if int(x.get("id", -1)) != cid]
        write_cases(cases)
        handler._send_json(200, {"message": "Case deleted successfully"})
        return True

    return False


def handle_put(handler: Any, *, path: str, deps: dict[str, Any]) -> bool:
    read_cases = deps["read_cases"]
    write_cases = deps["write_cases"]
    normalize_case = deps["normalize_case"]
    read_history = deps["read_history"]
    write_history = deps["write_history"]
    now_iso = deps["now_iso"]
    is_valid_filename = deps["is_valid_filename"]
    parse_menu_from_filename = deps["parse_menu_from_filename"]
    manual_from_legacy_fields_buttons = deps["manual_from_legacy_fields_buttons"]
    legacy_buttons_fields_from_elements = deps["legacy_buttons_fields_from_elements"]

    if path.startswith("/api/cases/"):
        if not _require_any_permission(handler, ("menu.case.management", "action.case.execute")):
            return True
        try:
            cid = int(path[len("/api/cases/") :])
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        ok, payload = _read_json_body_strict(handler)
        if not ok or payload is None:
            handler._send_json(400, {"error": "Invalid JSON"})
            return True
        if _case_update_is_execution_only(payload):
            if not _require_any_permission(handler, ("action.case.execute",)):
                return True
        elif not _require_any_permission(handler, ("menu.case.management", "action.case.edit")):
            return True
        cases = read_cases()
        idx = next((i for i, x in enumerate(cases) if int(x.get("id", -1)) == cid), None)
        if idx is None:
            handler._send_json(404, {"error": "Not found"})
            return True
        case = normalize_case(cases[idx])
        for k in ["title", "preconditions", "expected", "status", "run_notes", "last_run_at"]:
            if k in payload and isinstance(payload[k], str):
                case[k] = payload[k]
        if "steps" in payload and isinstance(payload["steps"], list):
            case["steps"] = [str(x) for x in payload["steps"] if str(x).strip()]
        if "step_expected" in payload and isinstance(payload.get("step_expected"), list):
            case["step_expected"] = [str(x) if x is not None else "" for x in (payload.get("step_expected") or [])]
        if "history_id" in payload:
            case["history_id"] = payload["history_id"]
        if "priority" in payload:
            case["priority"] = normalize_case_priority(payload.get("priority"))
        merge_case_executor_from_payload(case, payload)
        align_step_expected_to_steps(case)
        case["updated_at"] = now_iso()
        cases[idx] = case
        write_cases(cases)
        handler._send_json(200, case)
        return True

    if not path.startswith("/api/history/"):
        return False

    rest = path[len("/api/history/") :].strip("/")
    parts = [p for p in rest.split("/") if p]
    if len(parts) != 1:
        handler._send_json(400, {"error": "Invalid path"})
        return True
    try:
        rid = int(parts[0])
    except Exception:
        handler._send_json(400, {"error": "Invalid id"})
        return True

    ok, payload = _read_json_body_strict(handler)
    if not ok or payload is None:
        handler._send_json(400, {"error": "Invalid JSON"})
        return True

    items = read_history()
    idx = next((i for i, x in enumerate(items) if int(x.get("id", -1)) == rid), None)
    if idx is None:
        handler._send_json(404, {"error": "Not found"})
        return True

    record = items[idx]
    file_name_changed = False
    if isinstance(payload, dict):
        if "file_name" in payload and isinstance(payload["file_name"], str):
            new_file_name = payload["file_name"].strip()
            old_file_name = record.get("file_name")
            if isinstance(old_file_name, str) and new_file_name:
                if not is_valid_filename(new_file_name):
                    handler._send_json(400, {"error": "Invalid file name"})
                    return True
                duplicated = any(
                    int(x.get("id", -1)) != rid and str(x.get("file_name") or "").strip() == new_file_name
                    for x in items
                    if isinstance(x, dict)
                )
                if duplicated:
                    handler._send_json(409, {"error": "文件名已存在"})
                    return True
                record["file_name"] = new_file_name
                record["system_name"], record["menu_structure"] = parse_menu_from_filename(new_file_name)
                file_name_changed = True

        if "menu_structure" in payload and isinstance(payload["menu_structure"], list):
            if not file_name_changed:
                cleaned = []
                for item in payload["menu_structure"]:
                    if not isinstance(item, dict):
                        continue
                    level = item.get("level")
                    name = item.get("name")
                    if isinstance(level, int) and isinstance(name, str):
                        cleaned.append({"level": level, "name": name})
                record["menu_structure"] = cleaned

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
        if "vector_built_at" in payload and isinstance(payload["vector_built_at"], str):
            record["vector_built_at"] = payload["vector_built_at"].strip()
        if "vector_analysis_text" in payload and isinstance(payload["vector_analysis_text"], str):
            record["vector_analysis_text"] = payload["vector_analysis_text"]
        if "vector_build_summary" in payload and isinstance(payload["vector_build_summary"], str):
            record["vector_build_summary"] = payload["vector_build_summary"]
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
                    attr = "其他"
                cleaned_rows.append({"element": el, "attribute": attr, "requirement": req})
            record["analysis_style_table"] = cleaned_rows
        if "manual" in payload and isinstance(payload["manual"], dict):
            m = manual_from_legacy_fields_buttons(payload["manual"])
            lb, lf = legacy_buttons_fields_from_elements(m)
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

    record["updated_at"] = now_iso()
    items[idx] = record
    write_history(items)
    handler._send_json(200, record)
    return True


def handle_delete(handler: Any, *, path: str, deps: dict[str, Any]) -> bool:
    read_cases = deps["read_cases"]
    write_cases = deps["write_cases"]
    read_history = deps["read_history"]
    write_history = deps["write_history"]
    now_iso = deps["now_iso"]
    normalize_record = deps["normalize_record"]
    extract_upload_stored_name = deps["extract_upload_stored_name"]
    upload_dir: Path = deps["upload_dir"]

    if path.startswith("/api/cases/"):
        if not _require_any_permission(handler, ("action.case.delete",)):
            return True
        try:
            cid = int(path[len("/api/cases/") :])
        except Exception:
            handler._send_json(400, {"error": "Invalid id"})
            return True
        cases = read_cases()
        if not any(int(x.get("id", -1)) == cid for x in cases):
            handler._send_json(404, {"error": "Not found"})
            return True
        cases = [x for x in cases if int(x.get("id", -1)) != cid]
        write_cases(cases)
        handler._send_json(200, {"message": "Case deleted successfully"})
        return True

    if not path.startswith("/api/history/"):
        return False

    rest = path[len("/api/history/") :].strip("/")
    if not rest:
        handler._send_json(400, {"error": "Invalid path"})
        return True
    parts = [p for p in rest.split("/") if p]

    if len(parts) == 3 and parts[1] == "analysis-style-table":
        try:
            rid = int(parts[0])
            row_index = int(parts[2])
        except Exception:
            handler._send_json(400, {"error": "Invalid id or row index"})
            return True
        _delete_style_row(
            handler,
            rid=rid,
            row_index=row_index,
            read_history=read_history,
            write_history=write_history,
            normalize_record=normalize_record,
            now_iso=now_iso,
        )
        return True

    if len(parts) != 1:
        handler._send_text(404, "Not found")
        return True
    try:
        rid = int(parts[0])
    except Exception:
        handler._send_json(400, {"error": "Invalid id"})
        return True

    items = read_history()
    record = next((x for x in items if int(x.get("id", -1)) == rid), None)
    if not record:
        handler._send_json(404, {"error": "Not found"})
        return True

    items = [x for x in items if int(x.get("id", -1)) != rid]
    write_history(items)
    _cleanup_requirement_network_for_history(history_id=rid, deps=deps)

    try:
        stored_name = extract_upload_stored_name(record.get("file_url"))
        if not stored_name:
            file_name = record.get("file_name")
            stored_name = str(file_name or "").strip() if isinstance(file_name, str) else ""
        if stored_name:
            p = upload_dir / stored_name
            if p.exists() and p.is_file():
                p.unlink()
    except Exception:
        pass

    handler._send_json(200, {"message": "History record deleted successfully"})
    return True
