"""
Compatibility entrypoint for running OpenShorts backend.
Allows running:
  uvicorn backend.main:app --reload --port 8000
as well as:
  uvicorn app:app --reload --port 8000
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app import app
