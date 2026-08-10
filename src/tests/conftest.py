from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1]
EDGE = SRC / "main" / "edge"

if str(EDGE) not in sys.path:
    sys.path.insert(0, str(EDGE))
