"""
MCP server for Kelnix DataMind Curator using the official Model Context Protocol SDK.

Exposes all data curation tools via JSON-RPC over stdio (for Claude Desktop,
Cursor, etc.) or StreamableHTTP (for web-based MCP clients).

Usage:
    # stdio mode (Claude Desktop, Cursor, VS Code)
    python mcp_server.py

    # Or via the MCP CLI
    mcp run mcp_server.py
"""
from __future__ import annotations

import json
import os
from typing import Annotated, Any

from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ── Initialize MCP server ──────────────────────────────────────────────

mcp = FastMCP(
    "Kelnix DataMind Curator",
    instructions=(
        "AI-Ready Data & Context Engineering API. Connect any data source — PostgreSQL, "
        "MySQL, CRMs, APIs — and get clean, structured, AI-ready data in seconds. "
        "Natural language queries (NLQ), semantic vector search, automated PII redaction, "
        "deduplication, format standardization, and AI-powered context building for RAG "
        "pipelines. 25 free credits on signup, no credit card required."
    ),
    website_url="https://kelnix.org",
)

# ── Lazy-init backend ──────────────────────────────────────────────────

_initialized = False


def _ensure_init():
    global _initialized
    if not _initialized:
        import db
        db.init_db()
        _initialized = True


# ── MCP Tools: sources.* ──────────────────────────────────────────────

@mcp.tool(
    name="sources.connect",
    annotations=ToolAnnotations(
        title="Connect Data Source",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def connect_source(
    source_type: Annotated[str, Field(
        description="Type of data source to connect. Supported: postgresql, mysql, csv, json_api, mock_crm",
    )],
    name: Annotated[str, Field(
        description="A friendly name for this data source (e.g. 'Production DB', 'Salesforce CRM')",
    )],
    connection_string: Annotated[str | None, Field(
        description="Database connection string (e.g. 'postgresql://user:pass@host:5432/db'). Required for database sources.",
        default=None,
    )] = None,
    config: Annotated[dict | None, Field(
        description="Additional config as key-value pairs (e.g. API URL, headers, file path). Source-type specific.",
        default=None,
    )] = None,
) -> dict[str, Any]:
    """Connect a new data source for querying, fetching, and context building.

    Validates connectivity before saving. Use 'mock_crm' for a built-in demo
    with sample companies, contacts, and deals data.
    Costs 1 credit.
    """
    _ensure_init()
    import tools as _tools

    api_key = os.environ.get("DATAMIND_API_KEY", "")
    result = await _tools.connect_source(
        source_type=source_type,
        name=name,
        connection_string=connection_string,
        config=config,
        api_key=api_key,
    )
    return result


@mcp.tool(
    name="sources.list",
    annotations=ToolAnnotations(
        title="List Data Sources",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def list_sources() -> dict[str, Any]:
    """List all connected data sources with their status and type.

    Returns source_id, name, type, status, and creation date for each source.
    Free — no credits consumed.
    """
    _ensure_init()
    import tools as _tools

    api_key = os.environ.get("DATAMIND_API_KEY", "")
    if not api_key:
        return {"sources": [], "note": "Set DATAMIND_API_KEY to list sources"}
    return await _tools.list_sources(api_key)


@mcp.tool(
    name="sources.test",
    annotations=ToolAnnotations(
        title="Test Data Source",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def test_source(
    source_id: Annotated[str, Field(
        description="The source_id returned by sources.connect. Must be a previously connected source.",
    )],
) -> dict[str, Any]:
    """Test connectivity to a data source and list available tables.

    Returns connection status, database version info, and up to 20 table names.
    Free — no credits consumed.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.test_source(source_id)


# ── MCP Tools: data.* ─────────────────────────────────────────────────

@mcp.tool(
    name="data.query",
    annotations=ToolAnnotations(
        title="Query Data",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def query_data(
    source_id: Annotated[str, Field(
        description="The source_id to query against. Must be a connected data source.",
    )],
    query: Annotated[str, Field(
        description="Natural language question (e.g. 'top 5 customers by revenue') or raw SQL query (e.g. 'SELECT * FROM users LIMIT 10').",
    )],
    mode: Annotated[str, Field(
        description="Query mode. 'auto' detects if the query is natural language or SQL. 'nlq' forces natural language processing. 'sql' sends raw SQL.",
        default="auto",
    )] = "auto",
    limit: Annotated[int, Field(
        description="Maximum number of rows to return. Range: 1-10000.",
        default=100,
        ge=1,
        le=10000,
    )] = 100,
) -> dict[str, Any]:
    """Query data using natural language or SQL.

    In 'auto' mode, the system detects whether your query is plain English or SQL.
    Natural language queries are translated to SQL by Claude Haiku using your schema.
    Returns columns, rows, the executed SQL, and the mode used.
    Costs 2 credits.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.query_data(source_id, query, mode=mode, limit=limit)


@mcp.tool(
    name="data.fetch",
    annotations=ToolAnnotations(
        title="Fetch Data",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def fetch_data(
    source_id: Annotated[str, Field(
        description="The source_id to fetch data from.",
    )],
    table: Annotated[str, Field(
        description="Table or collection name to fetch rows from (e.g. 'users', 'orders').",
    )],
    limit: Annotated[int, Field(
        description="Maximum rows to return. Range: 1-10000.",
        default=100,
        ge=1,
        le=10000,
    )] = 100,
    offset: Annotated[int, Field(
        description="Number of rows to skip for pagination.",
        default=0,
        ge=0,
    )] = 0,
    filters: Annotated[dict | None, Field(
        description="Key-value filters to apply (e.g. {'status': 'active', 'country': 'US'}).",
        default=None,
    )] = None,
) -> dict[str, Any]:
    """Fetch raw rows from a specific table with optional filters and pagination.

    Returns columns, rows, row count, and total available records.
    Costs 1 credit.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.fetch_data(source_id, table, limit=limit, offset=offset, filters=filters)


@mcp.tool(
    name="data.search",
    annotations=ToolAnnotations(
        title="Semantic Search",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def search_data(
    query: Annotated[str, Field(
        description="Natural language search query (e.g. 'companies in the software industry with high revenue').",
    )],
    source_id: Annotated[str | None, Field(
        description="Optional source_id to limit search to a specific data source. Searches all sources if omitted.",
        default=None,
    )] = None,
    n_results: Annotated[int, Field(
        description="Maximum number of search results to return. Range: 1-100.",
        default=10,
        ge=1,
        le=100,
    )] = 10,
) -> dict[str, Any]:
    """Semantic vector search across your indexed data using ChromaDB embeddings.

    Finds records that are semantically similar to your natural language query,
    even if they don't contain the exact keywords. Data must be indexed first
    (happens automatically when you use context.build or data.fetch).
    Costs 2 credits.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.search_data(query, source_id=source_id, n_results=n_results)


# ── MCP Tools: pipeline.* ─────────────────────────────────────────────

@mcp.tool(
    name="pipeline.clean",
    annotations=ToolAnnotations(
        title="Clean & Standardize Data",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def clean_data(
    records: Annotated[list[dict], Field(
        description="Array of records (JSON objects) to clean and standardize.",
    )],
    rules: Annotated[dict[str, str] | None, Field(
        description="Optional field-to-type mapping for standardization. Types: 'date', 'phone', 'email', 'currency', 'text_lower', 'text_upper'. Auto-detected if omitted.",
        default=None,
    )] = None,
) -> dict[str, Any]:
    """Clean and standardize data formats — dates to ISO 8601, phones to digits, emails to lowercase, currencies to floats.

    Auto-detects field types from names and values when rules are not provided.
    Fills nulls with sensible defaults. Returns cleaned data with transformation stats.
    Costs 2 credits.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.clean_data(records, rules=rules)


@mcp.tool(
    name="pipeline.deduplicate",
    annotations=ToolAnnotations(
        title="Deduplicate Records",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def deduplicate_data(
    records: Annotated[list[dict], Field(
        description="Array of records (JSON objects) to deduplicate.",
    )],
    keys: Annotated[list[str] | None, Field(
        description="Field names to use as deduplication key (e.g. ['email'] or ['name', 'company']). If omitted, uses full record hash.",
        default=None,
    )] = None,
) -> dict[str, Any]:
    """Remove duplicate records based on specified key fields or full record hash.

    When keys are provided, two records are considered duplicates if they have
    identical values for all specified key fields. Returns deduplicated data with stats.
    Costs 1 credit.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.deduplicate_data(records, keys=keys)


@mcp.tool(
    name="pipeline.redact_pii",
    annotations=ToolAnnotations(
        title="Redact PII",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def redact_pii(
    records: Annotated[list[dict], Field(
        description="Array of records (JSON objects) to scan for PII.",
    )],
    fields: Annotated[list[str] | None, Field(
        description="Specific field names to redact (e.g. ['email', 'phone', 'name']). Auto-detects PII fields if omitted.",
        default=None,
    )] = None,
    replacement: Annotated[str, Field(
        description="String to replace PII with.",
        default="[REDACTED]",
    )] = "[REDACTED]",
) -> dict[str, Any]:
    """Detect and redact personally identifiable information (PII) from records.

    Auto-detects emails, phone numbers, SSNs, credit cards, IP addresses, names,
    and addresses using field name heuristics and regex patterns. Returns redacted
    data with stats on what was found and removed.
    Costs 1 credit.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.redact_pii_data(records, fields=fields, replacement=replacement)


# ── MCP Tools: context.* ──────────────────────────────────────────────

@mcp.tool(
    name="context.build",
    annotations=ToolAnnotations(
        title="Build AI Context",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def build_context(
    source_ids: Annotated[list[str], Field(
        description="List of source_id values to include in the context. Data from all specified sources will be combined.",
    )],
    query: Annotated[str | None, Field(
        description="Optional natural language query to focus the context on relevant data. If omitted, includes a broad sample.",
        default=None,
    )] = None,
    max_tokens: Annotated[int, Field(
        description="Maximum token budget for the context. Controls how much data is included. Range: 500-32000.",
        default=4000,
        ge=500,
        le=32000,
    )] = 4000,
) -> dict[str, Any]:
    """Build an AI-ready context package from one or more data sources.

    Fetches schemas, sample data, and relevant records from each source, then
    assembles them into structured chunks optimized for LLM consumption.
    Perfect for RAG pipelines. Also indexes data for semantic search.
    Costs 3 credits.
    """
    _ensure_init()
    import tools as _tools

    api_key = os.environ.get("DATAMIND_API_KEY", "")
    return await _tools.build_context(source_ids, query=query, max_tokens=max_tokens, api_key=api_key)


@mcp.tool(
    name="context.summarize",
    annotations=ToolAnnotations(
        title="Summarize Dataset",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def summarize_data(
    source_id: Annotated[str, Field(
        description="The source_id containing the data to summarize.",
    )],
    table: Annotated[str | None, Field(
        description="Specific table to summarize. If omitted, summarizes all tables in the source.",
        default=None,
    )] = None,
    question: Annotated[str | None, Field(
        description="Optional specific question to answer about the data (e.g. 'What are the top revenue drivers?').",
        default=None,
    )] = None,
) -> dict[str, Any]:
    """Generate an AI-powered summary of a dataset with key insights.

    Uses Claude Haiku to analyze the data and produce a narrative summary,
    key insights as bullet points, and data quality observations.
    Costs 2 credits.
    """
    _ensure_init()
    import tools as _tools
    return await _tools.summarize_data(source_id, table=table, question=question)


# ── MCP Tools: credits.* ──────────────────────────────────────────────

@mcp.tool(
    name="credits.check_balance",
    annotations=ToolAnnotations(
        title="Check Balance",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def check_balance(
    include_history: Annotated[bool, Field(
        description="Set to true to include recent transaction history (last 10 credit changes) in the response.",
        default=False,
    )] = False,
) -> dict[str, Any]:
    """Check your current credit balance and subscription plan.

    Returns remaining credits and active plan (free, basic, or pro).
    Call this before expensive operations to verify you have enough credits.
    Free — no credits consumed.
    """
    _ensure_init()
    import db

    api_key = os.environ.get("DATAMIND_API_KEY", "")
    if not api_key:
        return {"credits": "unlimited (local mode)", "plan": "local"}

    import tools as _tools
    return await _tools.check_balance(api_key, include_history=include_history)


# ── Prompts (MCP protocol) ─────────────────────────────────────────────

@mcp.prompt()
def explore_data(
    source_type: Annotated[str, Field(
        description="Type of data source to explore (e.g. 'mock_crm', 'postgresql')",
    )] = "mock_crm",
    question: Annotated[str, Field(
        description="What you want to learn about the data",
    )] = "Give me an overview of all the data",
) -> str:
    """Step-by-step guide to connect a data source and explore its contents."""
    return (
        f"I want to explore data from a {source_type} source.\n\n"
        f"Question: {question}\n\n"
        f"Please:\n"
        f"1. Connect the data source using sources.connect (type: {source_type})\n"
        f"2. Test the connection with sources.test\n"
        f"3. Query the data using data.query with my question\n"
        f"4. Summarize the findings with context.summarize\n"
        f"5. Present the results clearly"
    )


@mcp.prompt()
def clean_and_prepare(
    source_id: Annotated[str, Field(
        description="Source ID to clean data from",
    )],
    table: Annotated[str, Field(
        description="Table name to clean",
    )],
) -> str:
    """Clean, deduplicate, and redact PII from a dataset."""
    return (
        f"I need to clean and prepare data from source {source_id}, table {table}.\n\n"
        f"Please:\n"
        f"1. Fetch the raw data using data.fetch\n"
        f"2. Clean and standardize formats with pipeline.clean\n"
        f"3. Remove duplicates with pipeline.deduplicate\n"
        f"4. Redact any PII with pipeline.redact_pii\n"
        f"5. Show me a before/after summary of the transformations"
    )


@mcp.prompt()
def build_rag_context(
    source_ids: Annotated[str, Field(
        description="Comma-separated source IDs to include",
    )],
    topic: Annotated[str, Field(
        description="Topic or question to focus the context on",
    )] = "general overview",
) -> str:
    """Build an AI-ready context package for RAG from multiple data sources."""
    return (
        f"I need to build an AI-ready context package.\n\n"
        f"Sources: {source_ids}\n"
        f"Focus: {topic}\n\n"
        f"Please:\n"
        f"1. Use context.build with the specified sources\n"
        f"2. Review the chunks and token estimate\n"
        f"3. If the data needs cleaning, run it through pipeline.clean first\n"
        f"4. Present the final context summary with sources used and token count"
    )


# ── Resources (MCP protocol) ──────────────────────────────────────────

@mcp.resource("datamind://pricing")
def get_pricing() -> str:
    """Current pricing for DataMind Curator credits."""
    return json.dumps({
        "credit_packs": {
            "100": "$8.00 ($0.080/credit)",
            "500": "$30.00 ($0.060/credit)",
            "1000": "$50.00 ($0.050/credit)",
            "5000": "$200.00 ($0.040/credit)",
            "10000": "$400.00 ($0.040/credit)",
        },
        "subscriptions": {
            "free": "25 credits on signup, $0/mo",
            "basic": "200 credits/mo, $15/mo",
            "pro": "2000 credits/mo, $99/mo",
        },
        "tool_costs": {
            "sources.connect": "1 credit",
            "sources.list": "free",
            "sources.test": "free",
            "data.query": "2 credits",
            "data.fetch": "1 credit",
            "data.search": "2 credits",
            "pipeline.clean": "2 credits",
            "pipeline.deduplicate": "1 credit",
            "pipeline.redact_pii": "1 credit",
            "context.build": "3 credits",
            "context.summarize": "2 credits",
            "credits.check_balance": "free",
        },
    }, indent=2)


@mcp.resource("datamind://supported-sources")
def get_supported_sources() -> str:
    """Supported data source types and their configuration."""
    return json.dumps({
        "source_types": {
            "postgresql": {
                "description": "PostgreSQL database",
                "requires": "connection_string",
                "example": "postgresql://user:pass@host:5432/mydb",
            },
            "mysql": {
                "description": "MySQL database",
                "requires": "connection_string",
                "example": "mysql://user:pass@host:3306/mydb",
            },
            "mock_crm": {
                "description": "Built-in demo CRM with sample companies, contacts, and deals",
                "requires": "nothing (built-in data)",
                "example": "sources.connect(source_type='mock_crm', name='Demo CRM')",
            },
            "csv": {
                "description": "CSV file (coming soon)",
                "requires": "config.url or config.file_path",
            },
            "json_api": {
                "description": "JSON REST API (coming soon)",
                "requires": "config.url, config.headers",
            },
        },
    }, indent=2)


# ── Run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
