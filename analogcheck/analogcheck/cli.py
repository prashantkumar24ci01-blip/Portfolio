"""CLI entry point for AnalogCheck."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checker, config, report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="analogcheck",
        description="SPICE netlist semantic error checker",
    )
    p.add_argument("netlist", type=str, help="Path to .cir netlist file")
    p.add_argument(
        "-c", "--convention",
        default=config.get_default_convention(),
        help=f"Subcircuit convention (default: {config.get_default_convention()})",
    )
    p.add_argument(
        "--convention-dir",
        type=str,
        help="Custom convention YAML directory",
    )
    p.add_argument(
        "--port-mapping",
        type=str,
        help=(
            "JSON mapping of netlist port labels to convention ports. "
            'e.g. \'{"1":"Y","2":"X","3":"Z","4":"O"}\''
        ),
    )
    p.add_argument(
        "--format",
        choices=["json", "md"],
        default="json",
        dest="output_format",
        help="Output format (default: json)",
    )
    p.add_argument(
        "-o", "--output",
        type=str,
        help="Write output to file instead of stdout",
    )
    p.add_argument(
        "--no-sim",
        action="store_true",
        help="Skip simulation (parser-only mode)",
    )
    p.add_argument(
        "--llm",
        choices=["auto", "on", "off"],
        default="auto",
        help="LLM reasoning (auto=use if configured, on=require, off=skip)",
    )
    p.add_argument(
        "--rag",
        action="store_true",
        help="Enable RAG-enhanced LLM reasoning (index PSpice docs + IC errors)",
    )
    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()

    netlist_path = Path(args.netlist)
    if not netlist_path.exists():
        print(f"Error: netlist not found: {netlist_path}", file=sys.stderr)
        return 1

    # Port mapping
    port_mapping = None
    if args.port_mapping:
        import json
        try:
            port_mapping = json.loads(args.port_mapping)
        except json.JSONDecodeError as e:
            print(f"Error: --port-mapping is not valid JSON: {e}", file=sys.stderr)
            return 1

    # LLM mode
    llm_map = {"auto": None, "on": True, "off": False}
    enable_llm = llm_map[args.llm]

    # RAG mode: build knowledge base on first use
    enable_rag = args.rag
    if enable_rag:
        from . import rag
        n = rag.build_knowledge_base(force=False)
        if n == 0:
            print("RAG: No knowledge indexed yet. Run with --rag again after KB is ready.", file=sys.stderr)

    # Run checks
    conv_dir = Path(args.convention_dir) if args.convention_dir else None
    results = checker.check_netlist(
        netlist_path,
        convention_name=args.convention,
        convention_dir=conv_dir,
        port_mapping=port_mapping,
        enable_llm=enable_llm,
        enable_rag=enable_rag,
        run_sim=not args.no_sim,
    )

    # Format output
    if args.output_format == "md":
        output = report.format_markdown(results)
    else:
        output = report.format_json(results)

    # Write or print
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return report.exit_code_from_results(results)


if __name__ == "__main__":
    sys.exit(main())
