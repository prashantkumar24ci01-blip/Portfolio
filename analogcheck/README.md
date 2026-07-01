# AnalogCheck — RAG-Enhanced SPICE Netlist Debugger

**Technologies:** Python, ChromaDB, sentence-transformers, LLM (OpenRouter), ngspice, pytest
**Timeline:** May-June 2026
**Source:** `Z:\hermes\analogcheck\`

## What it does

CLI tool that catches semantic errors in SPICE netlists — bugs that simulators pass silently but produce wrong physical results (port-label swaps, missing ground, M vs MEG confusion).

Three-tier detection:
1. **Deterministic parse-time checks** — floating nodes, no ground, duplicate names, M vs MEG
2. **ngspice subprocess + .raw reader** — simulation-level anomaly detection
3. **LLM reasoning with RAG** — retrieves relevant IC error patterns + PSpice docs from ChromaDB

## Architecture

```
netlist.cir → token-split parser → Device/Subckt/Netlist data structures
           → deterministic checks (floating node, ground, M vs MEG, etc.)
           → ngspice subprocess → .raw reader
           → RAG query (ChromaDB: 35 chunks of IC errors + PSpice refs)
           → LLM diagnosis with RAG context
           → JSON / Markdown report
```

## Key files in this repo

| File | Purpose |
|------|---------|
| `analogcheck/checker.py` | Pipeline orchestrator + 5 health checks |
| `analogcheck/rag.py` | ChromaDB + sentence-transformers RAG pipeline |
| `analogcheck/parser.py` | Token-split SPICE netlist parser |
| `analogcheck/knowledge/ic_errors.yaml` | 20 IC error patterns (LM741, LM358, etc.) |
| `analogcheck/knowledge/pspice_reference.txt` | 20 common PSpice errors with fixes |
| `tests/netlists/` | Test netlists: correct, broken, missing_ground, bad_multiplier |
| `chroma_db/` | Persistent vector store (35 chunks) |

## Design decisions

| Decision | Why |
|----------|-----|
| Token-split parser, not regex | Regex backtracking fails on X devices with complex params |
| Subprocess ngspice, not PySpice | PySpice DLLs fragile on Windows |
| sentence-transformers (local) | Zero API cost, ~35ms retrieval, runs on CPU |
| ChromaDB (local) | Zero infra, persists to disk, no cloud |
| RAG context → LLM prompt | Grounds diagnosis in verified docs, not model guesswork |

## Running

```bash
pip install -e .
# Deterministic only
python -m analogcheck tests/netlists/cfoa_inverting_amp.cir --no-sim --format md

# With LLM
export ANALOGCHECK_LLM_ENDPOINT="https://openrouter.ai/api/v1/chat/completions"
export ANALOGCHECK_LLM_API_KEY="sk-..."
export ANALOGCHECK_LLM_MODEL="deepseek/deepseek-v4-flash"
python -m analogcheck netlist.cir --llm on --rag
```

## Resume bullet

> *"Built RAG-enhanced SPICE netlist debugger indexing 20+ common IC error patterns (LM741, LM358, LM317 pinout mismatches) and PSpice convergence documentation into ChromaDB with sentence-transformer embeddings. RAG context retrieved at check-time grounds LLM diagnosis in verified reference material. 35 chunks indexed, ~35ms retrieval latency."*
