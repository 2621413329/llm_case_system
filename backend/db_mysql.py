#!/usr/bin/env python3
"""
MySQL 持久化层：库 llm_case_system，表 screenshot_history / test_cases / page_elements。
配置来自 config.local.json 的 mysql 段；未配置或连接失败时由 simple_server 回退到 JSON 文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.local.json"
HISTORY_PATH = PROJECT_ROOT / "data" / "history.json"
CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
DB_NAME = "llm_case_system"


def _read_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_mysql_config() -> dict[str, Any] | None:
    cfg = _read_config()
    mysql = cfg.get("mysql")
    if not isinstance(mysql, dict):
        return None
    host = mysql.get("host") or "127.0.0.1"
    port = int(mysql.get("port") or 3306)
    user = mysql.get("user") or "root"
    password = mysql.get("password") or ""
    database = mysql.get("database") or DB_NAME
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def get_connection(use_db: bool = True):
    """获取连接。use_db=True 时连接到 llm_case_system；False 时用于创建库。"""
    cfg = _get_mysql_config()
    if not cfg:
        return None

    # 优先使用 pymysql（纯 Python），避免 mysql-connector-python 在部分环境崩溃/兼容性问题
    try:
        import pymysql  # type: ignore

        conn_kwargs = dict(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5,
        )
        if use_db:
            conn_kwargs["database"] = cfg["database"]
        return pymysql.connect(**conn_kwargs)
    except Exception:
        pass

    # 兜底：尝试 mysql-connector-python（如果 pymysql 不可用）
    try:
        import mysql.connector  # type: ignore
    except ImportError:
        return None

    try:
        if use_db:
            return mysql.connector.connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                charset="utf8mb4",
                autocommit=True,
            )
        return mysql.connector.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            charset="utf8mb4",
            autocommit=True,
        )
    except Exception:
        return None


def is_available() -> bool:
    """MySQL 已配置且可连接（库可不存在，仅测连接）。"""
    conn = get_connection(use_db=False)
    if conn is None:
        return False
    try:
        conn.ping(reconnect=False)
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_database() -> tuple[bool, str]:
    """
    创建数据库 llm_case_system 及表结构。
    返回 (成功, 消息)。
    """
    cfg = _get_mysql_config()
    if not cfg:
        return False, "MySQL not configured in config.local.json"
    conn = get_connection(use_db=False)
    if conn is None:
        return False, "Cannot connect to MySQL (check host/user/password)"
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{DB_NAME}`")

        # 截图历史表（与 data/history.json 结构对应）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS screenshot_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_name VARCHAR(512) NOT NULL DEFAULT '',
                file_url VARCHAR(1024) NOT NULL DEFAULT '',
                system_name VARCHAR(256) NOT NULL DEFAULT '默认系统',
                menu_structure JSON NULL COMMENT '[{level, name}, ...]',
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                analysis TEXT,
                analysis_style TEXT NULL,
                analysis_content TEXT NULL,
                analysis_interaction TEXT NULL,
                analysis_data JSON NULL,
                analysis_generated_at VARCHAR(64) NOT NULL DEFAULT '',
                manual JSON NULL COMMENT '{page_type, page_elements, buttons, fields, text_requirements, control_logic}'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        # 页面元素表（支持元素级增删改查审计）
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS page_elements (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                history_id INT NOT NULL,
                element_name VARCHAR(255) NOT NULL DEFAULT '',
                element_type VARCHAR(64) NOT NULL DEFAULT 'other',
                ui_pattern VARCHAR(128) NOT NULL DEFAULT '',
                required_flag TINYINT(1) NOT NULL DEFAULT 0,
                queryable_flag TINYINT(1) NOT NULL DEFAULT 0,
                validation_rule TEXT,
                min_len VARCHAR(32) NULL DEFAULT '',
                max_len VARCHAR(32) NULL DEFAULT '',
                action_name VARCHAR(64) NULL DEFAULT '',
                opens_modal TINYINT(1) NOT NULL DEFAULT 0,
                requires_confirm TINYINT(1) NOT NULL DEFAULT 0,
                source_name VARCHAR(64) NULL DEFAULT '',
                source_text TEXT,
                raw_text LONGTEXT,
                notes TEXT,
                options_json JSON NULL,
                attrs_json JSON NULL,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                INDEX idx_page_elements_history_id (history_id),
                INDEX idx_page_elements_type (element_type),
                INDEX idx_page_elements_name (element_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        # 兼容旧库：如果缺少新字段，自动补齐
        for alter_sql in [
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS manual JSON NULL COMMENT '{page_type, page_elements, buttons, fields, text_requirements, control_logic}'",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_style TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_content TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_interaction TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_data JSON NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_generated_at VARCHAR(64) NOT NULL DEFAULT ''",
        ]:
            try:
                cur.execute(alter_sql)
            except Exception:
                pass

        # 测试用例表（与 data/cases.json 结构对应）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_cases (
                id INT AUTO_INCREMENT PRIMARY KEY,
                history_id INT NULL,
                title VARCHAR(512) NOT NULL DEFAULT '',
                preconditions TEXT,
                steps JSON NULL COMMENT '["step1","step2",...]',
                expected TEXT,
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                last_run_at VARCHAR(64) NULL DEFAULT '',
                run_notes TEXT,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                INDEX idx_history_id (history_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # 需求网络库（向量检索所需的结构化原子单元 + 关系 + 向量嵌入）
        # 设计目标：单元以 unit_key 唯一标识；content/metadata 用于 UI 回填；embedding 用于相似检索。
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS requirement_units (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                history_id INT NOT NULL,
                unit_key VARCHAR(255) NOT NULL,
                unit_type VARCHAR(64) NOT NULL,
                content LONGTEXT NOT NULL,
                metadata JSON NULL,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                UNIQUE KEY uq_history_unit_key (history_id, unit_key),
                INDEX idx_units_history_id (history_id),
                INDEX idx_units_type (unit_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS requirement_edges (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                history_id INT NOT NULL,
                from_unit_key VARCHAR(255) NOT NULL,
                to_unit_key VARCHAR(255) NOT NULL,
                relation_type VARCHAR(64) NOT NULL,
                metadata JSON NULL,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                INDEX idx_edges_history_id (history_id),
                INDEX idx_edges_from (from_unit_key),
                INDEX idx_edges_to (to_unit_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS requirement_embeddings (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                history_id INT NOT NULL,
                unit_key VARCHAR(255) NOT NULL,
                embedding JSON NOT NULL,
                embedding_model VARCHAR(128) NOT NULL DEFAULT '',
                dim INT NOT NULL DEFAULT 0,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                UNIQUE KEY uq_history_unit_key (history_id, unit_key),
                INDEX idx_embeddings_history_id (history_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )

        # 兼容旧库：如果表已存在但字段缺失，尝试补齐（不影响正常运行）
        for alter_sql in [
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS metadata JSON NULL",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS metadata JSON NULL",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(128) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS dim INT NOT NULL DEFAULT 0",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
        ]:
            try:
                cur.execute(alter_sql)
            except Exception:
                pass
        # 若表为空，则从本地 JSON 迁移一份，避免切到 MySQL 后历史记录突然变空
        try:
            cur.execute("SELECT COUNT(*) FROM screenshot_history")
            screenshot_count = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*) FROM test_cases")
            cases_count = int(cur.fetchone()[0] or 0)
        except Exception:
            screenshot_count = -1
            cases_count = -1

        def _load_list(p: Path) -> list[dict[str, Any]]:
            if not p.exists():
                return []
            try:
                raw = p.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
            except Exception:
                pass
            return []

        # 注意：迁移时会触发 write_history/write_cases 内部的 DELETE+INSERT
        if screenshot_count == 0:
            items = _load_list(HISTORY_PATH)
            if items:
                try:
                    write_history(items)
                except Exception:
                    # 迁移失败不影响建表成功
                    pass
        if cases_count == 0:
            items = _load_list(CASES_PATH)
            if items:
                try:
                    write_cases(items)
                except Exception:
                    pass

        return True, f"Database {DB_NAME} and tables created successfully"
    except Exception as e:
        return False, str(e)
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


def _row_to_history(row: tuple) -> dict[str, Any]:
    """将 screenshot_history 一行转为与 JSON 一致的 dict。"""
    (
        id_,
        file_name,
        file_url,
        system_name,
        menu_structure,
        created_at,
        updated_at,
        analysis,
        analysis_style,
        analysis_content,
        analysis_interaction,
        analysis_data,
        analysis_generated_at,
        manual,
    ) = row
    out = {
        "id": id_,
        "file_name": file_name or "",
        "file_url": file_url or "",
        "system_name": system_name or "默认系统",
        "menu_structure": menu_structure if isinstance(menu_structure, list) else (json.loads(menu_structure) if isinstance(menu_structure, str) else []),
        "created_at": created_at or "",
        "updated_at": updated_at or "",
        "analysis": analysis or "",
        "analysis_style": analysis_style or "",
        "analysis_content": analysis_content or "",
        "analysis_interaction": analysis_interaction or "",
        "analysis_data": (
            analysis_data
            if isinstance(analysis_data, (dict, list))
            else (json.loads(analysis_data) if isinstance(analysis_data, str) and analysis_data.strip() else None)
        ),
        "analysis_generated_at": analysis_generated_at or "",
        "manual": manual if isinstance(manual, dict) else (json.loads(manual) if isinstance(manual, str) and manual else {}),
    }
    return out


def _row_to_case(row: tuple) -> dict[str, Any]:
    """将 test_cases 一行转为与 JSON 一致的 dict。"""
    (
        id_,
        history_id,
        title,
        preconditions,
        steps,
        expected,
        status,
        last_run_at,
        run_notes,
        created_at,
        updated_at,
    ) = row
    return {
        "id": id_,
        "history_id": history_id,
        "title": title or "",
        "preconditions": preconditions or "",
        "steps": steps if isinstance(steps, list) else (json.loads(steps) if isinstance(steps, str) and steps else []),
        "expected": expected or "",
        "status": status or "draft",
        "last_run_at": last_run_at or "",
        "run_notes": run_notes or "",
        "created_at": created_at or "",
        "updated_at": updated_at or "",
    }


def read_history() -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, file_name, file_url, system_name, menu_structure, created_at, updated_at, analysis, analysis_style, analysis_content, analysis_interaction, analysis_data, analysis_generated_at, manual FROM screenshot_history ORDER BY id DESC"
        )
        rows = cur.fetchall()
        cur.close()
        return [_row_to_history(r) for r in rows]
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def write_history(items: list[dict[str, Any]]) -> None:
    conn = get_connection()
    if conn is None:
        return
    try:
        cur = conn.cursor()
        # 为避免“服务已升级但数据库列尚未同步”的情况，写入前确保分析字段存在
        try:
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_style TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_content TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_interaction TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_data JSON NULL")
            cur.execute(
                "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_generated_at VARCHAR(64) NOT NULL DEFAULT ''"
            )
        except Exception:
            # 若表结构已完整，或 ALTER 不被允许，忽略；后续 INSERT 会报错并由上层处理
            pass
        cur.execute("DELETE FROM screenshot_history")
        cur.execute("DELETE FROM page_elements")
        for r in items:
            mid = json.dumps(r.get("menu_structure") or [], ensure_ascii=False) if isinstance(r.get("menu_structure"), list) else "[]"
            man = r.get("manual")
            man_str = json.dumps(man, ensure_ascii=False) if isinstance(man, dict) else "{}"
            analysis_data = r.get("analysis_data")
            analysis_data_str = json.dumps(analysis_data, ensure_ascii=False) if isinstance(analysis_data, (dict, list)) else None
            cur.execute(
                """INSERT INTO screenshot_history
                   (id, file_name, file_url, system_name, menu_structure, created_at, updated_at, analysis,
                    analysis_style, analysis_content, analysis_interaction, analysis_data, analysis_generated_at, manual)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    int(r.get("id", 0)),
                    (r.get("file_name") or "")[:512],
                    (r.get("file_url") or "")[:1024],
                    (r.get("system_name") or "默认系统")[:256],
                    mid,
                    r.get("created_at") or "",
                    r.get("updated_at") or "",
                    r.get("analysis") or "",
                    r.get("analysis_style") or "",
                    r.get("analysis_content") or "",
                    r.get("analysis_interaction") or "",
                    analysis_data_str,
                    r.get("analysis_generated_at") or "",
                    man_str,
                ),
            )
            # 同步 page_elements（冗余建模，便于后续按元素维度统计/查询）
            if isinstance(man, dict) and isinstance(man.get("page_elements"), list):
                for e in man.get("page_elements"):
                    if not isinstance(e, dict):
                        continue
                    ename = str(e.get("name") or "").strip()
                    if not ename:
                        continue
                    options_json = json.dumps(e.get("options") if isinstance(e.get("options"), list) else [], ensure_ascii=False)
                    attrs_json = json.dumps(e, ensure_ascii=False)
                    cur.execute(
                        """INSERT INTO page_elements
                        (history_id, element_name, element_type, ui_pattern, required_flag, queryable_flag, validation_rule,
                         min_len, max_len, action_name, opens_modal, requires_confirm, source_name, source_text, raw_text, notes,
                         options_json, attrs_json, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            int(r.get("id", 0)),
                            ename[:255],
                            (str(e.get("element_type") or "other").strip() or "other")[:64],
                            (str(e.get("ui_pattern") or "").strip())[:128],
                            1 if bool(e.get("required")) else 0,
                            1 if bool(e.get("queryable")) else 0,
                            str(e.get("validation") or ""),
                            str(e.get("min_len") if e.get("min_len") is not None else ""),
                            str(e.get("max_len") if e.get("max_len") is not None else ""),
                            (str(e.get("action") or "").strip())[:64],
                            1 if bool(e.get("opens_modal")) else 0,
                            1 if bool(e.get("requires_confirm")) else 0,
                            (str(e.get("source") or "").strip())[:64],
                            str(e.get("source_text") or ""),
                            str(e.get("raw_text") or ""),
                            str(e.get("notes") or ""),
                            options_json,
                            attrs_json,
                            r.get("created_at") or "",
                            r.get("updated_at") or "",
                        ),
                    )
        cur.close()
    except Exception:
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def write_requirement_network(
    history_id: int,
    units: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    embeddings: dict[str, list[float]] | None,
    *,
    embedding_model: str = "",
) -> None:
    """
    写入需求网络库：先清空同 history_id 的旧数据，再插入 units/edges/embeddings。
    embeddings 以 unit_key -> embedding_vector 的形式传入。
    """
    conn = get_connection()
    if conn is None:
        return
    try:
        cur = conn.cursor()
        # 清空同一页面作用域的旧网络数据，保证覆盖式生成
        cur.execute("DELETE FROM requirement_embeddings WHERE history_id=%s", (int(history_id),))
        cur.execute("DELETE FROM requirement_edges WHERE history_id=%s", (int(history_id),))
        cur.execute("DELETE FROM requirement_units WHERE history_id=%s", (int(history_id),))

        # units
        for u in units:
            if not isinstance(u, dict):
                continue
            unit_key = str(u.get("unit_key") or "").strip()
            unit_type = str(u.get("unit_type") or "other").strip()
            content = str(u.get("content") or "").strip()
            if not unit_key or not content:
                continue
            metadata = u.get("metadata")
            metadata_str = json.dumps(metadata, ensure_ascii=False) if isinstance(metadata, (dict, list)) else None
            created_at = str(u.get("created_at") or "")
            updated_at = str(u.get("updated_at") or "")
            cur.execute(
                """INSERT INTO requirement_units
                   (history_id, unit_key, unit_type, content, metadata, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (int(history_id), unit_key[:255], unit_type[:64], content, metadata_str, created_at, updated_at),
            )

        # edges
        for e in edges:
            if not isinstance(e, dict):
                continue
            from_key = str(e.get("from_unit_key") or "").strip()
            to_key = str(e.get("to_unit_key") or "").strip()
            relation_type = str(e.get("relation_type") or "related").strip()
            if not from_key or not to_key:
                continue
            metadata = e.get("metadata")
            metadata_str = json.dumps(metadata, ensure_ascii=False) if isinstance(metadata, (dict, list)) else None
            created_at = str(e.get("created_at") or "")
            updated_at = str(e.get("updated_at") or "")
            cur.execute(
                """INSERT INTO requirement_edges
                   (history_id, from_unit_key, to_unit_key, relation_type, metadata, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (int(history_id), from_key[:255], to_key[:255], relation_type[:64], metadata_str, created_at, updated_at),
            )

        # embeddings
        if embeddings and isinstance(embeddings, dict):
            for unit_key, vec in embeddings.items():
                if not unit_key:
                    continue
                if not isinstance(vec, list) or not vec:
                    continue
                try:
                    vec_f = [float(x) for x in vec]
                except Exception:
                    continue
                embedding_str = json.dumps(vec_f, ensure_ascii=False)
                cur.execute(
                    """INSERT INTO requirement_embeddings
                       (history_id, unit_key, embedding, embedding_model, dim, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        int(history_id),
                        str(unit_key)[:255],
                        embedding_str,
                        str(embedding_model or "")[:128],
                        int(len(vec_f)),
                        "",
                        "",
                    ),
                )

        cur.close()
    except Exception:
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def read_requirement_network_for_search(
    history_id: int | None = None,
    unit_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    为向量检索服务：读取所有/指定历史/指定 unit_type 的 embedding + metadata。
    返回：
    [
      {history_id, unit_key, unit_type, content, metadata, embedding:[...]}
    ]
    """
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        where = []
        params: list[Any] = []
        if history_id is not None:
            where.append("re.history_id=%s")
            params.append(int(history_id))
        if unit_type:
            where.append("u.unit_type=%s")
            params.append(str(unit_type)[:64])
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        cur.execute(
            f"""
            SELECT u.history_id, u.unit_key, u.unit_type, u.content, u.metadata, re.embedding, re.embedding_model
            FROM requirement_units u
            JOIN requirement_embeddings re
              ON re.history_id=u.history_id AND re.unit_key=u.unit_key
            {where_sql}
            """,
            tuple(params),
        )
        rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            (hid, unit_key, ut, content, metadata, embedding, embedding_model) = r
            meta_obj = metadata if isinstance(metadata, (dict, list)) else (json.loads(metadata) if isinstance(metadata, str) and metadata else None)
            emb_obj = embedding if isinstance(embedding, list) else (json.loads(embedding) if isinstance(embedding, str) and embedding else [])
            out.append(
                {
                    "history_id": hid,
                    "unit_key": unit_key,
                    "unit_type": ut,
                    "content": content or "",
                    "metadata": meta_obj,
                    "embedding": emb_obj,
                    "embedding_model": embedding_model or "",
                }
            )
        cur.close()
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def next_history_id() -> int:
    conn = get_connection()
    if conn is None:
        return 1
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screenshot_history")
        row = cur.fetchone()
        cur.close()
        return int(row[0]) if row else 1
    except Exception:
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


def read_cases() -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, history_id, title, preconditions, steps, expected, status, last_run_at, run_notes, created_at, updated_at FROM test_cases ORDER BY id DESC"
        )
        rows = cur.fetchall()
        cur.close()
        return [_row_to_case(r) for r in rows]
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def write_cases(items: list[dict[str, Any]]) -> None:
    conn = get_connection()
    if conn is None:
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM test_cases")
        for c in items:
            steps_str = json.dumps(c.get("steps") or [], ensure_ascii=False) if isinstance(c.get("steps"), list) else "[]"
            cur.execute(
                """INSERT INTO test_cases (id, history_id, title, preconditions, steps, expected, status, last_run_at, run_notes, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    int(c.get("id", 0)),
                    c.get("history_id") if c.get("history_id") is not None else None,
                    (c.get("title") or "")[:512],
                    c.get("preconditions") or "",
                    steps_str,
                    c.get("expected") or "",
                    (c.get("status") or "draft")[:32],
                    (c.get("last_run_at") or "")[:64],
                    c.get("run_notes") or "",
                    c.get("created_at") or "",
                    c.get("updated_at") or "",
                ),
            )
        cur.close()
    except Exception:
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def next_case_id() -> int:
    conn = get_connection()
    if conn is None:
        return 1
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM test_cases")
        row = cur.fetchone()
        cur.close()
        return int(row[0]) if row else 1
    except Exception:
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass
