"""SPICE netlist parser — builds a node/device graph from .cir files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Regex patterns
_CONT_RE = re.compile(r"^\s*\+")
_SUBCKT_RE = re.compile(r"^\.subckt\s+(?P<name>\S+)(?P<ports>(\s+\S+)+)", re.IGNORECASE)
_ENDS_RE = re.compile(r"^\.ends", re.IGNORECASE)
_MODEL_RE = re.compile(r"^\.model\s+(?P<name>\S+)\s+(?P<type>\S+)", re.IGNORECASE)
_PARAM_RE = re.compile(r"^\.param\s+", re.IGNORECASE)
_INCLUDE_RE = re.compile(r"^\.include\s+", re.IGNORECASE)
_CONTROL_RE = re.compile(r"^\.(ac|dc|tran|step|ic|nodeset|probe|print|plot|option)", re.IGNORECASE)
_END_RE = re.compile(r"^\.end", re.IGNORECASE)


@dataclass
class Device:
    """A single SPICE element (R, L, C, V, I, X, M, etc.)."""
    name: str
    kind: str  # R, L, C, V, I, X, M, D, Q, etc.
    nodes: list[str]  # node names (0 = ground)
    params: str = ""  # value or parameters as raw text
    model: Optional[str] = None  # .model reference name
    line: int = 0  # source line number
    subckt: Optional[str] = None  # enclosing .subckt name if any


@dataclass
class Subckt:
    """A .subckt / .ends block definition."""
    name: str
    ports: list[str]
    devices: list[Device] = field(default_factory=list)
    line: int = 0


@dataclass
class Netlist:
    """Complete parsed netlist."""
    path: Path
    devices: list[Device] = field(default_factory=list)
    subckts: dict[str, Subckt] = field(default_factory=dict)
    models: dict[str, str] = field(default_factory=dict)  # name -> type
    params: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    control_statements: list[str] = field(default_factory=list)
    title: str = ""

    @property
    def nodes(self) -> set[str]:
        """All unique node names appearing in top-level devices."""
        n: set[str] = set()
        for dev in self.devices:
            n.update(dev.nodes)
        return n

    def device_by_name(self, name: str) -> Optional[Device]:
        for dev in self.devices:
            if dev.name.lower() == name.lower():
                return dev
        for sub in self.subckts.values():
            for dev in sub.devices:
                if dev.name.lower() == name.lower():
                    return dev
        return None


def parse_netlist(path: str | Path) -> Netlist:
    """Parse a .cir or .sp file into a Netlist data structure."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    nl = Netlist(path=path)
    current_subckt: Optional[Subckt] = None
    # Continuation line accumulator
    pending_line: Optional[str] = None

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Handle continuation lines
        if _CONT_RE.match(line):
            if pending_line:
                pending_line += " " + stripped.lstrip("+").strip()
            continue

        # Flush pending line before processing new one
        if pending_line is not None:
            _parse_element_line(pending_line, nl, current_subckt, lineno - 1)
            pending_line = None

        # Comment lines
        if stripped.startswith("*"):
            if lineno == 1:
                nl.title = stripped[1:].strip()
            continue

        # Title line (first non-comment, non-blank line)
        if not nl.title and lineno == 1:
            nl.title = stripped
            continue

        # .subckt
        m = _SUBCKT_RE.match(stripped)
        if m:
            name = m.group("name").lower()
            ports = m.group("ports").strip().split()
            current_subckt = Subckt(name=name, ports=ports, line=lineno)
            nl.subckts[name] = current_subckt
            continue

        # .ends
        if _ENDS_RE.match(stripped):
            current_subckt = None
            continue

        # .model
        m = _MODEL_RE.match(stripped)
        if m:
            nl.models[m.group("name")] = m.group("type")
            continue

        # .param
        if _PARAM_RE.match(stripped):
            nl.params.append(stripped)
            continue

        # .include
        if _INCLUDE_RE.match(stripped):
            nl.includes.append(stripped)
            continue

        # .ac / .dc / .tran / .step / etc.
        if _CONTROL_RE.match(stripped):
            nl.control_statements.append(stripped)
            continue

        # .end
        if _END_RE.match(stripped):
            break

        # Element line
        pending_line = stripped

    # Flush last pending line
    if pending_line is not None:
        _parse_element_line(pending_line, nl, current_subckt, lineno)

    return nl


def _parse_element_line(
    line: str, nl: Netlist, subckt: Optional[Subckt], lineno: int
) -> None:
    """Parse a single element line and add to netlist or subckt."""
    # Strip inline comment ($)
    if "$" in line:
        parts = line.split("$", 1)
        line = parts[0].strip()
        if not line:
            return

    tokens = line.split()
    if not tokens:
        return

    name = tokens[0]
    kind = name[0].upper()
    rest = tokens[1:]

    # X = subcircuit instance: Xname nodes... subckt_name
    # e.g. X_U1 Y X Z O CFOA
    if kind == "X":
        if len(rest) >= 2:
            subckt_name = rest[-1]
            nodes = rest[:-1]
        else:
            subckt_name = ""
            nodes = rest
        device = Device(
            name=name, kind=kind, nodes=nodes,
            params=subckt_name, model=subckt_name, line=lineno,
        )

    # M = MOSFET: Mname D G S B modelname [params...]
    elif kind == "M":
        if len(rest) >= 5:
            nodes = rest[:4]
            model = rest[4]
            params = " ".join(rest[5:])
        elif len(rest) >= 4:
            nodes = rest[:4]
            model = rest[3] if len(rest) > 4 else None
            params = " ".join(rest[4:])
        else:
            nodes = rest
            model = None
            params = ""
        device = Device(
            name=name, kind=kind, nodes=nodes,
            params=params, model=model, line=lineno,
        )

    # D / Q / J / Z (diode, BJT, JFET, MESFET): must have a model name
    elif kind in ("D", "Q", "J", "Z"):
        if len(rest) >= 2:
            nodes = rest[:-1]
            model = rest[-1]
            params = ""
        else:
            nodes = rest
            model = None
            params = ""
        device = Device(
            name=name, kind=kind, nodes=nodes,
            params=params, model=model, line=lineno,
        )

    # V, I (independent sources) — first 2 tokens are nodes N+ N-, rest = params
    elif kind in ("V", "I"):
        if len(rest) >= 2:
            nodes = rest[:2]
            params = " ".join(rest[2:])
        else:
            nodes = rest
            params = ""
        device = Device(
            name=name, kind=kind, nodes=nodes,
            params=params, model=None, line=lineno,
        )

    # R, L, C, K, T, U, Y, S, W — last token is always the value
    else:
        if len(rest) >= 2:
            nodes = rest[:-1]
            params = rest[-1]
        else:
            nodes = rest
            params = ""
        device = Device(
            name=name, kind=kind, nodes=nodes,
            params=params, model=None, line=lineno,
        )

    # Add to correct container
    if subckt is not None:
        subckt.devices.append(device)
    else:
        nl.devices.append(device)

