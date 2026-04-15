from __future__ import annotations

import json
import socketserver
import threading
import time
import urllib.request
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.simple_server as server_mod


def _req(port: int, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{port}{path}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8") or "null")
        return resp.status, data


def main() -> None:
    srv = socketserver.TCPServer(("127.0.0.1", 0), server_mod.MyHTTPRequestHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)

    ok: list[bool] = []
    status, _ = _req(port, "/api/history/list", {})
    ok.append(status == 200)
    status, _ = _req(port, "/api/cases/list", {})
    ok.append(status == 200)

    status, h = _req(port, "/api/history/create", {"file_name": "smoke_sys_A_B_C_modal.png", "file_url": ""})
    ok.append(status == 201 and isinstance(h, dict) and h.get("id") is not None)
    hid = int(h["id"])

    status, h2 = _req(port, "/api/history/update", {"id": hid, "analysis": "smoke"})
    ok.append(status == 200 and h2.get("analysis") == "smoke")
    status, h3 = _req(port, "/api/history/detail", {"id": hid})
    ok.append(status == 200 and int(h3.get("id") or 0) == hid)

    status, c = _req(
        port,
        "/api/cases/create",
        {"history_id": hid, "title": "smoke-case", "steps": ["s1"], "expected": "ok"},
    )
    ok.append(status == 201 and c.get("id") is not None)
    cid = int(c["id"])

    status, c2 = _req(port, "/api/cases/update", {"id": cid, "status": "pass", "run_notes": "done"})
    ok.append(status == 200 and c2.get("status") == "pass")
    status, c3 = _req(port, "/api/cases/detail", {"id": cid})
    ok.append(status == 200 and int(c3.get("id") or 0) == cid)

    status, _ = _req(port, "/api/cases/delete", {"id": cid})
    ok.append(status == 200)
    status, _ = _req(port, "/api/history/delete", {"id": hid})
    ok.append(status == 200)

    print("smoke-ok" if all(ok) else f"smoke-fail:{ok}")

    srv.shutdown()
    srv.server_close()


if __name__ == "__main__":
    main()
