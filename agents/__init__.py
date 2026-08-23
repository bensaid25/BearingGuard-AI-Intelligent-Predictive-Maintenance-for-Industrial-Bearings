"""
agents/__init__.py
====================

Makes `agents` a package, and ensures the project root is on sys.path so
modules in here can do `from api.schemas import ...` regardless of which
directory this is run from (same fix used in tools/test_api.py).
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
