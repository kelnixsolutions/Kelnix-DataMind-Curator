"""
Natural Language to SQL engine powered by Claude Haiku.
Translates user questions into SQL queries based on the connected source schema.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

_client: anthropic.AsyncAnthropic | None = None

NLQ_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are a SQL query generator. Given a database schema and a natural language question,
generate a valid SQL query that answers the question.

Rules:
1. Return ONLY the SQL query, no explanation or markdown.
2. Use standard SQL syntax (PostgreSQL-compatible).
3. Always include a LIMIT clause (default 100 unless the user specifies otherwise).
4. Never use DROP, DELETE, UPDATE, INSERT, ALTER, or any DDL/DML statements.
5. Only use SELECT statements.
6. Use table and column names exactly as provided in the schema.
7. For aggregations, always include meaningful aliases.
"""


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def natural_language_to_sql(
    question: str,
    tables_schema: dict[str, list[dict[str, str]]],
    sample_data: dict[str, list[list]] | None = None,
) -> str:
    """Convert a natural language question to SQL.

    Args:
        question: The user's natural language question.
        tables_schema: {"table_name": [{"name": "col", "type": "text"}, ...]}
        sample_data: Optional sample rows per table for context.

    Returns:
        SQL query string.
    """
    schema_text = _format_schema(tables_schema)

    prompt = f"Database schema:\n{schema_text}\n"
    if sample_data:
        prompt += "\nSample data:\n"
        for table, rows in sample_data.items():
            prompt += f"\n{table} (first 3 rows): {json.dumps(rows[:3], default=str)}\n"

    prompt += f"\nQuestion: {question}\n\nGenerate the SQL query:"

    client = _get_client()
    response = await client.messages.create(
        model=NLQ_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    sql = response.content[0].text.strip()

    # Strip markdown code blocks if present
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Safety check
    _validate_sql(sql)

    return sql


def is_natural_language(query: str) -> bool:
    """Detect whether a query is natural language or SQL."""
    sql_keywords = {"select", "insert", "update", "delete", "create", "drop", "alter", "with"}
    first_word = query.strip().split()[0].lower() if query.strip() else ""
    return first_word not in sql_keywords


def _format_schema(tables_schema: dict[str, list[dict[str, str]]]) -> str:
    lines: list[str] = []
    for table, columns in tables_schema.items():
        cols = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
        lines.append(f"  {table}: {cols}")
    return "\n".join(lines)


def _validate_sql(sql: str) -> None:
    """Basic safety validation — reject DDL/DML statements."""
    upper = sql.upper().strip()
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]
    first_word = upper.split()[0] if upper else ""
    if first_word in forbidden:
        raise ValueError(f"Forbidden SQL statement: {first_word}. Only SELECT queries are allowed.")
