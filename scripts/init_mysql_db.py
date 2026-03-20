#!/usr/bin/env python3
"""在本地 MySQL 中创建库 llm_case_system 及表（screenshot_history、test_cases）。需先在 config.local.json 中配置 mysql。"""
import sys
from pathlib import Path

# 保证从项目根目录可导入 backend
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from backend import db_mysql
except Exception:
    import db_mysql

if __name__ == "__main__":
    ok, msg = db_mysql.init_database()
    print(msg)
    sys.exit(0 if ok else 1)
