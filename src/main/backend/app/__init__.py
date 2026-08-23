"""NetraPi Pi-ingest FastAPI app. Puts `src/main` on sys.path so `db` imports resolve."""

from __future__ import annotations

import sys
from pathlib import Path

_MAIN_DIR = Path(__file__).resolve().parents[2]
_main_str = str(_MAIN_DIR)
if _main_str not in sys.path:
    sys.path.insert(0, _main_str)
