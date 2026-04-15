from __future__ import annotations

# Backward-compatible facade.
# Keep import path `backend.requirement_network` stable while
# implementation is decomposed into `requirement_network_core.py`.
try:
    from .requirement_network_core import *  # type: ignore  # noqa: F401,F403
except Exception:
    from requirement_network_core import *  # type: ignore  # noqa: F401,F403
