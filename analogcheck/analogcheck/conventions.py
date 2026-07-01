"""Convention loader — reads per-subckt-type YAML configs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

# Built-in convention directory relative to project root
_BUILTIN_DIR = Path(__file__).resolve().parent.parent / "conventions"


def list_conventions(convention_dir: Optional[Path] = None) -> list[str]:
    """List available convention names (without .yaml extension)."""
    d = convention_dir or _BUILTIN_DIR
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.yaml") if f.stem != "conventions")


def load_convention(
    name: str,
    convention_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Load a convention YAML by name.

    Searches custom convention_dir first, then built-in conventions/.
    """
    d = convention_dir or _BUILTIN_DIR
    candidate = d / f"{name}.yaml"
    if not candidate.exists():
        # Fall back to built-in
        candidate = _BUILTIN_DIR / f"{name}.yaml"

    if not candidate.exists():
        available = list_conventions(convention_dir)
        raise FileNotFoundError(
            f"Convention '{name}' not found. "
            f"Available: {available}"
        )

    with open(candidate, encoding="utf-8") as f:
        return yaml.safe_load(f)
