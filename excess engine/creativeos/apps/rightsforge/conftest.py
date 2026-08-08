import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE / "src"))

# The shared CreativeOS platform, found by searching upward rather than by
# counting parents — a fixed depth breaks silently the moment an app moves.
for parent in _HERE.resolve().parents:
    if (parent / "src" / "creativeos_engine").is_dir():
        sys.path.insert(0, str(parent / "src"))
        break
