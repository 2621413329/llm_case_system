#!/usr/bin/env python3
"""
统一后端启动入口（推荐）。

说明：
- 该脚本现在直接启动 `backend/simple_server.py` 中的完整路由集合，
  包含 POST 风格 CRUD（如 `/api/history/list`）与需求分析/向量相关接口。
"""

from __future__ import annotations

import socketserver
import sys


def main() -> int:
    try:
        from backend.simple_server import MyHTTPRequestHandler, PORT
    except Exception as e:
        print(f"加载后端主服务失败: {e}")
        return 1

    print("=== LLM Case System Backend ===")
    print(f"Python version: {sys.version}")
    print("提示：MySQL 可用且 auth.enabled=true 时启用认证（导入 simple_server 时打印 [auth] 行）。")
    print("      若尚无 config/local.yaml，请先执行: python scripts/init_local_config.py")
    print(f"Starting simple HTTP server on port {PORT}...")
    print(f"Server will be available at http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), MyHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n正在关闭服务器...")
            httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
