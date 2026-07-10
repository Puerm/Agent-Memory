"""Source-checkout launcher for ``python -m memory_lab``.

The distributable package lives under ``src/``.  Extending this package path
lets the documented commands work from a fresh source checkout without first
installing the project; installed environments use the normal ``src`` package.
"""

from pathlib import Path

__path__.append(str(Path(__file__).resolve().parent.parent / "src" / "memory_lab"))
