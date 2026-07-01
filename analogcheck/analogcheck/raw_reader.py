"""Minimal ASCII .raw file reader for ngspice simulation output."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class RawData:
    """Parsed .raw file contents."""
    title: str = ""
    date: str = ""
    plot_name: str = ""
    flags: list[str] = field(default_factory=list)
    n_variables: int = 0
    n_points: int = 0
    variables: list[dict[str, Any]] = field(default_factory=list)
    data: np.ndarray | None = None  # shape (n_points, n_variables)


def read_raw(path: str | Path) -> RawData:
    """Read an ngspice ASCII .raw file and return structured data."""
    raw = RawData()
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Parse header
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("Title:"):
            raw.title = line[6:].strip()
        elif line.startswith("Date:"):
            raw.date = line[5:].strip()
        elif line.startswith("Plotname:"):
            raw.plot_name = line[9:].strip()
        elif line.startswith("Flags:"):
            raw.flags = line[6:].strip().split()
        elif line.startswith("No. Variables:"):
            raw.n_variables = int(line[14:].strip())
        elif line.startswith("No. Points:"):
            raw.n_points = int(line[11:].strip())
        elif line.startswith("Variables:"):
            i += 1
            # Read variable definitions (count = n_variables)
            for _ in range(raw.n_variables):
                if i >= len(lines):
                    break
                var_line = lines[i].strip()
                # Format: idx name type
                # e.g. 0 voltage(vout) voltage
                parts = var_line.split()
                if len(parts) >= 3:
                    raw.variables.append({
                        "index": int(parts[0]),
                        "name": _clean_var_name(parts[1]),
                        "type": parts[2],
                    })
                i += 1
            # Now at "Values:" line
            if i < len(lines) and lines[i].strip().lower().startswith("values"):
                i += 1
                # Read binary or ASCII data
                raw.data = _read_ascii_data(lines[i:], raw.n_points, raw.n_variables)
            break
        i += 1

    return raw


def _clean_var_name(name: str) -> str:
    """Remove wrapping parentheses from variable names like voltage(vout)."""
    # Already clean enough for our purposes — keep as-is
    return name


def _read_ascii_data(
    data_lines: list[str], n_points: int, n_vars: int
) -> np.ndarray:
    """Parse ASCII data block into numpy array."""
    arr = np.zeros((n_points, n_vars))
    row = 0
    for line in data_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip non-data lines (binary marker, trailing comments)
        if stripped.lower().startswith("binary"):
            continue
        parts = stripped.split()
        if len(parts) >= n_vars:
            try:
                arr[row] = [float(p) for p in parts[:n_vars]]
                row += 1
            except ValueError:
                continue
            if row >= n_points:
                break
    return arr
