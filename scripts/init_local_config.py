#!/usr/bin/env python3
"""首次启用 MySQL + 认证：从 local.example.yaml 生成 config/local.yaml（已 .gitignore）。"""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    dst = root / "config" / "local.yaml"
    src = root / "config" / "local.example.yaml"
    if dst.exists():
        print(f"已存在，跳过: {dst}")
        return 0
    if not src.exists():
        print(f"缺少模板: {src}")
        return 1
    text = src.read_text(encoding="utf-8")
    text = text.replace("password: YOUR_MYSQL_PASSWORD", 'password: ""')
    dst.write_text(text, encoding="utf-8")
    print(f"已创建: {dst}")
    print("请按需修改 mysql.password、API Key；然后重启后端，控制台应出现 [auth] 认证已启用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
