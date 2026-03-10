from __future__ import annotations

import json
import os
import uuid
from typing import Any

import anthropic

import db
import redis_cache
import vector_search
from connectors import get_connector
from connectors.base import BaseConnector
from nlq_engine import is_natural_language, natural_language_to_sql
from pipeline.dedup import deduplicate
from pipeline.formatter import standardize
from pipeline.pii_redactor import redact_pii

# ── Active connector pool ────────────────────────────────────────────────

_connectors: dict[str, BaseConnector] = {}

AI_MODEL = "claude-haiku-4-5-20251001"
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def _get_connector(source_id: str) -> BaseConnector:
    """Get or create a connector for a source."""
    if source_id in _connectors:
        return _connectors[source_id]

    source = db.get_source(source_id)
    if source is None:
        raise ValueError(f"Source '{source_id}' not found")

    connector = get_connector(
        source["source_type"],
        connection_string=source.get("connection_string"),
        **(source.get("config") or {}),
    )
    await connector.connect()
    _connectors[source_id] = connector
    return connector


# ── sources.connect ─────────────────────────────────────────────────────

async def connect_source(
    source_type: str,
    name: str,
    connection_string: str | None = None,
    config: dict | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    source_id = uuid.uuid4().hex[:16]

    # Validate by connecting
    connector = get_connector(
        source_type,
        connection_string=connection_string,
        **(config or {}),
    )
    await connector.connect()
    test_result = await connector.test_connection()

    if not test_result["connected"]:
        await connector.disconnect()
        raise ValueError(f"Failed to connect: {test_result['message']}")

    _connectors[source_id] = connector

    db.insert_source(
        source_id=source_id,
        api_key=api_key or "",
        source_type=source_type,
        name=name,
        connection_string=connection_string,
        config=config,
    )

    return {
        "source_id": source_id,
        "source_type": source_type,
        "name": name,
        "status": "connected",
    }


# ── sources.list ────────────────────────────────────────────────────────

async def list_sources(api_key: str) -> dict[str, Any]:
    sources = db.list_sources(api_key)
    return {"sources": sources}


# ── sources.test ────────────────────────────────────────────────────────

async def test_source(source_id: str) -> dict[str, Any]:
    connector = await _get_connector(source_id)
    result = await connector.test_connection()
    return {
        "source_id": source_id,
        "connected": result["connected"],
        "message": result["message"],
        "sample_tables": result.get("sample_tables"),
    }


# ── data.query ──────────────────────────────────────────────────────────

async def query_data(
    source_id: str,
    query: str,
    mode: str = "auto",
    limit: int = 100,
) -> dict[str, Any]:
    connector = await _get_connector(source_id)

    # Check cache
    cache_k = redis_cache.cache_key("query", source_id, query, str(limit))
    cached = redis_cache.get(cache_k)
    if cached:
        cached["from_cache"] = True
        return cached

    # Determine if NLQ or SQL
    if mode == "auto":
        use_nlq = is_natural_language(query)
    elif mode == "nlq":
        use_nlq = True
    else:
        use_nlq = False

    if use_nlq:
        tables = await connector.list_tables()
        schemas = {}
        for t in tables[:10]:
            schemas[t] = await connector.get_schema(t)

        sql = await natural_language_to_sql(query, schemas)
        mode_used = "nlq"
    else:
        sql = query
        mode_used = "sql"

    # Add LIMIT if not present
    if "limit" not in sql.lower():
        sql = sql.rstrip(";") + f" LIMIT {limit}"

    result = await connector.execute_query(sql)

    response = {
        "source_id": source_id,
        "sql_executed": sql,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "mode_used": mode_used,
    }

    redis_cache.set(cache_k, response, ttl=120)
    return response


# ── data.fetch ──────────────────────────────────────────────────────────

async def fetch_data(
    source_id: str,
    table: str,
    limit: int = 100,
    offset: int = 0,
    filters: dict | None = None,
) -> dict[str, Any]:
    connector = await _get_connector(source_id)
    result = await connector.fetch_rows(table, limit=limit, offset=offset, filters=filters)

    return {
        "source_id": source_id,
        "table": table,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "total_available": result.get("total_available"),
    }


# ── data.search ─────────────────────────────────────────────────────────

async def search_data(
    query: str,
    source_id: str | None = None,
    n_results: int = 10,
) -> dict[str, Any]:
    results = vector_search.search(query, source_id=source_id, n_results=n_results)
    return {
        "query": query,
        "results": results,
        "total_results": len(results),
    }


# ── pipeline.clean ──────────────────────────────────────────────────────

async def clean_data(
    records: list[dict],
    rules: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = standardize(records, rules=rules)
    return result


# ── pipeline.deduplicate ────────────────────────────────────────────────

async def deduplicate_data(
    records: list[dict],
    keys: list[str] | None = None,
) -> dict[str, Any]:
    result = deduplicate(records, keys=keys)
    return result


# ── pipeline.redact_pii ─────────────────────────────────────────────────

async def redact_pii_data(
    records: list[dict],
    fields: list[str] | None = None,
    replacement: str = "[REDACTED]",
) -> dict[str, Any]:
    result = redact_pii(records, fields_to_redact=fields, replacement=replacement)
    return result


# ── context.build ───────────────────────────────────────────────────────

async def build_context(
    source_ids: list[str],
    query: str | None = None,
    max_tokens: int = 4000,
    api_key: str | None = None,
) -> dict[str, Any]:
    context_id = uuid.uuid4().hex[:16]
    chunks: list[dict] = []
    sources_used: list[str] = []

    for sid in source_ids:
        connector = await _get_connector(sid)
        source = db.get_source(sid)
        source_name = source["name"] if source else sid
        tables = await connector.list_tables()
        sources_used.append(source_name)

        for table in tables[:5]:
            result = await connector.fetch_rows(table, limit=20)
            if result["rows"]:
                schema = await connector.get_schema(table)
                schema_text = ", ".join(f"{c['name']} ({c['type']})" for c in schema)

                # Build a readable chunk
                content = f"Table: {table}\nSchema: {schema_text}\n"
                content += f"Columns: {', '.join(result['columns'])}\n"
                for row in result["rows"][:10]:
                    content += json.dumps(dict(zip(result["columns"], row)), default=str) + "\n"

                chunks.append({
                    "content": content,
                    "source": source_name,
                    "relevance_score": 1.0,
                    "metadata": {"table": table, "source_id": sid},
                })

    # If a query is provided, rank chunks by relevance using vector search
    if query and chunks:
        # Index temporarily for search
        for chunk in chunks:
            vector_search.index_records(
                [json.loads(line) for line in chunk["content"].split("\n") if line.startswith("{")],
                source_id=chunk["metadata"]["source_id"],
                table=chunk["metadata"]["table"],
            )

    # Estimate tokens (~4 chars per token)
    total_chars = sum(len(c["content"]) for c in chunks)
    token_estimate = total_chars // 4

    # Trim if over max_tokens
    if token_estimate > max_tokens:
        trimmed: list[dict] = []
        running = 0
        for chunk in chunks:
            chunk_tokens = len(chunk["content"]) // 4
            if running + chunk_tokens > max_tokens:
                remaining = max_tokens - running
                chunk["content"] = chunk["content"][:remaining * 4]
                trimmed.append(chunk)
                break
            trimmed.append(chunk)
            running += chunk_tokens
        chunks = trimmed
        token_estimate = max_tokens

    # Store context
    if api_key:
        db.insert_context(context_id, api_key, json.dumps(chunks, default=str), token_estimate)

    return {
        "context_id": context_id,
        "chunks": chunks,
        "total_tokens_estimate": token_estimate,
        "sources_used": sources_used,
    }


# ── context.summarize ──────────────────────────────────────────────────

async def summarize_data(
    source_id: str,
    table: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    connector = await _get_connector(source_id)
    source = db.get_source(source_id)
    source_name = source["name"] if source else source_id

    tables = [table] if table else await connector.list_tables()
    all_data: list[str] = []
    total_records = 0

    for t in tables[:5]:
        result = await connector.fetch_rows(t, limit=50)
        total_records += result["row_count"]
        if result["rows"]:
            schema = await connector.get_schema(t)
            schema_text = ", ".join(f"{c['name']} ({c['type']})" for c in schema)
            data_text = f"\nTable: {t} ({schema_text})\n"
            for row in result["rows"]:
                data_text += json.dumps(dict(zip(result["columns"], row)), default=str) + "\n"
            all_data.append(data_text)

    prompt = "Analyze the following dataset and provide:\n"
    prompt += "1. A clear summary of what this data contains\n"
    prompt += "2. Key insights and patterns\n"
    prompt += "3. Data quality observations\n"
    if question:
        prompt += f"4. Specifically answer: {question}\n"
    prompt += "\nData:\n" + "\n".join(all_data)
    prompt += "\n\nRespond with JSON: {\"summary\": \"...\", \"key_insights\": [\"...\"], \"record_count\": N}"

    client = _get_client()
    try:
        response = await client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        raise RuntimeError("AI service authentication failed. Please contact support.")
    except anthropic.RateLimitError:
        raise RuntimeError("AI service is temporarily overloaded. Please try again in a few moments.")
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"AI service unavailable (status {e.status_code}). Please try again later.")
    except anthropic.APIConnectionError:
        raise RuntimeError("Could not connect to AI service. Please try again later.")

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(raw)
    return {
        "summary": parsed.get("summary", ""),
        "key_insights": parsed.get("key_insights", []),
        "record_count": total_records,
        "sources_used": [source_name],
    }


# ── credits.check_balance ──────────────────────────────────────────────

async def check_balance(api_key: str, include_history: bool = False) -> dict[str, Any]:
    agent = db.get_agent_by_api_key(api_key)
    plan = agent["plan"] if agent else "free"
    balance = db.get_credit_balance(api_key)
    result: dict[str, Any] = {"credits": balance, "plan": plan}
    if include_history:
        result["history"] = db.get_credit_history(api_key)[:10]
    return result
