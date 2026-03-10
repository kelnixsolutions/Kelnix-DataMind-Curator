from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import httpx

BASE_URL = "https://api.nowpayments.io/v1"


def _headers() -> dict[str, str]:
    return {
        "x-api-key": os.environ.get("NOWPAYMENTS_API_KEY", ""),
        "Content-Type": "application/json",
    }


async def get_estimated_price(fiat_amount: float, fiat_currency: str, crypto: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/estimate",
            params={"amount": fiat_amount, "currency_from": fiat_currency, "currency_to": crypto},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    return {"estimated_amount": data.get("estimated_amount", 0), "rate": data.get("rate", 0)}


async def create_payment(
    fiat_amount: float,
    fiat_currency: str,
    crypto_currency: str,
    order_id: str,
    order_description: str,
    ipn_callback_url: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "price_amount": fiat_amount,
        "price_currency": fiat_currency,
        "pay_currency": crypto_currency,
        "order_id": order_id,
        "order_description": order_description,
    }
    if ipn_callback_url:
        body["ipn_callback_url"] = ipn_callback_url

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BASE_URL}/payment", json=body, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    return {
        "payment_id": str(data["payment_id"]),
        "pay_amount": data["pay_amount"],
        "pay_currency": data["pay_currency"],
        "pay_address": data.get("pay_address"),
        "expiration_estimate_date": data.get("expiration_estimate_date"),
    }


async def get_payment_status(payment_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/payment/{payment_id}", headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    return {
        "payment_status": data.get("payment_status", "unknown"),
        "pay_amount": data.get("pay_amount", 0),
        "actually_paid": data.get("actually_paid", 0),
        "pay_currency": data.get("pay_currency", ""),
    }


def verify_ipn_signature(payload: dict, sig_header: str) -> bool:
    secret = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
    if not secret:
        raise ValueError("NOWPAYMENTS_IPN_SECRET not configured. Cannot verify IPN signature.")
    sorted_payload = dict(sorted(payload.items()))
    import json
    payload_str = json.dumps(sorted_payload, separators=(",", ":"))
    expected = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, sig_header)
