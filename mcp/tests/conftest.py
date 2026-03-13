import sys
from pathlib import Path

MCP_ROOT = Path(__file__).resolve().parents[1]
root_str = str(MCP_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
