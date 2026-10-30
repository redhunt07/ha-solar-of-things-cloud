"""Load the integration modules without importing Home Assistant.

The package ``__init__`` needs Home Assistant, but the parser and the session
renewal logic are plain Python. Registering a namespace-like package lets the
offline tests exercise them without a full HA installation.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "solar_of_things_cloud"

if "solar_of_things_cloud" not in sys.modules:
    package = types.ModuleType("solar_of_things_cloud")
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["solar_of_things_cloud"] = package
