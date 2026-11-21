"""Services level main FastAPI application re-export facade."""

import os
import sys

_API_DIR = os.path.join(os.path.dirname(__file__), "api")
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from main import app, create_app  # noqa: F401

__all__ = ["app", "create_app"]
