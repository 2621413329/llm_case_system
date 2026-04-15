"""密码哈希（仅标准库，PBKDF2-SHA256）。"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 600_000
_PREFIX = "pbkdf2_sha256"


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("ascii"), _ITERATIONS)
    return f"{_PREFIX}${_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    if not plain or not stored:
        return False
    parts = str(stored).split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
    except ValueError:
        return False
    salt, want_hex = parts[2], parts[3]
    try:
        want = bytes.fromhex(want_hex)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("ascii"), iterations)
    return hmac.compare_digest(dk, want)
