"""Load a local Gemini credential without storing it in the repository."""
import os
from pathlib import Path


def load_local_gemini_key():
    """Preserve explicit environment keys; otherwise read the local key file."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    configured = os.environ.get("GEMINI_API_KEY_FILE")
    path = (Path(configured).expanduser() if configured else
            Path.home() / "OneDrive" / "Documents" / "TQD" / "GEMINI_API_KEY.txt")
    if not path.is_file():
        return
    key = path.read_text(encoding="utf-8-sig").strip()
    if key:
        os.environ["GEMINI_API_KEY"] = key
