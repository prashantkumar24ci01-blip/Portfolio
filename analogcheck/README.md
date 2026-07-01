# AnalogCheck ⚡ SPICE Netlist Semantic Error Checker

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com)

CLI tool that catches **semantic errors** in SPICE netlists — bugs that simulators pass silently but produce wrong physical results (port-label swaps, missing ground, M vs MEG confusion, floating nodes).

**Deterministic parsing + ngspice subprocess + optional RAG-enhanced LLM reasoning.**

## Features

✔ **5 deterministic checks** — floating nodes, missing ground, duplicate names, missing title, M vs MEG multiplier  
✔ **ngspice integration** — subprocess runner with .raw output reader  
✔ **RAG-enhanced LLM** — retrieves 20+ IC error patterns (LM741, LM358, AD844 pinouts) + PSpice convergence docs from ChromaDB  
✔ **Two output formats** — JSON (canonical) and Markdown (human-readable tables)  
✔ **Provider-agnostic LLM** — works with OpenAI, OpenRouter, Anthropic, any OpenAI-compatible API  

## Quick Start

```bash
pip install -e .

# Deterministic checks only
python -m analogcheck tests/netlists/cfoa_inverting_amp.cir --no-sim --format md

# With simulation
python -m analogcheck tests/netlists/cfoa_inverting_amp.cir --format md

# With LLM + RAG
export ANALOGCHECK_LLM_ENDPOINT="https://openrouter.ai/api/v1/chat/completions"
export ANALOGCHECK_LLM_API_KEY="sk-..."
export ANALOGCHECK_LLM_MODEL="deepseek/deepseek-v4-flash"
python -m analogcheck netlist.cir --llm on --rag
```

## Example

```bash
$ python -m analogcheck tests/netlists/missing_ground.cir --no-sim --format md
```

| Severity | Check Type | Device | Rule | Reason |
|----------|-----------|--------|------|--------|
| ❌ fail | topology_mismatch | netlist | missing_ground | No ground node (0/GND) found |
| ⚠️ warn | topology_mismatch | netlist | no_subckt_instances | No subcircuit instances |

## Architecture

```
netlist.cir → token-split parser → Device/Subckt data structures
           → deterministic checks (5 rules)
           → ngspice subprocess → .raw reader
           → RAG query (ChromaDB: 35 chunks)
           → LLM diagnosis with RAG context → JSON / Markdown
```

## Project Structure

```
analogcheck/
├── analogcheck/
│   ├── checker.py           # Pipeline orchestrator + health checks
│   ├── parser.py            # Token-split SPICE parser
│   ├── rag.py               # ChromaDB + sentence-transformers RAG
│   ├── llm_reasoning.py     # Provider-agnostic LLM client
│   ├── runner.py            # ngspice subprocess manager
│   ├── conventions.py       # YAML convention loader
│   ├── knowledge/
│   │   ├── ic_errors.yaml   # 20 IC error signatures
│   │   └── pspice_reference.txt  # 20 common PSpice errors
│   └── cli.py               # Argument parser
├── tests/
│   ├── netlists/            # Test .cir files (correct + broken)
│   └── test_parser.py       # Pytest suite
└── chroma_db/               # Vector store (built on first --rag run)
```

## Tested IC error patterns

LM741, LM358, LM324, NE5532, TL081, AD844, 2N2222, 2N3904, LM317, LM337, 7805, 7905, LM393, LM317, BS170, 1N4148, and more.

## License

MIT