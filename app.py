from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
)
from fastapi.responses import FileResponse, JSONResponse

import billing
import db
import tools
from models import (
    BalanceResponse,
    BuildContextRequest,
    BuildContextResponse,
    BuyCreditsCryptoRequest,
    BuyCreditsCryptoResponse,
    BuyCreditsRequest,
    BuyCreditsResponse,
    CheckBalanceResponse,
    CheckPaymentStatusRequest,
    CheckPaymentStatusResponse,
    CleanRequest,
    CleanResult,
    ConnectSourceRequest,
    ConnectSourceResponse,
    CreditHistoryEntry,
    DedupRequest,
    DedupResult,
    FetchRequest,
    FetchResponse,
    ListSourcesResponse,
    QueryRequest,
    QueryResponse,
    RedactRequest,
    RedactResult,
    RegisterAgentRequest,
    RegisterAgentResponse,
    SearchRequest,
    SearchResponse,
    SubscribeRequest,
    SubscribeResponse,
    SummarizeRequest,
    SummarizeResponse,
    TestSourceResponse,
)
from webhooks import check_low_balance

# ── Legacy env-var API keys ─────────────────────────────────────────────

_LEGACY_KEYS: set[str] = set()


def _load_legacy_keys() -> None:
    raw = os.environ.get("API_KEYS", "")
    if raw:
        _LEGACY_KEYS.update(k.strip() for k in raw.split(",") if k.strip())


# ── Auth dependency ─────────────────────────────────────────────────────

async def verify_api_key(x_api_key: Annotated[str, Header()]) -> str:
    if x_api_key in _LEGACY_KEYS:
        return x_api_key
    if db.api_key_exists(x_api_key):
        return x_api_key
    raise HTTPException(status_code=401, detail="Invalid API key")


Auth = Depends(verify_api_key)


async def require_credits(x_api_key: Annotated[str, Header()], cost: int = 1) -> str:
    key = await verify_api_key(x_api_key)
    try:
        billing.check_and_deduct(key, cost=cost)
    except ValueError as e:
        raise HTTPException(
            status_code=402,
            detail={
                "error": str(e),
                "buy_credits_url": "/billing/buy_credits",
                "buy_credits_crypto_url": "/billing/buy_credits_crypto",
                "subscribe_url": "/billing/subscribe",
                "pricing_url": "/pricing",
                "cheapest_option": {"credits": 100, "price_usd": 8.00},
            },
        )
    await check_low_balance(key)
    return key


def credit_cost(cost: int):
    async def _dep(x_api_key: Annotated[str, Header()]) -> str:
        return await require_credits(x_api_key, cost=cost)
    return Depends(_dep)


CreditAuth = credit_cost(1)
CreditAuth2 = credit_cost(2)
CreditAuth3 = credit_cost(3)


async def refund_credits(api_key: str, cost: int) -> None:
    """Refund credits on failed operations."""
    db.add_credits(api_key, cost, reason="refund_failed_operation")


# ── MCP integration ────────────────────────────────────────────────────

from mcp_server import mcp as _mcp_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

_mcp_session_manager = StreamableHTTPSessionManager(
    app=_mcp_server._mcp_server,
    stateless=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_legacy_keys()
    db.init_db()
    async with _mcp_session_manager.run():
        yield


# ── FastAPI app ─────────────────────────────────────────────────────────

VERSION = "1.0.0"

app = FastAPI(
    title="Kelnix DataMind Curator API",
    version=VERSION,
    description=(
        "AI-Ready Data & Context Engineering API. Connect any data source, "
        "clean and standardize data, query with natural language, build AI-ready "
        "context packages, and protect privacy with automated PII redaction. "
        "25 free credits on signup."
    ),
    lifespan=lifespan,
)


# ── Mount MCP endpoint ─────────────────────────────────────────────────

mcp_starlette = Starlette(
    routes=[Mount("/", app=_mcp_session_manager.handle_request)],
)
app.mount("/stream/mcp", mcp_starlette)


# ── Static assets ──────────────────────────────────────────────────────

ICON_PATH = os.path.join(os.path.dirname(__file__), "Kelnix Datamind Curator.png")


@app.get("/icon.png", include_in_schema=False)
async def get_icon():
    return FileResponse(ICON_PATH, media_type="image/png")


# ── Public info ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Kelnix DataMind Curator API",
        "version": VERSION,
        "docs": "/docs",
        "mcp_endpoint": "/stream/mcp/",
        "icon": "/icon.png",
        "website": "https://kelnix.org",
        "description": (
            "AI-Ready Data & Context Engineering API. Connect any data source, "
            "query with natural language, clean data, build AI context, redact PII."
        ),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}


@app.get("/pricing")
async def pricing():
    return {
        "free_credits_on_signup": 25,
        "credit_packs": {
            "100": {"price_usd": 8.00, "per_credit": 0.080},
            "500": {"price_usd": 30.00, "per_credit": 0.060},
            "1000": {"price_usd": 50.00, "per_credit": 0.050},
            "5000": {"price_usd": 200.00, "per_credit": 0.040},
            "10000": {"price_usd": 400.00, "per_credit": 0.040},
        },
        "subscriptions": {
            "basic": {"credits_per_month": 200, "price_usd_per_month": 15.00},
            "pro": {"credits_per_month": 2000, "price_usd_per_month": 99.00},
        },
        "tool_costs": {
            "sources.connect": 1,
            "sources.list": 0,
            "sources.test": 0,
            "data.query": 2,
            "data.fetch": 1,
            "data.search": 2,
            "pipeline.clean": 2,
            "pipeline.deduplicate": 1,
            "pipeline.redact_pii": 1,
            "context.build": 3,
            "context.summarize": 2,
            "credits.check_balance": 0,
        },
        "payment_methods": ["Stripe (cards)", "Crypto (300+ coins via NOWPayments)"],
    }


@app.get(
    "/server-card",
    summary="MCP server card",
    description="Returns metadata for MCP registry discovery.",
)
async def server_card():
    return {
        "name": "Kelnix DataMind Curator",
        "version": VERSION,
        "description": (
            "AI-Ready Data & Context Engineering API. Connect any data source, "
            "query with natural language, clean data, build AI context, redact PII. "
            "25 free credits on signup."
        ),
        "icon_url": "https://datamind-api.kelnix.org/icon.png",
        "homepage_url": "https://kelnix.org",
        "mcp_endpoint": "https://datamind-api.kelnix.org/stream/mcp/",
        "tools": [
            {"name": "sources.connect", "cost": "1 credit"},
            {"name": "sources.list", "cost": "free"},
            {"name": "sources.test", "cost": "free"},
            {"name": "data.query", "cost": "2 credits"},
            {"name": "data.fetch", "cost": "1 credit"},
            {"name": "data.search", "cost": "2 credits"},
            {"name": "pipeline.clean", "cost": "2 credits"},
            {"name": "pipeline.deduplicate", "cost": "1 credit"},
            {"name": "pipeline.redact_pii", "cost": "1 credit"},
            {"name": "context.build", "cost": "3 credits"},
            {"name": "context.summarize", "cost": "2 credits"},
            {"name": "credits.check_balance", "cost": "free"},
        ],
        "pricing_url": "https://datamind-api.kelnix.org/pricing",
        "docs_url": "https://datamind-api.kelnix.org/docs",
    }


# ── Agent registration ─────────────────────────────────────────────────

@app.post("/register", response_model=RegisterAgentResponse)
async def register_agent(req: RegisterAgentRequest):
    result = db.create_agent(req.agent_name, req.org_id)
    return result


# ── Source management endpoints ─────────────────────────────────────────

@app.post("/sources/connect", response_model=ConnectSourceResponse)
async def api_connect_source(req: ConnectSourceRequest, api_key: str = CreditAuth):
    try:
        return await tools.connect_source(
            source_type=req.source_type,
            name=req.name,
            connection_string=req.connection_string,
            config=req.config,
            api_key=api_key,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 1)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sources", response_model=ListSourcesResponse)
async def api_list_sources(api_key: str = Auth):
    return await tools.list_sources(api_key)


@app.get("/sources/{source_id}/test", response_model=TestSourceResponse)
async def api_test_source(source_id: str, api_key: str = Auth):
    return await tools.test_source(source_id)


# ── Data endpoints ─────────────────────────────────────────────────────

@app.post("/data/query", response_model=QueryResponse)
async def api_query_data(req: QueryRequest, api_key: str = CreditAuth2):
    try:
        return await tools.query_data(
            source_id=req.source_id,
            query=req.query,
            mode=req.mode,
            limit=req.limit,
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        await refund_credits(api_key, 2)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        await refund_credits(api_key, 2)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/data/fetch", response_model=FetchResponse)
async def api_fetch_data(req: FetchRequest, api_key: str = CreditAuth):
    try:
        return await tools.fetch_data(
            source_id=req.source_id,
            table=req.table,
            limit=req.limit,
            offset=req.offset,
            filters=req.filters,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 1)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/data/search", response_model=SearchResponse)
async def api_search_data(req: SearchRequest, api_key: str = CreditAuth2):
    try:
        return await tools.search_data(
            query=req.query,
            source_id=req.source_id,
            n_results=req.n_results,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 2)
        raise HTTPException(status_code=500, detail=str(e))


# ── Pipeline endpoints ────────────────────────────────────────────────

@app.post("/pipeline/clean", response_model=CleanResult)
async def api_clean_data(req: CleanRequest, api_key: str = CreditAuth2):
    try:
        return await tools.clean_data(
            records=req.records,
            rules=req.rules,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 2)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/deduplicate", response_model=DedupResult)
async def api_deduplicate_data(req: DedupRequest, api_key: str = CreditAuth):
    try:
        return await tools.deduplicate_data(
            records=req.records,
            keys=req.keys,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 1)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/redact_pii", response_model=RedactResult)
async def api_redact_pii(req: RedactRequest, api_key: str = CreditAuth):
    try:
        return await tools.redact_pii_data(
            records=req.records,
            fields=req.fields,
            replacement=req.replacement,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 1)
        raise HTTPException(status_code=500, detail=str(e))


# ── Context endpoints ─────────────────────────────────────────────────

@app.post("/context/build", response_model=BuildContextResponse)
async def api_build_context(req: BuildContextRequest, api_key: str = CreditAuth3):
    try:
        return await tools.build_context(
            source_ids=req.source_ids,
            query=req.query,
            max_tokens=req.max_tokens,
            api_key=api_key,
        )
    except HTTPException:
        raise
    except Exception as e:
        await refund_credits(api_key, 3)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/context/summarize", response_model=SummarizeResponse)
async def api_summarize_data(req: SummarizeRequest, api_key: str = CreditAuth2):
    try:
        return await tools.summarize_data(
            source_id=req.source_id,
            table=req.table,
            question=req.question,
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        await refund_credits(api_key, 2)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        await refund_credits(api_key, 2)
        raise HTTPException(status_code=500, detail=str(e))


# ── Balance ────────────────────────────────────────────────────────────

@app.get("/balance", response_model=CheckBalanceResponse)
async def api_check_balance(api_key: str = Auth):
    return await tools.check_balance(api_key)


@app.get("/balance/history", response_model=BalanceResponse)
async def api_balance_history(api_key: str = Auth):
    agent = db.get_agent_by_api_key(api_key)
    balance = db.get_credit_balance(api_key)
    history = db.get_credit_history(api_key, limit=50)
    return {
        "credits": balance,
        "plan": agent["plan"] if agent else "free",
        "history": history,
    }


# ── Billing ────────────────────────────────────────────────────────────

@app.post("/billing/buy_credits", response_model=BuyCreditsResponse)
async def buy_credits(req: BuyCreditsRequest, api_key: str = Auth):
    try:
        result = billing.create_checkout_session(api_key, req.credits)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/billing/subscribe", response_model=SubscribeResponse)
async def subscribe(req: SubscribeRequest, api_key: str = Auth):
    try:
        result = billing.create_subscription_session(api_key, req.plan)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/billing/buy_credits_crypto", response_model=BuyCreditsCryptoResponse)
async def buy_credits_crypto(req: BuyCreditsCryptoRequest, api_key: str = Auth):
    try:
        result = await billing.create_crypto_payment(
            api_key, req.credits, req.fiat_usd, req.preferred_coin or "btc"
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/billing/check_payment", response_model=CheckPaymentStatusResponse)
async def check_payment(req: CheckPaymentStatusRequest, api_key: str = Auth):
    try:
        result = await billing.check_crypto_payment_status(req.payment_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Stripe webhook ─────────────────────────────────────────────────────

@app.post("/billing/stripe_webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        result = billing.handle_stripe_event(payload, sig)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Crypto IPN webhook ─────────────────────────────────────────────────

@app.post("/billing/crypto_ipn")
async def crypto_ipn(request: Request):
    payload = await request.json()
    sig = request.headers.get("x-nowpayments-sig", "")
    try:
        result = billing.handle_crypto_ipn(payload, sig)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
