from __future__ import annotations

# Backward-compatible facade.
# Keep import path `backend.services.case_generation` stable while
# implementation is decomposed into `case_generation_core.py`.
try:
    from .case_generation_core import generate_cases_from_history
except Exception:
    from case_generation_core import generate_cases_from_history  # type: ignore

__all__ = ["generate_cases_from_history"]
