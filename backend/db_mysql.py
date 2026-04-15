#!/usr/bin/env python3
"""
MySQL 持久化层：库 llm_case_system，表 screenshot_history / test_cases / page_elements。
配置来自 load_config()（config/default.yaml、config.local.json、config/local.yaml、config/local.json 等）的 mysql 段；未配置或连接失败时由 simple_server 回退到 JSON 文件。
"""

from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = PROJECT_ROOT / "data" / "history.json"
CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
DB_NAME = "llm_case_system"


def _parse_embedding_column(raw: Any) -> list[float]:
    """
    解析 requirement_embeddings.embedding。
    不同驱动/字段类型可能返回 list、str、bytes（JSON 文本）；仅 list 会导致其它类型被读成空向量。
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        try:
            return [float(x) for x in raw]
        except Exception:
            return []
    if isinstance(raw, (bytes, bytearray, memoryview)):
        try:
            b = bytes(raw)
            if not b.strip():
                return []
            parsed = json.loads(b.decode("utf-8", errors="replace"))
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except Exception:
            return []
        return []
    if isinstance(raw, str):
        try:
            s = raw.strip()
            if not s:
                return []
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except Exception:
            return []
        return []
    if isinstance(raw, tuple):
        try:
            return [float(x) for x in raw]
        except Exception:
            return []
    return []

# 与前端 router / App.vue / can() 对齐的权限码
AUTH_PERMISSION_SEED: list[tuple[str, str, str]] = [
    ("*", "全部功能", "拥有所有菜单与操作（仅建议赋给管理员角色）"),
    ("menu.system", "系统管理", "显示系统管理一级菜单"),
    ("menu.system.list", "系统列表", "访问系统列表页"),
    ("menu.analysis", "分析系统", "显示分析系统一级菜单"),
    ("menu.analysis.upload", "上传截图", "上传系统样式截图"),
    ("menu.analysis.requirement_library", "需求分析库", "系统需求分析库"),
    ("menu.preview", "系统预览", "显示系统预览一级菜单"),
    ("menu.preview.gallery", "截图预览", "截图预览页"),
    ("menu.case", "用例管理", "显示用例管理一级菜单"),
    ("menu.case.management", "用例管理页", "用例管理（生成/库）"),
    ("menu.case.execution", "执行用例", "执行用例页"),
    ("action.upload", "上传文件", "调用上传接口"),
    ("action.history.delete", "删除截图", "删除截图记录"),
    ("action.case.delete", "删除用例", "删除测试用例"),
    ("action.case.edit", "编辑用例", "编辑测试用例内容"),
    ("action.case.execute", "记录执行", "提交用例执行结果"),
    ("action.requirement.vector_build", "构建向量库", "构建需求网络/向量"),
]

ADMIN_ROLE_CODE = "admin"
OPERATOR_ROLE_CODE = "operator"
SUPER_ADMIN_USERNAME = "root"
SUPER_ADMIN_PASSWORD = "root"
RESERVED_USERNAMES = {"root", "admin"}
OPERATOR_PERMISSION_CODES = (
    "menu.case",
    "menu.case.execution",
    "action.case.edit",
    "action.case.execute",
    # 普通业务人员可“选择系统”（读取系统列表/详情），但不具备系统新建/编辑/删除权限
    # （后端系统管理写接口需要 menu.system 且 menu.system.list 同时具备）
    "menu.system.list",
)

try:
    from backend.config.loader import load_config as _load_config
except Exception:
    try:
        from config.loader import load_config as _load_config  # type: ignore
    except Exception:
        _load_config = None


def _read_config() -> dict[str, Any]:
    if callable(_load_config):
        try:
            return _load_config()
        except Exception:
            return {}
    # fallback: loader 不可用时兼容旧配置文件
    legacy = PROJECT_ROOT / "config.local.json"
    if not legacy.exists():
        return {}
    try:
        return json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_mysql_config() -> dict[str, Any] | None:
    cfg = _read_config()
    mysql = cfg.get("mysql")
    if not isinstance(mysql, dict):
        return None
    if mysql.get("enabled") is False:
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


def _permission_id_by_code(cur, code: str) -> int | None:
    cur.execute("SELECT id FROM permissions WHERE code=%s", (str(code or "").strip(),))
    row = cur.fetchone()
    return int(row[0]) if row else None


def _ensure_role(cur, code: str, name: str) -> int | None:
    ts = str(int(time.time()))
    cur.execute(
        """
        INSERT INTO roles (code, name, created_at, updated_at)
        VALUES (%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE name=VALUES(name), updated_at=VALUES(updated_at)
        """,
        (code, name, ts, ts),
    )
    cur.execute("SELECT id FROM roles WHERE code=%s", (code,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def _sync_role_permissions(cur, role_id: int, permission_codes: tuple[str, ...] | list[str]) -> None:
    code_set = {str(code or "").strip() for code in permission_codes if str(code or "").strip()}
    allowed_ids: list[int] = []
    for code in code_set:
        pid = _permission_id_by_code(cur, code)
        if pid is not None:
            allowed_ids.append(pid)
            cur.execute(
                "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s,%s)",
                (int(role_id), int(pid)),
            )
    if allowed_ids:
        placeholders = ",".join(["%s"] * len(allowed_ids))
        cur.execute(
            f"DELETE FROM role_permissions WHERE role_id=%s AND permission_id NOT IN ({placeholders})",
            (int(role_id), *allowed_ids),
        )
    else:
        cur.execute("DELETE FROM role_permissions WHERE role_id=%s", (int(role_id),))


def _ensure_super_admin_account(cur, admin_role_id: int | None) -> None:
    if admin_role_id is None:
        return
    try:
        from backend.auth_password import hash_password
    except Exception:
        from auth_password import hash_password  # type: ignore

    ts = str(int(time.time()))
    pwd = hash_password(SUPER_ADMIN_PASSWORD)
    cur.execute("SELECT id FROM users WHERE username=%s", (SUPER_ADMIN_USERNAME,))
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE users
            SET password_hash=%s, display_name=%s, role_id=%s, is_active=1, updated_at=%s
            WHERE id=%s
            """,
            (pwd, "系统超级管理员", int(admin_role_id), ts, int(row[0])),
        )
        return

    cur.execute("SELECT id FROM users WHERE username=%s", ("admin",))
    legacy_row = cur.fetchone()
    if legacy_row:
        cur.execute(
            """
            UPDATE users
            SET username=%s, password_hash=%s, display_name=%s, role_id=%s, is_active=1, updated_at=%s
            WHERE id=%s
            """,
            (SUPER_ADMIN_USERNAME, pwd, "系统超级管理员", int(admin_role_id), ts, int(legacy_row[0])),
        )
        return

    cur.execute(
        """
        INSERT INTO users (username, password_hash, display_name, role_id, is_active, created_at, updated_at)
        VALUES (%s,%s,%s,%s,1,%s,%s)
        """,
        (SUPER_ADMIN_USERNAME, pwd, "系统超级管理员", int(admin_role_id), ts, ts),
    )


def _ensure_auth_tables_and_seed(cur) -> None:
    """创建用户/角色/权限/会话表并首次灌入权限与管理员账号。"""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(64) NOT NULL,
            name VARCHAR(128) NOT NULL DEFAULT '',
            created_at VARCHAR(32) NOT NULL DEFAULT '',
            updated_at VARCHAR(32) NOT NULL DEFAULT '',
            UNIQUE KEY uq_roles_code (code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='角色'
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(128) NOT NULL,
            name VARCHAR(256) NOT NULL DEFAULT '',
            description VARCHAR(512) NOT NULL DEFAULT '',
            created_at VARCHAR(32) NOT NULL DEFAULT '',
            UNIQUE KEY uq_perm_code (code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='权限点（菜单/按钮/接口）'
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INT NOT NULL,
            permission_id INT NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            INDEX idx_rp_perm (permission_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='角色-权限'
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            display_name VARCHAR(128) NOT NULL DEFAULT '',
            role_id INT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at VARCHAR(32) NOT NULL DEFAULT '',
            updated_at VARCHAR(32) NOT NULL DEFAULT '',
            UNIQUE KEY uq_users_username (username),
            INDEX idx_users_role (role_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='用户'
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            token VARCHAR(128) NOT NULL,
            expires_at BIGINT NOT NULL COMMENT 'unix 秒',
            created_at VARCHAR(32) NOT NULL DEFAULT '',
            UNIQUE KEY uq_sess_token (token),
            INDEX idx_sess_user (user_id),
            INDEX idx_sess_exp (expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='登录会话'
        """
    )

    ts = str(int(time.time()))
    for code, name, desc in AUTH_PERMISSION_SEED:
        cur.execute(
            """
            INSERT INTO permissions (code, name, description, created_at)
            VALUES (%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description)
            """,
            (code[:128], name[:256], desc[:512], ts),
        )

    admin_role_id = _ensure_role(cur, ADMIN_ROLE_CODE, "管理员")
    op_role_id = _ensure_role(cur, OPERATOR_ROLE_CODE, "业务人员")

    if admin_role_id is not None:
        cur.execute("SELECT id FROM permissions")
        admin_perm_ids = [int(r[0]) for r in cur.fetchall()]
        for pid in admin_perm_ids:
            cur.execute(
                "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s,%s)",
                (admin_role_id, pid),
            )

    if op_role_id is not None:
        _sync_role_permissions(cur, op_role_id, OPERATOR_PERMISSION_CODES)

    _ensure_super_admin_account(cur, admin_role_id)


def init_database() -> tuple[bool, str]:
    """
    创建数据库 llm_case_system 及表结构。
    返回 (成功, 消息)。
    """
    cfg = _get_mysql_config()
    if not cfg:
        return False, "MySQL not configured（请在配置中设置 mysql.host / user 等）"
    conn = get_connection(use_db=False)
    if conn is None:
        return False, "Cannot connect to MySQL (check host/user/password)"
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{DB_NAME}`")

        # 系统表（多系统隔离基础）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS systems (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(256) NOT NULL,
                description TEXT,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                UNIQUE KEY uq_system_name (name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='系统表（多系统数据隔离）'
        """)
        # 确保至少存在一个默认系统
        cur.execute("SELECT COUNT(*) FROM systems")
        if int(cur.fetchone()[0] or 0) == 0:
            cur.execute(
                "INSERT INTO systems (name, description, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                ("默认系统", "系统初始化时自动创建的默认系统", "", ""),
            )

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
                vector_analysis_text LONGTEXT NULL,
                vector_build_summary TEXT NULL,
                vector_built_at VARCHAR(64) NOT NULL DEFAULT '',
                `manual` JSON NULL COMMENT 'manual field: page_type, page_elements, buttons, fields, text_requirements, control_logic'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='截图历史主表（含分析结果与手动补录）'
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
              COMMENT='页面元素明细表（由手动补录/OCR同步）'
            """
        )
        # 兼容旧库：如果缺少新字段，自动补齐
        for alter_sql in [
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS `manual` JSON NULL COMMENT 'manual field: page_type, page_elements, buttons, fields, text_requirements, control_logic'",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_style TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_content TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_interaction TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_data JSON NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_generated_at VARCHAR(64) NOT NULL DEFAULT ''",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS vector_analysis_text LONGTEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS vector_build_summary TEXT NULL",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS vector_built_at VARCHAR(64) NOT NULL DEFAULT ''",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_style_table JSON NULL COMMENT '样式分析表格行 [{element, attributes[], requirement}]'",
            "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'",
            "ALTER TABLE screenshot_history COMMENT='截图历史主表（含分析结果与手动补录）'",
            "ALTER TABLE page_elements COMMENT='页面元素明细表（由手动补录/OCR同步）'",
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
                step_expected JSON NULL COMMENT '["每步预期",...] 与 steps 对齐',
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                last_run_at VARCHAR(64) NULL DEFAULT '',
                run_notes TEXT,
                run_attachments JSON NULL COMMENT '[{file_url, original_name, uploaded_at}, ...]',
                run_records JSON NULL COMMENT '[{operator_name, operator_id, operation_time, message}, ...]',
                executor_id INT NULL DEFAULT NULL COMMENT '最后执行人用户ID，预留关联用户表',
                executor_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '最后执行人展示名',
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                INDEX idx_history_id (history_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='测试用例表（生成、执行与状态追踪）'
        """)
        # 测试计划主表 + 计划用例关联表（计划内执行状态独立于 test_cases.status）
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS test_plans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(256) NOT NULL DEFAULT '',
                description TEXT,
                system_id INT NULL DEFAULT NULL COMMENT '关联系统ID',
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                INDEX idx_tp_system_id (system_id),
                INDEX idx_tp_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='测试计划主表（计划维度）'
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS test_plan_cases (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                plan_id INT NOT NULL,
                case_id INT NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '计划内执行状态',
                run_notes TEXT,
                last_run_at VARCHAR(64) NULL DEFAULT '',
                executor_id INT NULL DEFAULT NULL,
                executor_name VARCHAR(128) NOT NULL DEFAULT '',
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                UNIQUE KEY uq_plan_case (plan_id, case_id),
                INDEX idx_tpc_plan_id (plan_id),
                INDEX idx_tpc_case_id (case_id),
                INDEX idx_tpc_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='测试计划-用例关联表（含计划内执行记录）'
            """
        )

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
                semantic_id VARCHAR(64) NULL DEFAULT NULL,
                parent_unit_key VARCHAR(255) NULL DEFAULT NULL,
                created_at VARCHAR(32) NOT NULL DEFAULT '',
                updated_at VARCHAR(32) NOT NULL DEFAULT '',
                UNIQUE KEY uq_history_unit_key (history_id, unit_key),
                INDEX idx_units_history_id (history_id),
                INDEX idx_units_type (unit_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='需求原子单元表（可检索语义片段）'
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
              COMMENT='需求关系边表（单元间语义关系）'
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
              COMMENT='需求向量表（单元 embedding 存储）'
            """
        )

        # 兼容旧库：如果表已存在但字段缺失，尝试补齐（不影响正常运行）
        for alter_sql in [
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS metadata JSON NULL",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS semantic_id VARCHAR(64) NULL DEFAULT NULL",
            "ALTER TABLE requirement_units ADD COLUMN IF NOT EXISTS parent_unit_key VARCHAR(255) NULL DEFAULT NULL",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS metadata JSON NULL",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_edges ADD COLUMN IF NOT EXISTS system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(128) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS dim INT NOT NULL DEFAULT 0",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE requirement_embeddings ADD COLUMN IF NOT EXISTS system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS executor_id INT NULL DEFAULT NULL COMMENT '最后执行人用户ID，预留关联用户表'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS executor_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '最后执行人展示名'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS run_attachments JSON NULL COMMENT '[{file_url, original_name, uploaded_at}, ...]'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS run_records JSON NULL COMMENT '[{operator_name, operator_id, operation_time, message}, ...]'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS priority VARCHAR(8) NOT NULL DEFAULT 'P2' COMMENT 'P0~P3'",
            "ALTER TABLE test_cases ADD COLUMN IF NOT EXISTS step_expected JSON NULL COMMENT '[\"每步预期\",...] 与 steps 对齐'",
            "ALTER TABLE test_plans ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE test_plans ADD COLUMN IF NOT EXISTS system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'",
            "ALTER TABLE test_plans ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE test_plans ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '计划内执行状态'",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS run_notes TEXT",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS last_run_at VARCHAR(64) NULL DEFAULT ''",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS executor_id INT NULL DEFAULT NULL",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS executor_name VARCHAR(128) NOT NULL DEFAULT ''",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE test_plan_cases ADD COLUMN IF NOT EXISTS updated_at VARCHAR(32) NOT NULL DEFAULT ''",
            "ALTER TABLE test_cases COMMENT='测试用例表（生成、执行与状态追踪）'",
            "ALTER TABLE test_plans COMMENT='测试计划主表（计划维度）'",
            "ALTER TABLE test_plan_cases COMMENT='测试计划-用例关联表（含计划内执行记录）'",
            "ALTER TABLE requirement_units COMMENT='需求原子单元表（可检索语义片段）'",
            "ALTER TABLE requirement_edges COMMENT='需求关系边表（单元间语义关系）'",
            "ALTER TABLE requirement_embeddings COMMENT='需求向量表（单元 embedding 存储）'",
        ]:
            try:
                cur.execute(alter_sql)
            except Exception:
                pass
        try:
            _ensure_mysql_indexes(cur)
        except Exception:
            pass
        try:
            _ensure_auth_tables_and_seed(cur)
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
        vector_analysis_text,
        vector_build_summary,
        vector_built_at,
        analysis_style_table,
        manual,
        system_id,
    ) = row
    _ast = analysis_style_table
    if isinstance(_ast, list):
        _ast_out = _ast
    elif isinstance(_ast, str) and _ast.strip():
        try:
            _ast_out = json.loads(_ast)
        except Exception:
            _ast_out = []
    else:
        _ast_out = []
    if not isinstance(_ast_out, list):
        _ast_out = []
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
            else (
                (json.loads(analysis_data) if isinstance(analysis_data, str) and analysis_data.strip() else None)
                if not isinstance(analysis_data, str)
                else (
                    (json.loads(analysis_data) if analysis_data.strip() else "")
                    if analysis_data.strip().startswith(("{", "[", "\""))
                    else analysis_data
                )
            )
        ),
        "analysis_generated_at": analysis_generated_at or "",
        "vector_analysis_text": vector_analysis_text or "",
        "vector_build_summary": vector_build_summary or "",
        "vector_built_at": vector_built_at or "",
        "analysis_style_table": _ast_out,
        "manual": manual if isinstance(manual, dict) else (json.loads(manual) if isinstance(manual, str) and manual else {}),
        "system_id": system_id,
    }
    return out


def _column_exists_mysql(cur, table: str, column: str) -> bool:
    """当前连接库下是否存在某列（兼容不支持 ADD COLUMN IF NOT EXISTS 的 MySQL/MariaDB）。"""
    try:
        cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s LIMIT 1",
            (table, column),
        )
        return cur.fetchone() is not None
    except Exception:
        return False


def _ensure_screenshot_history_columns_for_read(cur) -> None:
    """读前补齐 screenshot_history 上 read_history SELECT 所需的列。"""
    if not _column_exists_mysql(cur, "screenshot_history", "analysis_style_table"):
        try:
            cur.execute(
                "ALTER TABLE screenshot_history ADD COLUMN analysis_style_table JSON NULL COMMENT '样式分析表格行 [{element, attributes[], requirement}]'"
            )
        except Exception:
            pass


    if not _column_exists_mysql(cur, "screenshot_history", "vector_analysis_text"):
        try:
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN vector_analysis_text LONGTEXT NULL")
        except Exception:
            pass
    if not _column_exists_mysql(cur, "screenshot_history", "vector_build_summary"):
        try:
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN vector_build_summary TEXT NULL")
        except Exception:
            pass
    if not _column_exists_mysql(cur, "screenshot_history", "vector_built_at"):
        try:
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN vector_built_at VARCHAR(64) NOT NULL DEFAULT ''")
        except Exception:
            pass


def _mysql_index_exists(cur, table: str, index_name: str) -> bool:
    try:
        cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s LIMIT 1",
            (table, index_name),
        )
        return cur.fetchone() is not None
    except Exception:
        return False


def _ensure_mysql_indexes(cur) -> None:
    """
    为常用 WHERE / JOIN / ORDER BY 补齐二级索引（老库升级时可能缺失）。
    说明：screenshot_history 主查询为 ORDER BY id DESC，主键聚簇索引已覆盖；
    以下索引主要加速按时间筛选、需求网络按 history_id+类型 查询等。
    """
    specs: list[tuple[str, str, str]] = [
        (
            "screenshot_history",
            "idx_sh_created_at",
            "CREATE INDEX idx_sh_created_at ON screenshot_history (created_at)",
        ),
        (
            "screenshot_history",
            "idx_sh_updated_at",
            "CREATE INDEX idx_sh_updated_at ON screenshot_history (updated_at)",
        ),
        (
            "requirement_units",
            "idx_units_hid_type",
            "CREATE INDEX idx_units_hid_type ON requirement_units (history_id, unit_type)",
        ),
        (
            "requirement_edges",
            "idx_edges_hid_relation",
            "CREATE INDEX idx_edges_hid_relation ON requirement_edges (history_id, relation_type)",
        ),
        (
            "screenshot_history",
            "idx_sh_system_name",
            "CREATE INDEX idx_sh_system_name ON screenshot_history (system_name)",
        ),
        (
            "screenshot_history",
            "idx_sh_file_name",
            "CREATE INDEX idx_sh_file_name ON screenshot_history (file_name)",
        ),
        (
            "test_cases",
            "idx_tc_hid_status",
            "CREATE INDEX idx_tc_hid_status ON test_cases (history_id, status)",
        ),
        (
            "test_cases",
            "idx_tc_updated_at",
            "CREATE INDEX idx_tc_updated_at ON test_cases (updated_at)",
        ),
        (
            "page_elements",
            "idx_pe_hid_type_name",
            "CREATE INDEX idx_pe_hid_type_name ON page_elements (history_id, element_type, element_name)",
        ),
        (
            "requirement_edges",
            "idx_edges_hid_from",
            "CREATE INDEX idx_edges_hid_from ON requirement_edges (history_id, from_unit_key)",
        ),
        (
            "requirement_edges",
            "idx_edges_hid_to",
            "CREATE INDEX idx_edges_hid_to ON requirement_edges (history_id, to_unit_key)",
        ),
        (
            "screenshot_history",
            "idx_sh_system_id",
            "CREATE INDEX idx_sh_system_id ON screenshot_history (system_id)",
        ),
        (
            "test_cases",
            "idx_tc_system_id",
            "CREATE INDEX idx_tc_system_id ON test_cases (system_id)",
        ),
        (
            "test_cases",
            "idx_tc_executor_id",
            "CREATE INDEX idx_tc_executor_id ON test_cases (executor_id)",
        ),
        (
            "requirement_units",
            "idx_units_system_id",
            "CREATE INDEX idx_units_system_id ON requirement_units (system_id)",
        ),
        (
            "requirement_embeddings",
            "idx_embeddings_system_id",
            "CREATE INDEX idx_embeddings_system_id ON requirement_embeddings (system_id)",
        ),
    ]
    for table, iname, ddl in specs:
        if _mysql_index_exists(cur, table, iname):
            continue
        try:
            cur.execute(ddl)
        except Exception:
            pass


def _row_to_case(row: tuple) -> dict[str, Any]:
    """将 test_cases 一行转为与 JSON 一致的 dict。"""
    id_ = row[0]
    history_id = row[1]
    title = row[2]
    preconditions = row[3]
    steps = row[4]
    expected = row[5]
    status = row[6]
    last_run_at = row[7]
    run_notes = row[8]
    run_attachments = row[9] if len(row) > 9 else None
    run_records = row[10] if len(row) > 10 else None
    created_at = row[11] if len(row) > 11 else ""
    updated_at = row[12] if len(row) > 12 else ""
    system_id = row[13] if len(row) > 13 else None
    executor_id = row[14] if len(row) > 14 else None
    executor_name = row[15] if len(row) > 15 else ""
    priority = row[16] if len(row) > 16 else "P2"
    step_expected_raw = row[17] if len(row) > 17 else None
    if isinstance(run_attachments, list):
        ra_out = run_attachments
    elif isinstance(run_attachments, str) and run_attachments.strip():
        try:
            ra_out = json.loads(run_attachments)
        except Exception:
            ra_out = []
    else:
        ra_out = []
    if not isinstance(ra_out, list):
        ra_out = []
    if isinstance(run_records, list):
        rr_out = run_records
    elif isinstance(run_records, str) and run_records.strip():
        try:
            rr_out = json.loads(run_records)
        except Exception:
            rr_out = []
    else:
        rr_out = []
    if not isinstance(rr_out, list):
        rr_out = []
    if isinstance(step_expected_raw, list):
        se_out = step_expected_raw
    elif isinstance(step_expected_raw, str) and step_expected_raw.strip():
        try:
            se_out = json.loads(step_expected_raw)
        except Exception:
            se_out = []
    else:
        se_out = []
    if not isinstance(se_out, list):
        se_out = []
    se_out = [str(x) if x is not None else "" for x in se_out]
    return {
        "id": id_,
        "history_id": history_id,
        "title": title or "",
        "preconditions": preconditions or "",
        "steps": steps if isinstance(steps, list) else (json.loads(steps) if isinstance(steps, str) and steps else []),
        "expected": expected or "",
        "step_expected": se_out,
        "status": status or "draft",
        "last_run_at": last_run_at or "",
        "run_notes": run_notes or "",
        "run_attachments": ra_out,
        "run_records": rr_out,
        "created_at": created_at or "",
        "updated_at": updated_at or "",
        "system_id": system_id,
        "executor_id": int(executor_id) if executor_id is not None else None,
        "executor_name": executor_name or "",
        "priority": str(priority or "P2")[:8] if str(priority or "").strip() else "P2",
    }


def read_history(system_id: int | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        _ensure_screenshot_history_columns_for_read(cur)
        if not _column_exists_mysql(cur, "screenshot_history", "system_id"):
            try:
                cur.execute("ALTER TABLE screenshot_history ADD COLUMN system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'")
            except Exception:
                pass
        sql = "SELECT id, file_name, file_url, system_name, menu_structure, created_at, updated_at, analysis, analysis_style, analysis_content, analysis_interaction, analysis_data, analysis_generated_at, vector_analysis_text, vector_build_summary, vector_built_at, analysis_style_table, `manual`, system_id FROM screenshot_history"
        params: list[Any] = []
        if system_id is not None:
            sql += " WHERE system_id=%s"
            params.append(int(system_id))
        sql += " ORDER BY id DESC"
        cur.execute(sql, tuple(params))
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


def read_history_by_id(history_id: int, system_id: int | None = None) -> dict[str, Any] | None:
    """
    按主键读取单条截图历史（与 read_history 字段一致）。
    用于向量建库/预览等「已知 history_id」场景，避免拉取系统下全表。
    """
    conn = get_connection()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        _ensure_screenshot_history_columns_for_read(cur)
        if not _column_exists_mysql(cur, "screenshot_history", "system_id"):
            try:
                cur.execute("ALTER TABLE screenshot_history ADD COLUMN system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'")
            except Exception:
                pass
        sql = (
            "SELECT id, file_name, file_url, system_name, menu_structure, created_at, updated_at, analysis, "
            "analysis_style, analysis_content, analysis_interaction, analysis_data, analysis_generated_at, "
            "vector_analysis_text, vector_build_summary, vector_built_at, analysis_style_table, manual, system_id "
            "FROM screenshot_history WHERE id=%s"
        )
        params: list[Any] = [int(history_id)]
        if system_id is not None:
            sql += " AND system_id=%s"
            params.append(int(system_id))
        sql += " LIMIT 1"
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return _row_to_history(row)
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def update_history_vector_meta(history_id: int, *, vector_built_at: str, vector_build_summary: str = "") -> bool:
    """更新 screenshot_history 的向量建库时间与摘要。"""
    conn = get_connection()
    if conn is None:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE screenshot_history
            SET vector_built_at=%s, vector_build_summary=%s
            WHERE id=%s
            """,
            (str(vector_built_at or ""), str(vector_build_summary or ""), int(history_id)),
        )
        try:
            conn.commit()
        except Exception:
            pass
        try:
            cur.close()
        except Exception:
            pass
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def write_history(items: list[dict[str, Any]]) -> None:
    conn = get_connection()
    if conn is None:
        return
    cur = None
    try:
        cur = conn.cursor()
        try:
            conn.begin()
        except Exception:
            pass
        # 为避免“服务已升级但数据库列尚未同步”的情况，写入前确保分析字段存在
        try:
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_style TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_content TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_interaction TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_data JSON NULL")
            cur.execute(
                "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_generated_at VARCHAR(64) NOT NULL DEFAULT ''"
            )
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS vector_analysis_text LONGTEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS vector_build_summary TEXT NULL")
            cur.execute("ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS vector_built_at VARCHAR(64) NOT NULL DEFAULT ''")
            cur.execute(
                "ALTER TABLE screenshot_history ADD COLUMN IF NOT EXISTS analysis_style_table JSON NULL COMMENT '样式分析表格行'"
            )
        except Exception:
            # 若表结构已完整，或 ALTER 不被允许，忽略；后续 INSERT 会报错并由上层处理
            pass
        _ensure_screenshot_history_columns_for_read(cur)
        cur.execute("DELETE FROM screenshot_history")
        cur.execute("DELETE FROM page_elements")
        for r in items:
            mid = json.dumps(r.get("menu_structure") or [], ensure_ascii=False) if isinstance(r.get("menu_structure"), list) else "[]"
            man = r.get("manual")
            man_str = json.dumps(man, ensure_ascii=False) if isinstance(man, dict) else "{}"
            analysis_data = r.get("analysis_data")
            analysis_data_str = (
                json.dumps(analysis_data, ensure_ascii=False)
                if isinstance(analysis_data, (dict, list, str, int, float, bool))
                else None
            )
            ast = r.get("analysis_style_table")
            analysis_style_table_str = json.dumps(ast, ensure_ascii=False) if isinstance(ast, list) else None
            vector_analysis_text = str(r.get("vector_analysis_text") or "")
            vector_build_summary = str(r.get("vector_build_summary") or "")
            vector_built_at = str(r.get("vector_built_at") or "")
            system_id_val = r.get("system_id")
            if system_id_val is not None:
                try:
                    system_id_val = int(system_id_val)
                except (ValueError, TypeError):
                    system_id_val = None
            cur.execute(
                """INSERT INTO screenshot_history
                   (id, file_name, file_url, system_name, menu_structure, created_at, updated_at, analysis,
                    analysis_style, analysis_content, analysis_interaction, analysis_data, analysis_generated_at,
                    vector_analysis_text, vector_build_summary, vector_built_at, analysis_style_table, `manual`, system_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
                    vector_analysis_text,
                    vector_build_summary,
                    vector_built_at,
                    analysis_style_table_str,
                    man_str,
                    system_id_val,
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
        try:
            conn.commit()
        except Exception:
            pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
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


def write_requirement_network(
    history_id: int,
    units: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    embeddings: dict[str, list[float]] | None,
    *,
    embedding_model: str = "",
    system_id: int | None = None,
) -> None:
    """
    写入需求网络库：先清空同 history_id 的旧数据，再插入 units/edges/embeddings。
    embeddings 以 unit_key -> embedding_vector 的形式传入。
    """
    conn = get_connection()
    if conn is None:
        return
    cur = None
    try:
        cur = conn.cursor()
        # 老库兼容：部分环境不支持 `ADD COLUMN IF NOT EXISTS`，导致新字段缺失时插入报错。
        # 这里按实际列存在性动态选择 INSERT 列表，避免整条建库失败。
        has_units_system_id = _column_exists_mysql(cur, "requirement_units", "system_id")
        has_edges_system_id = _column_exists_mysql(cur, "requirement_edges", "system_id")
        has_emb_system_id = _column_exists_mysql(cur, "requirement_embeddings", "system_id")
        has_units_semantic_id = _column_exists_mysql(cur, "requirement_units", "semantic_id")
        has_units_parent_uk = _column_exists_mysql(cur, "requirement_units", "parent_unit_key")
        try:
            conn.begin()
        except Exception:
            pass
        # 清空同一页面作用域的旧网络数据，保证覆盖式生成
        cur.execute("DELETE FROM requirement_embeddings WHERE history_id=%s", (int(history_id),))
        cur.execute("DELETE FROM requirement_edges WHERE history_id=%s", (int(history_id),))
        cur.execute("DELETE FROM requirement_units WHERE history_id=%s", (int(history_id),))

        # units
        seen_unit_keys: set[str] = set()
        for u in units:
            if not isinstance(u, dict):
                continue
            unit_key = str(u.get("unit_key") or "").strip()
            unit_type = str(u.get("unit_type") or "other").strip()
            content = str(u.get("content") or "").strip()
            if not unit_key or not content:
                continue
            if unit_key in seen_unit_keys:
                continue
            seen_unit_keys.add(unit_key)
            metadata = u.get("metadata")
            metadata_str = json.dumps(metadata, ensure_ascii=False) if isinstance(metadata, (dict, list)) else None
            created_at = str(u.get("created_at") or "")
            updated_at = str(u.get("updated_at") or "")
            _sid = int(system_id) if system_id is not None else None
            sem_id = str(u.get("semantic_id") or "").strip() or None
            parent_uk = str(u.get("parent_unit_key") or "").strip() or None

            cols = ["history_id", "unit_key", "unit_type", "content", "metadata", "created_at", "updated_at"]
            vals: list[Any] = [
                int(history_id),
                unit_key[:255],
                unit_type[:64],
                content,
                metadata_str,
                created_at,
                updated_at,
            ]
            if has_units_system_id:
                cols.append("system_id")
                vals.append(_sid)
            if has_units_semantic_id:
                cols.append("semantic_id")
                vals.append(sem_id[:64] if sem_id else None)
            if has_units_parent_uk:
                cols.append("parent_unit_key")
                vals.append(parent_uk[:255] if parent_uk else None)

            placeholders = ",".join(["%s"] * len(cols))
            cur.execute(
                f"INSERT INTO requirement_units ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(vals),
            )

        # edges
        seen_edges: set[tuple[str, str, str]] = set()
        for e in edges:
            if not isinstance(e, dict):
                continue
            from_key = str(e.get("from_unit_key") or "").strip()
            to_key = str(e.get("to_unit_key") or "").strip()
            relation_type = str(e.get("relation_type") or "related").strip()
            if not from_key or not to_key:
                continue
            edge_key = (from_key, to_key, relation_type)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            metadata = e.get("metadata")
            metadata_str = json.dumps(metadata, ensure_ascii=False) if isinstance(metadata, (dict, list)) else None
            created_at = str(e.get("created_at") or "")
            updated_at = str(e.get("updated_at") or "")
            _sid = int(system_id) if system_id is not None else None
            if has_edges_system_id:
                cur.execute(
                    """INSERT INTO requirement_edges
                       (history_id, from_unit_key, to_unit_key, relation_type, metadata, created_at, updated_at, system_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        int(history_id),
                        from_key[:255],
                        to_key[:255],
                        relation_type[:64],
                        metadata_str,
                        created_at,
                        updated_at,
                        _sid,
                    ),
                )
            else:
                cur.execute(
                    """INSERT INTO requirement_edges
                       (history_id, from_unit_key, to_unit_key, relation_type, metadata, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        int(history_id),
                        from_key[:255],
                        to_key[:255],
                        relation_type[:64],
                        metadata_str,
                        created_at,
                        updated_at,
                    ),
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
                _sid = int(system_id) if system_id is not None else None
                if has_emb_system_id:
                    cur.execute(
                        """INSERT INTO requirement_embeddings
                           (history_id, unit_key, embedding, embedding_model, dim, created_at, updated_at, system_id)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            int(history_id),
                            str(unit_key)[:255],
                            embedding_str,
                            str(embedding_model or "")[:128],
                            int(len(vec_f)),
                            "",
                            "",
                            _sid,
                        ),
                    )
                else:
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

        try:
            conn.commit()
        except Exception:
            pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
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


def read_requirement_network_for_search(
    history_id: int | None = None,
    unit_type: str | None = None,
    unit_types: list[str] | None = None,
    system_id: int | None = None,
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
        if unit_types:
            cleaned = [str(x).strip()[:64] for x in unit_types if str(x).strip()]
            cleaned = cleaned[:48]
            if cleaned:
                placeholders = ",".join(["%s"] * len(cleaned))
                where.append(f"u.unit_type IN ({placeholders})")
                params.extend(cleaned)
        elif unit_type:
            where.append("u.unit_type=%s")
            params.append(str(unit_type)[:64])
        if system_id is not None:
            sid = int(system_id)
            if _column_exists_mysql(cur, "requirement_embeddings", "system_id"):
                where.append("re.system_id=%s")
                params.append(sid)
            elif _column_exists_mysql(cur, "requirement_units", "system_id"):
                where.append("u.system_id=%s")
                params.append(sid)
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
            emb_obj = _parse_embedding_column(embedding)
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


def read_requirement_network_for_search_many(
    *,
    history_ids: list[int],
    unit_types: list[str] | None = None,
    system_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    批量读取多个 history 的 embedding + metadata（用于 record-level 聚合/相似度）。
    返回结构与 read_requirement_network_for_search 对齐：
    [
      {history_id, unit_key, unit_type, content, metadata, embedding:[...]}
    ]
    """
    ids = []
    for x in (history_ids or []):
        try:
            v = int(x)
        except Exception:
            continue
        if v > 0 and v not in ids:
            ids.append(v)
    ids = ids[:200]
    if not ids:
        return []

    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        where = []
        params: list[Any] = []

        placeholders = ",".join(["%s"] * len(ids))
        where.append(f"re.history_id IN ({placeholders})")
        params.extend(ids)

        cleaned_types: list[str] = []
        if unit_types:
            cleaned_types = [str(x).strip()[:64] for x in unit_types if str(x).strip()]
            cleaned_types = cleaned_types[:48]
        if cleaned_types:
            tp = ",".join(["%s"] * len(cleaned_types))
            where.append(f"u.unit_type IN ({tp})")
            params.extend(cleaned_types)

        # 注意：与 read_requirement_network_graph 保持一致，不按 system_id 过滤 unit。
        # 原因：历史数据里 requirement_units.system_id 可能与建库写入不一致，
        # 容易出现「库里有向量但接口返回空」的情况。system_id 参数仅为兼容保留。

        if system_id is not None:
            sid = int(system_id)
            if _column_exists_mysql(cur, "requirement_embeddings", "system_id"):
                where.append("re.system_id=%s")
                params.append(sid)
            elif _column_exists_mysql(cur, "requirement_units", "system_id"):
                where.append("u.system_id=%s")
                params.append(sid)
        where_sql = " WHERE " + " AND ".join(where)
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
            meta_obj = (
                metadata
                if isinstance(metadata, (dict, list))
                else (json.loads(metadata) if isinstance(metadata, str) and metadata else None)
            )
            emb_obj = _parse_embedding_column(embedding)
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
        try:
            cur.close()
        except Exception:
            pass
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def read_requirement_network_graph(
    history_id: int,
    system_id: int | None = None,
) -> dict[str, Any]:
    """
    读取指定截图记录的需求网络：原子单元（含向量）与边，供前端「需求向量图」可视化。

    仅按 history_id 过滤：若再按 system_id 过滤 unit，易与建库时写入的
    requirement_units.system_id 不一致导致「库里有向量但接口全空」。
    system_id 参数保留仅为兼容旧调用，不再参与 WHERE。
    """
    conn = get_connection()
    if conn is None:
        return {"units": [], "edges": [], "embedding_model": ""}
    cur = None
    try:
        cur = conn.cursor()
        hid = int(history_id)
        if system_id is not None and _column_exists_mysql(cur, "screenshot_history", "system_id"):
            cur.execute(
                "SELECT 1 FROM screenshot_history WHERE id=%s AND system_id=%s LIMIT 1",
                (hid, int(system_id)),
            )
            if not cur.fetchone():
                return {"units": [], "edges": [], "embedding_model": ""}

        where_units = "u.history_id=%s"
        params_units: list[Any] = [hid]
        if system_id is not None and _column_exists_mysql(cur, "requirement_embeddings", "system_id"):
            where_units += " AND re.system_id=%s"
            params_units.append(int(system_id))

        sql_units_full = f"""
            SELECT u.history_id, u.unit_key, u.unit_type, u.content, u.metadata,
                   u.semantic_id, u.parent_unit_key,
                   re.embedding, re.embedding_model
            FROM requirement_units u
            LEFT JOIN requirement_embeddings re
              ON re.history_id=u.history_id AND re.unit_key=u.unit_key
            WHERE {where_units}
        """
        sql_units_simple = f"""
            SELECT u.history_id, u.unit_key, u.unit_type, u.content, u.metadata,
                   re.embedding, re.embedding_model
            FROM requirement_units u
            LEFT JOIN requirement_embeddings re
              ON re.history_id=u.history_id AND re.unit_key=u.unit_key
            WHERE {where_units}
        """
        rows: list[Any] = []
        mode_full = True
        try:
            cur.execute(sql_units_full, tuple(params_units))
            rows = list(cur.fetchall() or [])
        except Exception:
            cur.execute(sql_units_simple, tuple(params_units))
            rows = list(cur.fetchall() or [])
            mode_full = False

        units: list[dict[str, Any]] = []
        emb_model_global = ""
        for r in rows:
            if mode_full:
                hid_v = r[0]
                unit_key = r[1]
                ut = r[2]
                content = r[3]
                metadata = r[4]
                sem_id = r[5]
                parent_uk = r[6]
                embedding = r[7]
                emb_model = r[8] if len(r) > 8 else ""
            else:
                hid_v = r[0]
                unit_key = r[1]
                ut = r[2]
                content = r[3]
                metadata = r[4]
                sem_id, parent_uk = None, None
                embedding = r[5]
                emb_model = r[6] if len(r) > 6 else ""
            meta_obj = metadata if isinstance(metadata, (dict, list)) else (json.loads(metadata) if isinstance(metadata, str) and metadata else None)
            emb_obj = _parse_embedding_column(embedding)
            if isinstance(emb_model, str) and emb_model.strip() and not emb_model_global:
                emb_model_global = emb_model.strip()
            units.append(
                {
                    "history_id": int(hid_v) if hid_v is not None else hid,
                    "unit_key": str(unit_key or ""),
                    "unit_type": str(ut or "other"),
                    "content": str(content or ""),
                    "metadata": meta_obj,
                    "semantic_id": str(sem_id or "").strip() or None,
                    "parent_unit_key": str(parent_uk or "").strip() or None,
                    "embedding": emb_obj,
                    "embedding_model": str(emb_model or ""),
                }
            )

        cur.execute(
            """
            SELECT from_unit_key, to_unit_key, relation_type, metadata
            FROM requirement_edges
            WHERE history_id=%s
            """,
            (hid,),
        )
        erows = cur.fetchall()
        edges: list[dict[str, Any]] = []
        for er in erows or []:
            fk = str(er[0] or "").strip()
            tk = str(er[1] or "").strip()
            rt = str(er[2] or "related").strip()
            em = er[3] if len(er) > 3 else None
            em_obj = em if isinstance(em, (dict, list)) else (json.loads(em) if isinstance(em, str) and em else None)
            if fk and tk:
                edges.append({"from_unit_key": fk, "to_unit_key": tk, "relation_type": rt, "metadata": em_obj})

        cur.close()
        return {"units": units, "edges": edges, "embedding_model": emb_model_global}
    except Exception as exc:
        try:
            import traceback

            traceback.print_exc()
            print(f"[read_requirement_network_graph] history_id={history_id} failed: {exc}", flush=True)
        except Exception:
            pass
        return {"units": [], "edges": [], "embedding_model": ""}
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


def count_requirement_network(history_id: int) -> dict[str, Any]:
    """
    调试用：统计指定 history_id 下需求网络相关数据量，
    用于区分「历史ID不一致」与「向量写入/解析失败」。
    """
    conn = get_connection()
    if conn is None:
        return {
            "units_total": 0,
            "embeddings_total": 0,
            "edges_total": 0,
            "units_with_embedding": 0,
        }

    cur = None
    try:
        cur = conn.cursor()
        hid = int(history_id)
        cur.execute("SELECT COUNT(*) FROM requirement_units WHERE history_id=%s", (hid,))
        units_total = int(cur.fetchone()[0] or 0)

        cur.execute("SELECT COUNT(*) FROM requirement_embeddings WHERE history_id=%s", (hid,))
        embeddings_total = int(cur.fetchone()[0] or 0)

        cur.execute("SELECT COUNT(*) FROM requirement_edges WHERE history_id=%s", (hid,))
        edges_total = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT COUNT(DISTINCT u.unit_key)
            FROM requirement_units u
            JOIN requirement_embeddings re
              ON re.history_id=u.history_id AND re.unit_key=u.unit_key
            WHERE u.history_id=%s
            """,
            (hid,),
        )
        units_with_embedding = int(cur.fetchone()[0] or 0)

        cur.close()
        return {
            "units_total": units_total,
            "embeddings_total": embeddings_total,
            "edges_total": edges_total,
            "units_with_embedding": units_with_embedding,
        }
    except Exception:
        return {
            "units_total": 0,
            "embeddings_total": 0,
            "edges_total": 0,
            "units_with_embedding": 0,
        }
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


def list_requirement_network_counts(*, system_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """
    调试用：列出当前库中哪些 history_id 已写入需求网络（units/embeddings/edges）。
    用于定位“页面选的 history_id 与实际写入不一致”的问题。
    """
    conn = get_connection()
    if conn is None:
        return []
    cur = None
    try:
        cur = conn.cursor()
        where = []
        params: list[Any] = []
        if system_id is not None:
            where.append("u.system_id=%s")
            params.append(int(system_id))
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        lim = max(1, min(int(limit or 200), 500))
        cur.execute(
            f"""
            SELECT
              u.history_id,
              COUNT(*) AS units_total,
              COUNT(DISTINCT re.unit_key) AS embeddings_total,
              (
                SELECT COUNT(*)
                FROM requirement_edges e
                WHERE e.history_id=u.history_id
              ) AS edges_total
            FROM requirement_units u
            LEFT JOIN requirement_embeddings re
              ON re.history_id=u.history_id AND re.unit_key=u.unit_key
            {where_sql}
            GROUP BY u.history_id
            ORDER BY units_total DESC, u.history_id DESC
            LIMIT {lim}
            """,
            tuple(params),
        )
        rows = cur.fetchall() or []
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                hid = int(r[0] or 0)
            except Exception:
                continue
            out.append(
                {
                    "history_id": hid,
                    "units_total": int(r[1] or 0),
                    "embeddings_total": int(r[2] or 0),
                    "edges_total": int(r[3] or 0),
                }
            )
        cur.close()
        return out
    except Exception:
        return []
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


def read_requirement_network_graph_all(
    *,
    system_id: int | None = None,
    limit_units: int = 800,
    limit_edges: int = 4000,
    show_all: bool = False,
) -> dict[str, Any]:
    """
    聚合读取“全量需求网络图”（跨多个 history）。
    注意：为避免历史数据 system_id 不一致导致漏数据，这里 system_id 过滤是“尽力而为”：
    - 若提供 system_id，则优先按 requirement_embeddings.system_id 过滤（向量写入时更稳定）
    - units/edges 仍会做二次 key 过滤保证闭包
    """
    conn = get_connection()
    if conn is None:
        return {"units": [], "edges": [], "embedding_model": ""}
    cur = None
    try:
        cur = conn.cursor()
        if show_all:
            lim_u = max(50, int(limit_units or 800))
            lim_e = max(0, int(limit_edges or 4000))
        else:
            lim_u = max(50, min(int(limit_units or 800), 5000))
            lim_e = max(0, min(int(limit_edges or 4000), 30000))
        has_emb_system_id = _column_exists_mysql(cur, "requirement_embeddings", "system_id")
        included_history_ids: list[int] = []

        # 1) units：优先取“有 embedding 的 unit”，保证可视化布局可用
        # system_id 过滤可能因历史数据不一致导致“明明有向量但返回空”，因此若过滤为空则自动 fallback 为不过滤。
        def _pick_history_ids(sys_id: int | None) -> tuple[list[int], bool]:
            """
            为避免 lim_u 被单个 history 的大量 unit “挤占”，先选取一批 history_id，
            再在这些 history 范围内拉取 units。
            """
            # show_all 时不做 history 抽样，避免漏掉某些 history 的向量节点
            if show_all:
                used_filter = (sys_id is not None and has_emb_system_id)
                return [], used_filter
            where = []
            params: list[Any] = []
            if sys_id is not None and has_emb_system_id:
                where.append("system_id=%s")
                params.append(int(sys_id))
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            # 经验值：history 覆盖数不宜过大，避免 IN 过长；同时至少覆盖一批近期截图
            limit_hist = max(10, min(120, int(lim_u // 6) or 60))
            cur.execute(
                f"""
                SELECT history_id
                FROM requirement_embeddings
                {where_sql}
                GROUP BY history_id
                ORDER BY MAX(id) DESC
                LIMIT %s
                """,
                tuple([*params, int(limit_hist)]),
            )
            rows = list(cur.fetchall() or [])
            hids = []
            for r in rows:
                try:
                    hids.append(int(r[0]))
                except Exception:
                    continue
            used_filter = (sys_id is not None and has_emb_system_id)
            return hids, used_filter

        def _read_unit_rows(sys_id: int | None) -> tuple[list[Any], bool, list[int]]:
            where = []
            params: list[Any] = []
            if sys_id is not None and has_emb_system_id:
                where.append("re.system_id=%s")
                params.append(int(sys_id))
            # 先选 history_id，保证覆盖多个截图
            hist_ids, used_filter = _pick_history_ids(sys_id)
            if hist_ids:
                placeholders = ",".join(["%s"] * len(hist_ids))
                where.append(f"re.history_id IN ({placeholders})")
                params.extend([int(x) for x in hist_ids])
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            # 兼容旧库：semantic_id / parent_unit_key 可能不存在
            sql_full = f"""
                SELECT u.history_id, u.unit_key, u.unit_type, u.content, u.metadata,
                       u.semantic_id, u.parent_unit_key,
                       re.embedding, re.embedding_model
                FROM requirement_units u
                JOIN requirement_embeddings re
                  ON re.history_id=u.history_id AND re.unit_key=u.unit_key
                {where_sql}
                ORDER BY re.id DESC
                LIMIT %s
            """
            sql_simple = f"""
                SELECT u.history_id, u.unit_key, u.unit_type, u.content, u.metadata,
                       '' AS semantic_id, '' AS parent_unit_key,
                       re.embedding, re.embedding_model
                FROM requirement_units u
                JOIN requirement_embeddings re
                  ON re.history_id=u.history_id AND re.unit_key=u.unit_key
                {where_sql}
                ORDER BY re.id DESC
                LIMIT %s
            """
            try:
                cur.execute(sql_full, tuple([*params, int(lim_u)]))
            except Exception:
                cur.execute(sql_simple, tuple([*params, int(lim_u)]))
            # used_filter: 表示“请求方期望按 system_id 过滤且实际执行了过滤”
            return list(cur.fetchall() or []), used_filter, hist_ids

        rows, _used_filter, included_history_ids = _read_unit_rows(system_id)
        fallback_used = False
        # 若库结构不支持 embeddings.system_id，则无法按系统过滤：直接 fallback
        if system_id is not None and not has_emb_system_id:
            return {
                "units": [],
                "edges": [],
                "embedding_model": "",
                "meta": {
                    "fallback_used": False,
                    "system_filter_available": False,
                    "included_history_ids": [],
                },
            }
        units: list[dict[str, Any]] = []
        emb_model_global = ""
        keys: set[tuple[int, str]] = set()
        for r in rows:
            (hid, unit_key, ut, content, metadata, semantic_id, parent_unit_key, embedding, embedding_model) = r
            uk = str(unit_key or "").strip()
            if not uk:
                continue
            emb = _parse_embedding_column(embedding)
            if not emb:
                continue
            if not emb_model_global and isinstance(embedding_model, str):
                emb_model_global = embedding_model
            meta_obj = (
                metadata
                if isinstance(metadata, (dict, list))
                else (json.loads(metadata) if isinstance(metadata, str) and metadata else None)
            )
            units.append(
                {
                    "history_id": int(hid),
                    "node_id": f"{int(hid)}:{uk}",
                    "unit_key": uk,
                    "unit_type": str(ut or "other"),
                    "content": str(content or ""),
                    "metadata": meta_obj,
                    "semantic_id": str(semantic_id or ""),
                    "parent_unit_key": str(parent_unit_key or ""),
                    "embedding": emb,
                }
            )
            keys.add((int(hid), uk))

        if not units:
            return {
                "units": [],
                "edges": [],
                "embedding_model": emb_model_global,
                "meta": {
                    "fallback_used": fallback_used,
                    "system_filter_available": bool(has_emb_system_id),
                    "included_history_ids": included_history_ids,
                },
            }

        # 2) edges：仅取 units 涵盖的 history 范围，再按 key 闭包过滤
        hist_ids = sorted({hid for hid, _uk in keys})
        if lim_e <= 0 or not hist_ids:
            return {
                "units": units,
                "edges": [],
                "embedding_model": emb_model_global,
                "meta": {
                    "fallback_used": fallback_used,
                    "system_filter_available": bool(has_emb_system_id),
                    "included_history_ids": included_history_ids,
                },
            }

        placeholders = ",".join(["%s"] * len(hist_ids))
        cur.execute(
            f"""
            SELECT history_id, from_unit_key, to_unit_key, relation_type, metadata
            FROM requirement_edges
            WHERE history_id IN ({placeholders})
            ORDER BY id DESC
            LIMIT %s
            """,
            tuple([*hist_ids, int(lim_e)]),
        )
        erows = list(cur.fetchall() or [])
        edges: list[dict[str, Any]] = []
        for (hid, fk, tk, rt, md) in erows:
            hk = int(hid)
            fks = str(fk or "").strip()
            tks = str(tk or "").strip()
            if not fks or not tks:
                continue
            if (hk, fks) not in keys or (hk, tks) not in keys:
                continue
            meta_obj = md if isinstance(md, (dict, list)) else (json.loads(md) if isinstance(md, str) and md else None)
            edges.append(
                {
                    "history_id": hk,
                    "from_node_id": f"{hk}:{fks}",
                    "to_node_id": f"{hk}:{tks}",
                    "from_unit_key": fks,
                    "to_unit_key": tks,
                    "relation_type": str(rt or ""),
                    "metadata": meta_obj,
                }
            )

        return {
            "units": units,
            "edges": edges,
            "embedding_model": emb_model_global,
            "meta": {
                "fallback_used": fallback_used,
                "system_filter_available": bool(has_emb_system_id),
                "included_history_ids": included_history_ids,
            },
        }
    except Exception:
        return {
            "units": [],
            "edges": [],
            "embedding_model": "",
            "meta": {"fallback_used": False, "system_filter_available": False},
        }
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


def read_cases(system_id: int | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        if not _column_exists_mysql(cur, "test_cases", "system_id"):
            try:
                cur.execute("ALTER TABLE test_cases ADD COLUMN system_id INT NULL DEFAULT NULL COMMENT '关联系统ID'")
            except Exception:
                pass
        if not _column_exists_mysql(cur, "test_cases", "executor_id"):
            try:
                cur.execute(
                    "ALTER TABLE test_cases ADD COLUMN executor_id INT NULL DEFAULT NULL COMMENT '最后执行人用户ID，预留关联用户表'"
                )
            except Exception:
                pass
        if not _column_exists_mysql(cur, "test_cases", "executor_name"):
            try:
                cur.execute(
                    "ALTER TABLE test_cases ADD COLUMN executor_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '最后执行人展示名'"
                )
            except Exception:
                pass
        if not _column_exists_mysql(cur, "test_cases", "run_attachments"):
            try:
                cur.execute(
                    "ALTER TABLE test_cases ADD COLUMN run_attachments JSON NULL COMMENT '[{file_url, original_name, uploaded_at}, ...]'"
                )
            except Exception:
                pass
        if not _column_exists_mysql(cur, "test_cases", "run_records"):
            try:
                cur.execute(
                    "ALTER TABLE test_cases ADD COLUMN run_records JSON NULL COMMENT '[{operator_name, operator_id, operation_time, message}, ...]'"
                )
            except Exception:
                pass
        if not _column_exists_mysql(cur, "test_cases", "priority"):
            try:
                cur.execute(
                    "ALTER TABLE test_cases ADD COLUMN priority VARCHAR(8) NOT NULL DEFAULT 'P2' COMMENT 'P0~P3'"
                )
            except Exception:
                pass
        if not _column_exists_mysql(cur, "test_cases", "step_expected"):
            try:
                cur.execute(
                    "ALTER TABLE test_cases ADD COLUMN step_expected JSON NULL COMMENT '[\"每步预期\",...] 与 steps 对齐'"
                )
            except Exception:
                pass
        sql = "SELECT id, history_id, title, preconditions, steps, expected, status, last_run_at, run_notes, run_attachments, run_records, created_at, updated_at, system_id, executor_id, executor_name, priority, step_expected FROM test_cases"
        params: list[Any] = []
        if system_id is not None:
            sql += " WHERE system_id=%s"
            params.append(int(system_id))
        sql += " ORDER BY id DESC"
        cur.execute(sql, tuple(params))
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
    cur = None
    try:
        cur = conn.cursor()
        try:
            conn.begin()
        except Exception:
            pass
        cur.execute("DELETE FROM test_cases")
        for c in items:
            steps_str = json.dumps(c.get("steps") or [], ensure_ascii=False) if isinstance(c.get("steps"), list) else "[]"
            se = c.get("step_expected")
            se_str = json.dumps(se, ensure_ascii=False) if isinstance(se, list) else None
            ra = c.get("run_attachments")
            ra_str = json.dumps(ra, ensure_ascii=False) if isinstance(ra, list) else None
            rr = c.get("run_records")
            rr_str = json.dumps(rr, ensure_ascii=False) if isinstance(rr, list) else None
            sys_id = c.get("system_id")
            if sys_id is not None:
                try:
                    sys_id = int(sys_id)
                except (ValueError, TypeError):
                    sys_id = None
            ex_id = c.get("executor_id")
            if ex_id is not None:
                try:
                    ex_id = int(ex_id)
                except (ValueError, TypeError):
                    ex_id = None
            ex_name = str(c.get("executor_name") or "")[:128]
            pr = str(c.get("priority") or "P2").strip().upper()[:8]
            if pr not in ("P0", "P1", "P2", "P3"):
                pr = "P2"
            cur.execute(
                """INSERT INTO test_cases (id, history_id, title, preconditions, steps, expected, status, last_run_at, run_notes, run_attachments, run_records, created_at, updated_at, system_id, executor_id, executor_name, priority, step_expected)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
                    ra_str,
                    rr_str,
                    c.get("created_at") or "",
                    c.get("updated_at") or "",
                    sys_id,
                    ex_id,
                    ex_name,
                    pr,
                    se_str,
                ),
            )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
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


# ---------------------------------------------------------------------------
# systems 表 CRUD
# ---------------------------------------------------------------------------

def _row_to_system(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "name": row[1] or "",
        "description": row[2] or "",
        "created_at": row[3] or "",
        "updated_at": row[4] or "",
    }


def read_systems() -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, created_at, updated_at FROM systems ORDER BY id ASC")
        rows = cur.fetchall()
        cur.close()
        return [_row_to_system(r) for r in rows]
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def read_system_by_id(system_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, created_at, updated_at FROM systems WHERE id=%s", (int(system_id),))
        row = cur.fetchone()
        cur.close()
        return _row_to_system(row) if row else None
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def create_system(name: str, description: str = "", created_at: str = "", updated_at: str = "") -> dict[str, Any] | None:
    conn = get_connection()
    if conn is None:
        return None
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO systems (name, description, created_at, updated_at) VALUES (%s, %s, %s, %s)",
            (name[:256], description or "", created_at, updated_at),
        )
        new_id = cur.lastrowid
        try:
            conn.commit()
        except Exception:
            pass
        return {"id": new_id, "name": name, "description": description, "created_at": created_at, "updated_at": updated_at}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
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


def update_system(system_id: int, name: str | None = None, description: str | None = None, updated_at: str = "") -> dict[str, Any] | None:
    conn = get_connection()
    if conn is None:
        return None
    cur = None
    try:
        cur = conn.cursor()
        sets: list[str] = []
        params: list[Any] = []
        if name is not None:
            sets.append("name=%s")
            params.append(name[:256])
        if description is not None:
            sets.append("description=%s")
            params.append(description)
        if updated_at:
            sets.append("updated_at=%s")
            params.append(updated_at)
        if not sets:
            return read_system_by_id(system_id)
        params.append(int(system_id))
        cur.execute(f"UPDATE systems SET {', '.join(sets)} WHERE id=%s", tuple(params))
        try:
            conn.commit()
        except Exception:
            pass
        return read_system_by_id(system_id)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
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


def delete_system(system_id: int) -> bool:
    conn = get_connection()
    if conn is None:
        return False
    cur = None
    try:
        cur = conn.cursor()
        try:
            conn.begin()
        except Exception:
            pass
        cur.execute("DELETE FROM requirement_embeddings WHERE system_id=%s", (int(system_id),))
        cur.execute("DELETE FROM requirement_edges WHERE system_id=%s", (int(system_id),))
        cur.execute("DELETE FROM requirement_units WHERE system_id=%s", (int(system_id),))
        cur.execute("DELETE FROM test_cases WHERE system_id=%s", (int(system_id),))
        cur.execute("DELETE FROM screenshot_history WHERE system_id=%s", (int(system_id),))
        cur.execute("DELETE FROM systems WHERE id=%s", (int(system_id),))
        try:
            conn.commit()
        except Exception:
            pass
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
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


def next_system_id() -> int:
    conn = get_connection()
    if conn is None:
        return 1
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM systems")
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


# ---------------------------------------------------------------------------
# 认证 / 权限（依赖 users / roles / permissions / user_sessions 表）
# ---------------------------------------------------------------------------


def auth_permission_codes_for_user(user_id: int) -> list[str]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT p.code FROM permissions p
            INNER JOIN role_permissions rp ON rp.permission_id = p.id
            INNER JOIN users u ON u.role_id = rp.role_id
            WHERE u.id = %s AND u.is_active = 1
            """,
            (int(user_id),),
        )
        out = [str(r[0]) for r in cur.fetchall() if r and r[0]]
        cur.close()
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def auth_validate_token(token: str) -> dict[str, Any] | None:
    if not token or not str(token).strip():
        return None
    tok = str(token).strip()[:128]
    now = int(time.time())
    conn = get_connection()
    if conn is None:
        return None
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.username, u.display_name, u.role_id, u.is_active
            FROM users u
            INNER JOIN user_sessions s ON s.user_id = u.id
            WHERE s.token = %s AND s.expires_at > %s
            """,
            (tok, now),
        )
        row = cur.fetchone()
        if not row or not int(row[4] or 0):
            return None
        uid = int(row[0])
        perms = auth_permission_codes_for_user(uid)
        return {
            "id": uid,
            "username": row[1] or "",
            "display_name": row[2] or "",
            "role_id": int(row[3]) if row[3] is not None else None,
            "permissions": perms,
        }
    except Exception:
        return None
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


_REG_USERNAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,63}$")
_REG_PASSWORD_MIN = 8
_REG_PASSWORD_MAX = 128
_REG_NAME_MAX = 40


def _validate_register_username(username: str) -> str | None:
    u = str(username or "").strip()
    if u.lower() in RESERVED_USERNAMES:
        return "该用户名为系统保留账号，请更换其他用户名"
    if not _REG_USERNAME.fullmatch(u):
        return "用户名须为 3–64 个字符，以英文字母开头，仅含字母、数字、下划线"
    return None


def _validate_register_password(password: str) -> str | None:
    pw = str(password or "")
    if len(pw) < _REG_PASSWORD_MIN or len(pw) > _REG_PASSWORD_MAX:
        return f"密码长度须为 {_REG_PASSWORD_MIN}–{_REG_PASSWORD_MAX} 位"
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "密码须同时包含至少一个字母和一个数字"
    return None


def _validate_register_display_name(display_name: str) -> str | None:
    s = str(display_name or "").strip()
    if len(s) < 1 or len(s) > _REG_NAME_MAX:
        return f"姓名须为 1–{_REG_NAME_MAX} 个字符（不可为空）"
    return None


def auth_register(username: str, password: str, display_name: str) -> tuple[dict[str, Any] | None, str | None]:
    """自助注册：默认角色为 operator。成功返回 (与 auth_login 相同结构, None)，失败返回 (None, 错误文案)。"""
    err = _validate_register_username(username)
    if err:
        return None, err
    err = _validate_register_password(password)
    if err:
        return None, err
    err = _validate_register_display_name(display_name)
    if err:
        return None, err
    u = str(username).strip()
    try:
        from backend.auth_password import hash_password
    except Exception:
        from auth_password import hash_password  # type: ignore
    pw_hash = hash_password(password)
    conn = get_connection()
    if conn is None:
        return None, "数据库不可用"
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM roles WHERE code=%s", ("operator",))
        row = cur.fetchone()
        role_id = int(row[0]) if row else None
        if role_id is None:
            return None, "未找到默认角色，请联系管理员"
        ts = str(int(time.time()))
        cur.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role_id, is_active, created_at, updated_at)
            VALUES (%s,%s,%s,%s,1,%s,%s)
            """,
            (u[:64], pw_hash, str(display_name).strip()[:128], role_id, ts, ts),
        )
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as e:
        try:
            import pymysql  # type: ignore

            if isinstance(e, pymysql.err.IntegrityError):
                return None, "用户名已被占用"
        except Exception:
            pass
        if "Duplicate" in str(e) or "1062" in str(e):
            return None, "用户名已被占用"
        return None, "注册失败，请稍后重试"
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

    out = auth_login(u, password)
    if not out:
        return None, "注册成功但自动登录失败，请手动登录"
    return out, None


def auth_login(username: str, password: str, ttl_seconds: int = 604800) -> dict[str, Any] | None:
    try:
        from backend.auth_password import verify_password
    except Exception:
        from auth_password import verify_password  # type: ignore
    u = str(username or "").strip()
    if not u:
        return None
    conn = get_connection()
    if conn is None:
        return None
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, password_hash, display_name, role_id, is_active FROM users WHERE username=%s",
            (u[:64],),
        )
        row = cur.fetchone()
        if not row or not int(row[4] or 0):
            return None
        uid = int(row[0])
        if not verify_password(password or "", str(row[1] or "")):
            return None
        token = secrets.token_urlsafe(48)
        exp = int(time.time()) + int(ttl_seconds)
        ts = str(int(time.time()))
        cur.execute(
            "INSERT INTO user_sessions (user_id, token, expires_at, created_at) VALUES (%s,%s,%s,%s)",
            (uid, token[:128], exp, ts),
        )
        try:
            conn.commit()
        except Exception:
            pass
        perms = auth_permission_codes_for_user(uid)
        return {
            "token": token,
            "user": {
                "id": uid,
                "username": u,
                "display_name": row[2] or "",
                "role_id": int(row[3]) if row[3] is not None else None,
                "permissions": perms,
            },
        }
    except Exception:
        return None
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


def auth_logout(token: str) -> None:
    tok = str(token or "").strip()[:128]
    if not tok:
        return
    conn = get_connection()
    if conn is None:
        return
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE token=%s", (tok,))
        try:
            conn.commit()
        except Exception:
            pass
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
