"""Report formatter — JSON (canonical) and Markdown (derived view)."""

from __future__ import annotations

import json
from typing import Any


def format_json(results: list[dict[str, Any]], indent: int = 2) -> str:
    """Format check results as JSON."""
    return json.dumps(results, indent=indent)


def format_markdown(results: list[dict[str, Any]]) -> str:
    """Format check results as a human-readable Markdown table."""
    if not results:
        return "**No checks performed.**\n"

    # Summary counts
    fails = sum(1 for r in results if r.get("severity") == "fail")
    warns = sum(1 for r in results if r.get("severity") == "warn")
    passes = sum(1 for r in results if r.get("severity") == "pass")

    summary = (
        f"**AnalogCheck Report**\n\n"
        f"| Severity | Count |\n"
        f"|----------|-------|\n"
        f"| ❌ Fail  | {fails} |\n"
        f"| ⚠️ Warn  | {warns} |\n"
        f"| ✅ Pass  | {passes} |\n\n"
    )

    # Detail table
    table = (
        "| # | Severity | Check Type | Device | Rule | Reason |\n"
        "|---|----------|------------|--------|------|--------|\n"
    )

    for i, r in enumerate(results, 1):
        sev_icon = {"fail": "❌", "warn": "⚠️", "pass": "✅"}.get(
            r.get("severity", ""), "?"
        )
        sev = r.get("severity", "")
        ctype = r.get("check_type", "")
        device = r.get("device", "")
        rule = r.get("rule_id", "")
        reason = r.get("reason", "")
        confidence = r.get("confidence")
        conf_str = f" (conf: {confidence:.2f})" if confidence is not None else ""
        table += (
            f"| {i} | {sev_icon} {sev} | {ctype} | {device} | "
            f"{rule} | {reason}{conf_str} |\n"
        )

    return summary + table


def exit_code_from_results(results: list[dict[str, Any]]) -> int:
    """Return exit code: count of 'fail' severity results."""
    return sum(1 for r in results if r.get("severity") == "fail")
