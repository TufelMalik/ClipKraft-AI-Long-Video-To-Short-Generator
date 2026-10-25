import os
import sys

# Make the repo root and backend subdirectories importable so tests can import modules directly.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_root = os.path.join(_repo_root, "backend")
for _p in [
    _repo_root,
    _backend_root,
    os.path.join(_backend_root, "pipeline"),
    os.path.join(_backend_root, "services"),
    os.path.join(_backend_root, "utils"),
    os.path.join(_backend_root, "api"),
]:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# backend/main.py is an ASGI compatibility entrypoint, not the video engine.
# Keep the repository's main.py ahead of it, as when running the pipeline CLI.
sys.path.remove(_repo_root)
sys.path.insert(0, _repo_root)


# Tests always run the app in self-host (BYOK) mode. app.py freezes
# BILLING_ENABLED at import time and load_dotenv never overrides an existing
# variable, so this must be set here — before any test module imports app — or
# the suite's behavior would depend on the developer's personal .env.
os.environ["BILLING_ENABLED"] = "0"
