"""Services level inventory router re-export facade."""

import os
import sys

_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from services.api.routers.inventory import router  # noqa: F401

__all__ = ["router"]
