"""Config reader — project-level defaults and env var overrides."""

from __future__ import annotations

import os
from pathlib import Path


def get_convention_dir() -> Path:
    """Return path to convention YAML directory."""
    env = os.environ.get("ANALOGCHECK_CONVENTION_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "conventions"


def get_default_convention() -> str:
    """Return the default convention name to use."""
    return os.environ.get("ANALOGCHECK_CONVENTION", "cfoa")


def get_ngspice_path() -> str:
    """Return path to ngspice binary."""
    return os.environ.get("ANALOGCHECK_NGSPICE", "ngspice")


def get_port_mapping_var() -> str:
    """Return JSON port mapping from env var, if set."""
    raw = os.environ.get("ANALOGCHECK_PORT_MAPPING")
    if raw:
        import json
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None
