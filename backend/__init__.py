"""
ClipKraft Backend Architecture Package.

Subpackages:
- pipeline: Video processing, computer vision, audio, layouts, subtitle rendering.
- services: LLM integration, Gemini worker, SaaS shorts, storage backends.
- api: MCP protocol server, stdio runner, UI bridges, media streaming auth.
- utils: URL security, proxy rotation, yt-dlp clients, social metrics.
"""
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
for _sub in ["pipeline", "services", "api", "utils"]:
    _path = os.path.join(_BACKEND_DIR, _sub)
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)
