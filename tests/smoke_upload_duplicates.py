from __future__ import annotations

import json
import uuid
import urllib.request


def upload(base: str, filename: str) -> tuple[int, dict]:
    boundary = "----CursorBoundary" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + b"PNGDATA" + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url=f"{base}/api/upload",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        return resp.status, payload


def history_count(base: str) -> int:
    req = urllib.request.Request(
        url=f"{base}/api/history/list",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace") or "[]")
        return len(data) if isinstance(data, list) else -1


def delete_history(base: str, rid: int) -> None:
    req = urllib.request.Request(
        url=f"{base}/api/history/delete",
        data=json.dumps({"id": rid}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10):
        pass


def main() -> None:
    base = "http://127.0.0.1:5000"
    before = history_count(base)
    created_ids: list[int] = []
    try:
        for _ in range(2):
            status, payload = upload(base, "dup_same_A_B_C.png")
            if status != 201:
                raise RuntimeError(f"upload failed: status={status}, payload={payload}")
            rid = int(payload.get("id") or 0)
            if rid:
                created_ids.append(rid)
        after = history_count(base)
        print(f"before={before}, after={after}, delta={after - before}")
        print("duplicate_upload_ok" if (after - before) >= 2 else "duplicate_upload_fail")
    finally:
        for rid in created_ids:
            try:
                delete_history(base, rid)
            except Exception:
                pass


if __name__ == "__main__":
    main()
