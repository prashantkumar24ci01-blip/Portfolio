"""ngspice subprocess runner — executes netlists and captures .raw output."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .raw_reader import RawData, read_raw


def run_ngspice(
    netlist_path: str | Path,
    *,
    raw_path: Optional[str | Path] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run ngspice -b on a netlist, saving .raw output.

    Args:
        netlist_path: Path to .cir file.
        raw_path: Where to write .raw output. Auto-tempfile if None.
        timeout: Seconds before subprocess is killed.

    Returns:
        subprocess.CompletedProcess with stdout/stderr captured.
    """
    netlist_path = Path(netlist_path).resolve()
    if not netlist_path.exists():
        raise FileNotFoundError(f"Netlist not found: {netlist_path}")

    if raw_path is None:
        raw_file = tempfile.NamedTemporaryFile(
            suffix=".raw", delete=False, mode="w"
        )
        raw_path = raw_file.name
        raw_file.close()

    raw_path = Path(raw_path).resolve()

    cmd = ["ngspice", "-b", str(netlist_path), "-r", str(raw_path)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ngspice failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-2000:]}\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    return result


def run_with_raw(netlist_path: str | Path, **kwargs) -> RawData:
    """Run ngspice and return parsed .raw data."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        raw_path = f.name

    try:
        run_ngspice(netlist_path, raw_path=raw_path, **kwargs)
        return read_raw(raw_path)
    finally:
        Path(raw_path).unlink(missing_ok=True)
