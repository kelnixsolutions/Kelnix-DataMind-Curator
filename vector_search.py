"""
Semantic vector search using ChromaDB for context retrieval.
Stores ingested data as embeddings for natural language search.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection

    import chromadb

    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_data")
    _client = chromadb.PersistentClient(path=persist_dir)
    _collection = _client.get_or_create_collection(
        name="datamind_vectors",
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def index_records(records: list[dict[str, Any]], source_id: str, table: str | None = None) -> int:
    """Index records into the vector store.

    Args:
        records: List of dicts to index.
        source_id: ID of the data source.
        table: Optional table name for metadata.

    Returns:
        Number of records indexed.
    """
    collection = _get_collection()

    documents: list[str] = []
    ids: list[str] = []
    metadatas: list[dict] = []

    for record in records:
        doc_text = json.dumps(record, default=str)
        doc_id = hashlib.md5(f"{source_id}:{table}:{doc_text}".encode()).hexdigest()

        documents.append(doc_text)
        ids.append(doc_id)
        metadatas.append({
            "source_id": source_id,
            "table": table or "unknown",
        })

    if documents:
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)

    return len(documents)


def search(query: str, source_id: str | None = None, n_results: int = 10) -> list[dict[str, Any]]:
    """Semantic search across indexed data.

    Args:
        query: Natural language search query.
        source_id: Optional filter by source.
        n_results: Max results to return.

    Returns:
        List of {"content": str, "source": str, "score": float, "metadata": dict}
    """
    collection = _get_collection()

    where_filter = None
    if source_id:
        where_filter = {"source_id": source_id}

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
    )

    output: list[dict[str, Any]] = []
    if results and results["documents"]:
        docs = results["documents"][0]
        dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

        for doc, dist, meta in zip(docs, dists, metas):
            output.append({
                "content": doc,
                "source": meta.get("source_id", "unknown"),
                "score": round(1.0 - dist, 4),  # cosine distance → similarity
                "metadata": meta,
            })

    return output


def delete_source_vectors(source_id: str) -> int:
    """Delete all vectors for a source."""
    collection = _get_collection()
    existing = collection.get(where={"source_id": source_id})
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0
