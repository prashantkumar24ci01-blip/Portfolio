"""Checker orchestrator — runs deterministic checks + optional LLM reasoning."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import config, conventions, llm_reasoning, parser, raw_reader, runner


def check_netlist(
    netlist_path: str | Path,
    *,
    convention_name: Optional[str] = None,
    convention_dir: Optional[Path] = None,
    port_mapping: Optional[dict[str, str]] = None,
    enable_llm: Optional[bool] = None,
    enable_rag: bool = False,
    run_sim: bool = True,
) -> list[dict[str, Any]]:
    """Run full AnalogCheck pipeline on a netlist.

    Args:
        netlist_path: Path to .cir file.
        convention_name: Subcircuit convention to check against. Default from env.
        convention_dir: Custom convention directory.
        port_mapping: Optional {netlist_port_label: convention_port} mapping.
        enable_llm: If True, run LLM reasoning. None=auto (use if configured).
        run_sim: If True, run ngspice and read .raw output.

    Returns:
        List of check result dicts.
    """
    results: list[dict[str, Any]] = []

    # Phase 1: Parse netlist
    nl = parser.parse_netlist(netlist_path)
    results.append({
        "severity": "pass" if nl.devices else "fail",
        "check_type": "topology_mismatch",
        "rule_id": "parse_complete",
        "device": "netlist",
        "expected": "Netlist parses with >= 1 device",
        "actual": f"{len(nl.devices)} top-level devices, {len(nl.subckts)} subckts",
        "reason": f"Parsed {len(nl.devices)} devices, {len(nl.subckts)} subcircuits",
    })

    # Phase 1b: Generic SPICE netlist health checks
    results.extend(_run_netlist_health_checks(nl))

    # Phase 2: Load convention
    conv_name = convention_name or config.get_default_convention()
    conv_dir = convention_dir or config.get_convention_dir()
    try:
        conv = conventions.load_convention(conv_name, conv_dir)
    except FileNotFoundError as e:
        results.append({
            "severity": "fail",
            "check_type": "topology_mismatch",
            "rule_id": "convention_not_found",
            "device": "convention",
            "expected": f"Convention '{conv_name}' exists",
            "actual": str(e),
            "reason": "Cannot load convention file",
        })
        return results

    # Phase 3: Device-level deterministic checks
    # Check for X devices (subcircuit instantiations)
    x_devs = [d for d in nl.devices if d.kind == "X"]
    if not x_devs:
        results.append({
            "severity": "warn",
            "check_type": "topology_mismatch",
            "rule_id": "no_subckt_instances",
            "device": "netlist",
            "expected": "At least one subcircuit (X) instance",
            "actual": "0 X devices found",
            "reason": "No subcircuit instances to check against convention",
        })

    for dev in x_devs:
        # Check port count matches
        expected_ports = list(conv.get("ports", {}).keys())
        if len(dev.nodes) != len(expected_ports):
            results.append({
                "severity": "fail",
                "check_type": "topology_mismatch",
                "rule_id": "port_count_mismatch",
                "device": dev.name,
                "location": {"line": dev.line},
                "expected": f"{len(expected_ports)} ports: {expected_ports}",
                "actual": f"{len(dev.nodes)} nodes: {dev.nodes}",
                "reason": (
                    f"Device {dev.name} has {len(dev.nodes)} connections "
                    f"but {conv_name} expects {len(expected_ports)}"
                ),
            })

    # Phase 4: Simulation and .raw analysis
    raw_data = None
    if run_sim and nl.control_statements:
        try:
            raw_data = runner.run_with_raw(netlist_path)
            results.append({
                "severity": "pass",
                "check_type": "sim_anomaly",
                "rule_id": "sim_complete",
                "device": "ngspice",
                "expected": "Simulation completes successfully",
                "actual": f"{raw_data.n_points} data points, {raw_data.n_variables} variables",
                "reason": f"Simulation OK ({raw_data.plot_name})",
            })
        except (RuntimeError, FileNotFoundError) as e:
            results.append({
                "severity": "fail",
                "check_type": "sim_anomaly",
                "rule_id": "sim_failed",
                "device": "ngspice",
                "expected": "ngspice exits with code 0",
                "actual": str(e),
                "reason": f"Simulation failed",
            })

    # Phase 5: LLM reasoning (optional)
    llm_enabled = enable_llm if enable_llm is not None else llm_reasoning.llm_available()

    if not llm_enabled and enable_llm is not False:
        # Print warning only if no LLM configured (not explicitly disabled)
        import sys
        print(llm_reasoning.llm_warning(), file=sys.stderr)

    if llm_enabled and raw_data is not None:
        try:
            netlist_text = Path(netlist_path).read_text(encoding="utf-8")
            raw_text_lines = str(raw_data)

            # Build RAG context if enabled
            rag_context = ""
            if enable_rag:
                try:
                    from . import rag as rag_module
                    rag_context = rag_module.build_rag_context(
                        netlist_text,
                        sim_error=str(raw_data) if raw_data else None,
                    )
                except Exception as e:
                    rag_context = f"[RAG error: {e}]"

            system, user = llm_reasoning.build_check_prompt(
                netlist_text, raw_text_lines, conv, port_mapping,
                rag_context=rag_context if enable_rag else None,
            )
            llm_response = llm_reasoning.query_llm(system, user)
            if llm_response:
                import json
                try:
                    llm_results = json.loads(llm_response)
                    if isinstance(llm_results, list):
                        for r in llm_results:
                            r["_source"] = "llm"
                        results.extend(llm_results)
                except (json.JSONDecodeError, TypeError):
                    results.append({
                        "severity": "warn",
                        "check_type": "sim_anomaly",
                        "rule_id": "llm_parse_failed",
                        "device": "llm",
                        "expected": "Valid JSON from LLM",
                        "actual": "Parse failed",
                        "reason": "LLM response was not valid JSON",
                    })
        except Exception as e:
            results.append({
                "severity": "warn",
                "check_type": "sim_anomaly",
                "rule_id": "llm_error",
                "device": "llm",
                "expected": "LLM reasoning completes",
                "actual": str(e),
                "reason": f"LLM query failed",
            })

    return results


def _run_netlist_health_checks(nl: parser.Netlist) -> list[dict[str, Any]]:
    """Run generic SPICE netlist health checks (ground, title, floating, etc.)."""
    results: list[dict[str, Any]] = []
    src = "netlist"

    # --- 1. Ground check ---
    all_nodes: set[str] = set()
    for dev in nl.devices:
        all_nodes.update(dev.nodes)
    for sub in nl.subckts.values():
        for dev in sub.devices:
            all_nodes.update(dev.nodes)

    has_ground = "0" in all_nodes or "gnd" in all_nodes or "GND" in all_nodes
    if not has_ground:
        results.append({
            "severity": "fail",
            "check_type": "topology_mismatch",
            "rule_id": "missing_ground",
            "device": src,
            "expected": "Node 0 or GND present in netlist",
            "actual": f"Nodes: {sorted(all_nodes)[:10]}",
            "reason": "No ground node (0/GND) found - SPICE requires a global ground reference",
        })

    # --- 2. Title line check ---
    if not nl.title:
        results.append({
            "severity": "error",
            "check_type": "topology_mismatch",
            "rule_id": "missing_title",
            "device": src,
            "expected": "First line is a title/comment",
            "actual": "First line starts with a component or is blank",
            "reason": "SPICE requires first line to be a title or comment. Add * or title line.",
        })

    # --- 3. Duplicate component names ---
    name_counts: dict[str, int] = {}
    for dev in nl.devices:
        name_counts[dev.name.lower()] = name_counts.get(dev.name.lower(), 0) + 1
    for sub in nl.subckts.values():
        for dev in sub.devices:
            name_counts[dev.name.lower()] = name_counts.get(dev.name.lower(), 0) + 1

    for n, cnt in name_counts.items():
        if cnt > 1:
            first_line = None
            for dev in nl.devices:
                if dev.name.lower() == n:
                    first_line = dev.line
                    break
            if first_line is None:
                for sub in nl.subckts.values():
                    for dev in sub.devices:
                        if dev.name.lower() == n:
                            first_line = dev.line
                            break
                    if first_line:
                        break
            results.append({
                "severity": "warn",
                "check_type": "topology_mismatch",
                "rule_id": "duplicate_name",
                "device": n,
                "location": {"line": first_line} if first_line else None,
                "expected": "Unique component reference designator",
                "actual": f"Found {cnt} instances of {n}",
                "reason": f"Duplicate component name {n} found {cnt} times",
            })

    # --- 4. Floating nodes ---
    node_connections: dict[str, int] = {}
    for dev in nl.devices:
        for node in dev.nodes:
            if node and node not in ("0", "GND", "gnd"):
                node_connections[node] = node_connections.get(node, 0) + 1
    for sub in nl.subckts.values():
        for dev in sub.devices:
            for node in dev.nodes:
                if node and node not in ("0", "GND", "gnd"):
                    node_connections[node] = node_connections.get(node, 0) + 1

    floating = [n for n, c in node_connections.items() if c < 2]
    for node in sorted(floating):
        results.append({
            "severity": "warn",
            "check_type": "topology_mismatch",
            "rule_id": "floating_node",
            "device": src,
            "expected": f"Node {node} has >= 2 connections",
            "actual": f"Node {node} has {node_connections[node]} connection(s)",
            "reason": f"Node {node} is floating ({node_connections[node]} connection). Add R to ground.",
        })

    # --- 5. M vs MEG multiplier check ---
    m_vals: list[tuple[str, int, str]] = []
    for dev in nl.devices:
        if dev.kind in ("R", "L", "C", "K") and dev.params:
            import re
            for m in re.finditer(r"\b(\d+\.?\d*)M\b", dev.params):
                m_vals.append((dev.name, dev.line, m.group(1)))
    for sub in nl.subckts.values():
        for dev in sub.devices:
            if dev.kind in ("R", "L", "C", "K") and dev.params:
                for m in re.finditer(r"\b(\d+\.?\d*)M\b", dev.params):
                    m_vals.append((dev.name, dev.line, m.group(1)))

    for dname, dline, val in m_vals:
        results.append({
            "severity": "warn",
            "check_type": "topology_mismatch",
            "rule_id": "milli_vs_mega",
            "device": dname,
            "location": {"line": dline} if dline else None,
            "expected": f"Value {val}M unambiguous",
            "actual": f"Value {val}M on {dname} is ambiguous",
            "reason": (f"{val}M is read as {float(val)*1e-3} (milli) by SPICE, "
                       f"not {float(val)*1e6} (mega). Use {val}MEG or {val}e6."),
        })

    return results
