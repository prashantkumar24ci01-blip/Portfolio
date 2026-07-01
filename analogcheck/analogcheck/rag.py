"""
RAG pipeline for AnalogCheck.

Ingests PSpice documentation + common IC error patterns into ChromaDB
for context-aware netlist diagnosis.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

# Paths
_KB_DIR = Path(__file__).parent / "knowledge"
_CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
_COLLECTION_NAME = "analogcheck_rag"

# Embedding model (local, free, CPU)
_MODEL_NAME = "all-MiniLM-L6-v2"

# Lazy-loaded globals
_embedder: Optional[SentenceTransformer] = None
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


# ---------------------------------------------------------------------------
# Embedding function for ChromaDB
# ---------------------------------------------------------------------------
class _EmbeddingFn(chromadb.EmbeddingFunction):
    """ChromaDB embedding function using sentence-transformers."""

    def __init__(self, model_name: str = _MODEL_NAME):
        global _embedder
        if _embedder is None:
            _embedder = SentenceTransformer(model_name)
        self._model = _embedder
        self._name = model_name

    def __call__(self, input: list[str]) -> list[list[float]]:
        emb = self._model.encode(input, show_progress_bar=False)
        return emb.tolist()


# ---------------------------------------------------------------------------
# Initialize / get collection
# ---------------------------------------------------------------------------
def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _client = chromadb.PersistentClient(
        path=str(_CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_EmbeddingFn(),
    )
    return _collection


# ---------------------------------------------------------------------------
# Build / rebuild knowledge base
# ---------------------------------------------------------------------------
def build_knowledge_base(force: bool = False) -> int:
    """Index all knowledge base files into ChromaDB.

    Args:
        force: If True, delete existing collection and rebuild.

    Returns:
        Number of chunks indexed.
    """
    if force:
        global _client, _collection
        try:
            _client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass
        _collection = None

    coll = _get_collection()

    # Check if already populated
    if coll.count() > 0 and not force:
        return coll.count()

    # Collect all text chunks
    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    # --- PSpice doc chunks ---
    pspice_dir = _KB_DIR / "pspice_docs"
    if pspice_dir.is_dir():
        for fpath in sorted(pspice_dir.glob("*.txt")):
            text = fpath.read_text(encoding="utf-8")
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=512,
                chunk_overlap=64,
                separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
            )
            doc_chunks = splitter.split_text(text)
            for i, chunk in enumerate(doc_chunks):
                chunks.append({
                    "id": f"pspice_{fpath.stem}_{i}",
                    "text": chunk,
                    "source": f"pspice_docs/{fpath.name}",
                    "category": "pspice_manual",
                })

    # --- IC errors ---
    ic_path = _KB_DIR / "ic_errors.yaml"
    if ic_path.exists():
        import yaml
        data = yaml.safe_load(ic_path.read_text(encoding="utf-8"))
        if data and isinstance(data, list):
            for ic_idx, entry in enumerate(data):
                text = (
                    f"IC: {entry.get('ic', 'unknown')}\n"
                    f"Error type: {entry.get('error_type', '')}\n"
                    f"Symptom: {entry.get('symptom', '')}\n"
                    f"Root cause: {entry.get('root_cause', '')}\n"
                    f"Fix: {entry.get('fix', '')}\n"
                    f"Example netlist: {entry.get('example', '')}"
                )
                chunks.append({
                    "id": f"ic_{ic_idx}",
                    "text": text,
                    "source": "ic_errors.yaml",
                    "category": "ic_error",
                })

    # --- PSpice reference errors ---
    pspice_ref_path = _KB_DIR / "pspice_reference.txt"
    if pspice_ref_path.exists():
        text = pspice_ref_path.read_text(encoding="utf-8")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=64,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". "],
        )
        ref_chunks = splitter.split_text(text)
        for i, chunk in enumerate(ref_chunks):
            chunks.append({
                "id": f"pspice_ref_{i}",
                "text": chunk,
                "source": "pspice_reference.txt",
                "category": "pspice_reference",
            })

    # Index into ChromaDB
    if chunks:
        coll.add(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"], "category": c["category"]} for c in chunks],
        )

    return len(chunks)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def search(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Search the RAG knowledge base.

    Args:
        query: Natural-language query (error msg, IC name, symptom).
        k: Number of results.

    Returns:
        List of {text, source, category, distance}.
    """
    coll = _get_collection()
    results = coll.query(query_texts=[query], n_results=k)
    entries: list[dict[str, Any]] = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 0.0
            entries.append({
                "text": doc,
                "source": meta.get("source", ""),
                "category": meta.get("category", ""),
                "distance": dist,
            })
    return entries


# ---------------------------------------------------------------------------
# Build RAG context for LLM prompt
# ---------------------------------------------------------------------------
def build_rag_context(
    netlist_text: str,
    sim_error: Optional[str] = None,
    ic_names: Optional[list[str]] = None,
    k: int = 5,
) -> str:
    """Build a RAG context string for inclusion in the LLM prompt.

    Constructs queries from the netlist content, simulation error (if any),
    and detected IC names, then concatenates the top-k results into a
    formatted context block.
    """
    queries: list[str] = []

    # Query from sim error
    if sim_error:
        queries.append(f"SPICE error: {sim_error}")

    # Query from IC names
    if ic_names:
        for ic in ic_names[:3]:
            queries.append(f"{ic} common errors pinout configuration")

    # Query from netlist characteristics
    lines = netlist_text.strip().split("\n")
    for line in lines[:3]:
        st = line.strip()
        if st and not st.startswith("*"):
            queries.append(st)
            break

    # Run queries, deduplicate
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for q in queries:
        for r in search(q, k=k):
            dedup_key = r["text"][:80]
            if dedup_key not in seen:
                seen.add(dedup_key)
                results.append(r)

    # Format context
    if not results:
        return ""

    lines_out = ["--- RAG Knowledge Context ---"]
    for i, r in enumerate(results[:k], 1):
        lines_out.append(f"\n[{i}] Source: {r['source']} (cat: {r['category']})")
        lines_out.append(r["text"][:600])
    lines_out.append("\n--- End RAG Context ---")

    return "\n".join(lines_out)


# ---------------------------------------------------------------------------
# Quick check: is the KB populated?
# ---------------------------------------------------------------------------
def knowledge_base_size() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0


def knowledge_base_available() -> bool:
    try:
        return _get_collection().count() > 0
    except Exception:
        return False
