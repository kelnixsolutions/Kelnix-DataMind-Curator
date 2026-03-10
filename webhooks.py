from __future__ import annotations

import db


async def check_low_balance(api_key: str) -> None:
    balance = db.get_credit_balance(api_key)
    if balance <= 5:
        subs = db.get_webhook_subscriptions(api_key)
        for sub in subs:
            if "low_balance" in sub["events"]:
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        await client.post(sub["url"], json={
                            "event": "low_balance",
                            "api_key": api_key[:8] + "...",
                            "balance": balance,
                        })
                except Exception:
                    pass
