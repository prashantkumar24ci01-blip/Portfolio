"""LLM reasoning layer — provider-agnostic via env vars."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

_LLM_WARNING = (
    "AnalogCheck LLM reasoning: no LLM configured. "
    "Set ANALOGCHECK_LLM_ENDPOINT, ANALOGCHECK_LLM_API_KEY, and ANALOGCHECK_LLM_MODEL "
    "for semantic analysis of simulation results.\n"
    "Example:\n"
    '  export ANALOGCHECK_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"\n'
    '  export ANALOGCHECK_LLM_API_KEY="sk-..."\n'
    '  export ANALOGCHECK_LLM_MODEL="gpt-4o"\n'
)


def llm_available() -> bool:
    """Check if LLM env vars are configured."""
    return bool(
        os.environ.get("ANALOGCHECK_LLM_ENDPOINT")
        and os.environ.get("ANALOGCHECK_LLM_API_KEY")
    )


def llm_warning() -> str:
    """Return setup instructions if LLM not configured."""
    return _LLM_WARNING


def query_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> Optional[str]:
    """Query the configured LLM and return text response.

    Reads env vars:
      ANALOGCHECK_LLM_ENDPOINT  — full URL like .../chat/completions
      ANALOGCHECK_LLM_API_KEY   — API key
      ANALOGCHECK_LLM_MODEL     — model identifier

    Compatible with OpenAI API format (OpenAI, OpenRouter, Nous, etc.).
    """
    if not llm_available():
        return None

    endpoint = os.environ["ANALOGCHECK_LLM_ENDPOINT"]
    api_key = os.environ["ANALOGCHECK_LLM_API_KEY"]
    model = os.environ.get("ANALOGCHECK_LLM_MODEL", "gpt-4o")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = httpx.post(
            endpoint,
            json=body,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return json.dumps({"error": f"LLM query failed: {e}"})


def build_check_prompt(
    netlist_text: str,
    raw_text: str,
    convention: dict[str, Any],
    port_mapping: Optional[dict[str, str]] = None,
    rag_context: Optional[str] = None,
) -> tuple[str, str]:
    """Build system + user prompts for LLM-based port-convention checking.

    Returns:
        (system_prompt, user_prompt)
    """
    system = (
        "You are a semiconductor analog circuit verification assistant. "
        "Your role is to check whether the port labeling in a SPICE netlist "
        "matches the expected convention for the given subcircuit type.\n\n"
        f"Convention for this circuit:\n{json.dumps(convention, indent=2)}\n\n"
        "Identify any port mislabeling, signal-flow violations, or "
        "admittance-map mismatches. Return your analysis as a JSON array "
        "of check results. Each result must have:\n"
        '  - "severity": "pass" | "warn" | "fail"\n'
        '  - "check_type": "port_mislabel" | "topology_mismatch" | "sim_anomaly"\n'
        '  - "rule_id": the convention rule that applies\n'
        '  - "device": device name\n'
        '  - "reason": explanation in 1-2 sentences\n'
        '  - "expected": what should be true\n'
        '  - "actual": what the simulation suggests is true\n'
        '  - "confidence": float 0.0 to 1.0\n\n'
        'Return ONLY the JSON array, no other text.'
    )

    mapping_text = ""
    if port_mapping:
        mapping_text = f"\nUser-provided port mapping: {json.dumps(port_mapping, indent=2)}"

    user = (
        f"Netlist:\n```spice\n{netlist_text}\n```\n\n"
        f"Simulation output (.raw):\n```\n{raw_text[:4000]}\n```\n"
        f"{mapping_text}\n\n"
        f"Analyze and return JSON check results."
    )

    if rag_context:
        user = f"{rag_context}\n\n{user}"

    return system, user
