from __future__ import annotations

import enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Data source models ─────────────────────────────────────────────────

class SourceType(str, enum.Enum):
    postgresql = "postgresql"
    mysql = "mysql"
    csv = "csv"
    json_api = "json_api"
    mock_crm = "mock_crm"


class ConnectSourceRequest(BaseModel):
    source_type: str = Field(..., description="Type of data source: postgresql, mysql, csv, json_api, mock_crm")
    name: str = Field(..., description="Friendly name for this source")
    connection_string: Optional[str] = Field(None, description="Connection string (for databases)")
    config: Optional[dict] = Field(None, description="Additional config (url, headers, etc.)")


class ConnectSourceResponse(BaseModel):
    source_id: str
    source_type: str
    name: str
    status: str


class TestSourceResponse(BaseModel):
    source_id: str
    connected: bool
    message: str
    sample_tables: Optional[list[str]] = None


class ListSourcesResponse(BaseModel):
    sources: list[dict]


# ── Query models ───────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    source_id: str = Field(..., description="Source to query")
    query: str = Field(..., description="Natural language question or SQL query")
    mode: str = Field("auto", description="Query mode: 'nlq' (natural language), 'sql' (raw SQL), or 'auto' (detect)")
    limit: int = Field(100, ge=1, le=10000, description="Max rows to return")


class QueryResponse(BaseModel):
    source_id: str
    sql_executed: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    mode_used: str


class FetchRequest(BaseModel):
    source_id: str = Field(..., description="Source to fetch from")
    table: str = Field(..., description="Table or collection name")
    limit: int = Field(100, ge=1, le=10000, description="Max rows")
    offset: int = Field(0, ge=0, description="Offset for pagination")
    filters: Optional[dict] = Field(None, description="Key-value filters")


class FetchResponse(BaseModel):
    source_id: str
    table: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    total_available: Optional[int] = None


# ── Pipeline request models ────────────────────────────────────────────

class CleanRequest(BaseModel):
    records: list[dict] = Field(..., description="Records to clean/standardize")
    rules: Optional[dict[str, str]] = Field(None, description="Field-level formatting rules")


class DedupRequest(BaseModel):
    records: list[dict] = Field(..., description="Records to deduplicate")
    keys: Optional[list[str]] = Field(None, description="Fields to use as dedup keys")


class RedactRequest(BaseModel):
    records: list[dict] = Field(..., description="Records containing PII to redact")
    fields: Optional[list[str]] = Field(None, description="Specific fields to redact")
    replacement: str = Field("[REDACTED]", description="Replacement string for PII values")


# ── Pipeline response models ──────────────────────────────────────────

class CleanResult(BaseModel):
    records_in: int
    records_out: int
    nulls_filled: int
    formats_standardized: int
    cleaned_data: list[dict]


class DedupResult(BaseModel):
    records_in: int
    records_out: int
    duplicates_removed: int
    deduplicated_data: list[dict]


class RedactResult(BaseModel):
    records_in: int
    fields_redacted: int
    pii_types_found: list[str]
    redacted_data: list[dict]


# ── Context request models ─────────────────────────────────────────────

class BuildContextRequest(BaseModel):
    source_ids: list[str] = Field(..., description="Source IDs to build context from")
    query: Optional[str] = Field(None, description="Optional query to rank context relevance")
    max_tokens: int = Field(4000, ge=100, le=100000, description="Maximum tokens for context")


class SummarizeRequest(BaseModel):
    source_id: str = Field(..., description="Source to summarize")
    table: Optional[str] = Field(None, description="Specific table to summarize")
    question: Optional[str] = Field(None, description="Specific question to answer about the data")


# ── Context response models ───────────────────────────────────────────

class ContextChunk(BaseModel):
    content: str
    source: str
    relevance_score: Optional[float] = None
    metadata: Optional[dict] = None


class BuildContextResponse(BaseModel):
    context_id: str
    chunks: list[ContextChunk]
    total_tokens_estimate: int
    sources_used: list[str]


class SummarizeResponse(BaseModel):
    summary: str
    key_insights: list[str]
    record_count: int
    sources_used: list[str]


# ── Search request models ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., description="Semantic search query")
    source_id: Optional[str] = Field(None, description="Limit search to a specific source")
    n_results: int = Field(10, ge=1, le=100, description="Number of results to return")


# ── Search response models ─────────────────────────────────────────────

class SearchResult(BaseModel):
    content: str
    source: str
    score: float
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_results: int


# ── Agent registration ─────────────────────────────────────────────────

class RegisterAgentRequest(BaseModel):
    agent_name: str = Field(..., description="Name for this agent")
    org_id: Optional[str] = Field(None, description="Organisation identifier")


class RegisterAgentResponse(BaseModel):
    api_key: str
    agent_name: str
    org_id: Optional[str]
    stripe_customer_id: Optional[str]
    free_credits: int
    message: str = (
        "IMPORTANT: Store this API key securely — it is your permanent identity "
        "and cannot be recovered if lost. Include it as the X-API-Key header in "
        "all future requests. Your credits and data sources are tied to this key."
    )


# ── Billing ────────────────────────────────────────────────────────────

class BuyCreditsRequest(BaseModel):
    credits: int = Field(
        ...,
        description="Number of credits to purchase. Valid packs: 100, 500, 1000, 5000, 10000",
    )


class BuyCreditsResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscribeRequest(BaseModel):
    plan: str = Field(
        ..., description="Subscription plan: 'basic' (200 credits/mo, $15) or 'pro' (2000 credits/mo, $99)"
    )


class SubscribeResponse(BaseModel):
    checkout_url: str
    session_id: str


class CreditHistoryEntry(BaseModel):
    delta: int
    reason: str
    created_at: str


class BalanceResponse(BaseModel):
    credits: int
    plan: str
    history: list[CreditHistoryEntry]


class CheckBalanceResponse(BaseModel):
    credits: int
    plan: str


class BuyCreditsCryptoRequest(BaseModel):
    credits: Optional[int] = Field(None, description="Credits to buy (uses pack pricing). Provide this OR fiat_usd.")
    fiat_usd: Optional[float] = Field(None, description="Exact USD amount. Provide this OR credits.")
    preferred_coin: Optional[str] = Field("btc", description="Crypto to pay with (btc, eth, sol, usdc, etc.)")


class BuyCreditsCryptoResponse(BaseModel):
    payment_id: str
    quoted_crypto_amount: float
    currency: str
    address: str
    expiry: str
    fiat_locked: float
    rate_used: float
    credits: int


class CheckPaymentStatusRequest(BaseModel):
    payment_id: str


class CheckPaymentStatusResponse(BaseModel):
    payment_id: str
    status: str
    pay_amount: float
    actually_paid: float
    pay_currency: str
    fiat_locked: float
    credits: int
