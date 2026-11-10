"""Pytest configuration.

The ``gpwcf`` package uses a src layout and is not installed into the project
virtual environment yet (packaging lands with task 10). Put ``src`` on
``sys.path`` so every test module can import ``gpwcf`` directly.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
