from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1]
MAIN = SRC / "main"
EDGE = MAIN / "edge"

if str(MAIN) not in sys.path:
    sys.path.insert(0, str(MAIN))
if str(EDGE) not in sys.path:
    sys.path.insert(0, str(EDGE))
