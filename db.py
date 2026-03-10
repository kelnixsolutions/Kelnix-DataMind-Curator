from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional


# ── Simple encryption for connection strings ─────────────────────────────
# XOR-based obfuscation using a server-side key. Not military-grade, but
# prevents plaintext credentials if the DB file is exposed.

def _get_encryption_key() -> bytes:
    raw = os.environ.get("ANTHROPIC_API_KEY", "datamind-default-key")
    return hashlib.sha256(raw.encode()).digest()


def _encrypt(plaintext: str) -> str:
    key = _get_encryption_key()
    data = plaintext.encode()
    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.b64encode(encrypted).decode()


def _decrypt(ciphertext: str) -> str:
    key = _get_encryption_key()
    data = base64.b64decode(ciphertext)
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return decrypted.decode()

DB_PATH = Path(__file__).parent / "datamind.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id          TEXT PRIMARY KEY,
    api_key            TEXT NOT NULL,
    source_type        TEXT NOT NULL,
    name               TEXT NOT NULL,
    connection_string  TEXT,
    config_json        TEXT,
    status             TEXT NOT NULL DEFAULT 'connected',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    api_key             TEXT PRIMARY KEY,
    agent_name          TEXT NOT NULL,
    org_id              TEXT,
    plan                TEXT NOT NULL DEFAULT 'free',
    stripe_customer_id  TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key     TEXT NOT NULL,
    delta       INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (api_key) REFERENCES agents(api_key)
);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key     TEXT NOT NULL,
    url         TEXT NOT NULL,
    events      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (api_key) REFERENCES agents(api_key)
);

CREATE TABLE IF NOT EXISTS crypto_payments (
    payment_id          TEXT PRIMARY KEY,
    api_key             TEXT NOT NULL,
    credits             INTEGER NOT NULL,
    quoted_fiat_usd     REAL NOT NULL,
    locked_fiat_usd     REAL NOT NULL,
    crypto_amount       REAL NOT NULL,
    crypto_currency     TEXT NOT NULL,
    pay_address         TEXT,
    tx_hash             TEXT,
    status              TEXT NOT NULL DEFAULT 'waiting',
    rate_used           REAL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (api_key) REFERENCES agents(api_key)
);

CREATE TABLE IF NOT EXISTS contexts (
    context_id   TEXT PRIMARY KEY,
    api_key      TEXT NOT NULL,
    chunks_json  TEXT NOT NULL,
    token_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (api_key) REFERENCES agents(api_key)
);

CREATE INDEX IF NOT EXISTS idx_sources_api_key ON sources(api_key);
CREATE INDEX IF NOT EXISTS idx_credits_api_key ON credits(api_key);
CREATE INDEX IF NOT EXISTS idx_crypto_payments_api_key ON crypto_payments(api_key);
CREATE INDEX IF NOT EXISTS idx_contexts_api_key ON contexts(api_key);
"""

# ── Connection pool ──────────────────────────────────────────────────────

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return conn


@contextmanager
def _conn():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(SCHEMA)


# ── API key cache ────────────────────────────────────────────────────────

_api_key_cache: dict[str, float] = {}
_CACHE_TTL = 300


def api_key_exists(api_key: str) -> bool:
    now = time.monotonic()
    expiry = _api_key_cache.get(api_key)
    if expiry and now < expiry:
        return True
    exists = get_agent_by_api_key(api_key) is not None
    if exists:
        _api_key_cache[api_key] = now + _CACHE_TTL
    return exists


def _invalidate_cache(api_key: str) -> None:
    _api_key_cache.pop(api_key, None)


# ── Sources ──────────────────────────────────────────────────────────────

def insert_source(
    source_id: str,
    api_key: str,
    source_type: str,
    name: str,
    connection_string: str | None = None,
    config: dict | None = None,
) -> None:
    encrypted_conn = _encrypt(connection_string) if connection_string else None
    encrypted_config = _encrypt(json.dumps(config)) if config else None
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sources (source_id, api_key, source_type, name, connection_string, config_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source_id, api_key, source_type, name, encrypted_conn, encrypted_config),
        )


def get_source(source_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("connection_string"):
        d["connection_string"] = _decrypt(d["connection_string"])
    if d.get("config_json"):
        d["config"] = json.loads(_decrypt(d["config_json"]))
    return d


def list_sources(api_key: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT source_id, source_type, name, status, created_at FROM sources WHERE api_key = ? ORDER BY created_at DESC",
            (api_key,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_source(source_id: str, *, status: str | None = None) -> None:
    parts: list[str] = ["updated_at = datetime('now')"]
    params: list[Any] = []
    if status is not None:
        parts.append("status = ?")
        params.append(status)
    params.append(source_id)
    with _conn() as conn:
        conn.execute(f"UPDATE sources SET {', '.join(parts)} WHERE source_id = ?", params)


def delete_source(source_id: str, api_key: str) -> bool:
    with _conn() as conn:
        cursor = conn.execute("DELETE FROM sources WHERE source_id = ? AND api_key = ?", (source_id, api_key))
    return cursor.rowcount > 0


# ── Agents ───────────────────────────────────────────────────────────────

def create_agent(agent_name: str, org_id: str | None = None) -> dict[str, Any]:
    api_key = f"dm_{secrets.token_urlsafe(32)}"
    stripe_customer_id = None

    try:
        import stripe
        if stripe.api_key:
            customer = stripe.Customer.create(
                name=agent_name,
                metadata={"api_key": api_key, "org_id": org_id or ""},
            )
            stripe_customer_id = customer.id
    except Exception:
        pass

    with _conn() as conn:
        conn.execute(
            "INSERT INTO agents (api_key, agent_name, org_id, stripe_customer_id) VALUES (?, ?, ?, ?)",
            (api_key, agent_name, org_id, stripe_customer_id),
        )
    add_credits(api_key, 25, reason="free_tier_signup")
    _api_key_cache[api_key] = time.monotonic() + _CACHE_TTL
    return {
        "api_key": api_key,
        "agent_name": agent_name,
        "org_id": org_id,
        "stripe_customer_id": stripe_customer_id,
        "free_credits": 25,
    }


def get_agent_by_api_key(api_key: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM agents WHERE api_key = ?", (api_key,)).fetchone()
    if row is None:
        return None
    return dict(row)


def update_agent(api_key: str, *, plan: str | None = None) -> None:
    parts: list[str] = []
    params: list[Any] = []
    if plan is not None:
        parts.append("plan = ?")
        params.append(plan)
    if not parts:
        return
    params.append(api_key)
    with _conn() as conn:
        conn.execute(f"UPDATE agents SET {', '.join(parts)} WHERE api_key = ?", params)


# ── Credits ──────────────────────────────────────────────────────────────

def add_credits(api_key: str, amount: int, reason: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO credits (api_key, delta, reason) VALUES (?, ?, ?)",
            (api_key, amount, reason),
        )


def deduct_credits(api_key: str, amount: int, reason: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO credits (api_key, delta, reason) VALUES (?, ?, ?)",
            (api_key, -amount, reason),
        )


def atomic_deduct_if_sufficient(api_key: str, cost: int, reason: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) AS balance FROM credits WHERE api_key = ?",
            (api_key,),
        ).fetchone()
        balance = int(row["balance"])
        if balance < cost:
            return False
        conn.execute(
            "INSERT INTO credits (api_key, delta, reason) VALUES (?, ?, ?)",
            (api_key, -cost, reason),
        )
    return True


def get_credit_balance(api_key: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) AS balance FROM credits WHERE api_key = ?",
            (api_key,),
        ).fetchone()
    return int(row["balance"])


def get_credit_history(api_key: str, limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT delta, reason, created_at FROM credits WHERE api_key = ? ORDER BY created_at DESC LIMIT ?",
            (api_key, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Contexts ─────────────────────────────────────────────────────────────

def insert_context(context_id: str, api_key: str, chunks_json: str, token_count: int) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO contexts (context_id, api_key, chunks_json, token_count) VALUES (?, ?, ?, ?)",
            (context_id, api_key, chunks_json, token_count),
        )


def get_context(context_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM contexts WHERE context_id = ?", (context_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["chunks"] = json.loads(d["chunks_json"])
    return d


# ── Webhook subscriptions ───────────────────────────────────────────────

def add_webhook_subscription(api_key: str, url: str, events: list[str]) -> int:
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO webhook_subscriptions (api_key, url, events) VALUES (?, ?, ?)",
            (api_key, url, json.dumps(events)),
        )
    return cursor.lastrowid


def get_webhook_subscriptions(api_key: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM webhook_subscriptions WHERE api_key = ?", (api_key,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["events"] = json.loads(d["events"])
        result.append(d)
    return result


# ── Crypto payments ─────────────────────────────────────────────────────

def insert_crypto_payment(
    payment_id: str,
    api_key: str,
    credits: int,
    quoted_fiat_usd: float,
    locked_fiat_usd: float,
    crypto_amount: float,
    crypto_currency: str,
    pay_address: str | None = None,
    rate_used: float | None = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO crypto_payments "
            "(payment_id, api_key, credits, quoted_fiat_usd, locked_fiat_usd, "
            "crypto_amount, crypto_currency, pay_address, rate_used) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payment_id, api_key, credits, quoted_fiat_usd, locked_fiat_usd,
             crypto_amount, crypto_currency, pay_address, rate_used),
        )


def get_crypto_payment(payment_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM crypto_payments WHERE payment_id = ?", (payment_id,)).fetchone()
    if row is None:
        return None
    return dict(row)


def update_crypto_payment(payment_id: str, *, status: str | None = None, tx_hash: str | None = None) -> None:
    parts: list[str] = ["updated_at = datetime('now')"]
    params: list[Any] = []
    if status is not None:
        parts.append("status = ?")
        params.append(status)
    if tx_hash is not None:
        parts.append("tx_hash = ?")
        params.append(tx_hash)
    params.append(payment_id)
    with _conn() as conn:
        conn.execute(f"UPDATE crypto_payments SET {', '.join(parts)} WHERE payment_id = ?", params)
