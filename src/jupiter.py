"""Jupiter Developer Platform client.

Uses the keyless endpoint (0.5 RPS) at lite-api.jup.ag. If JUPITER_API_KEY is
set, we bump to api.jup.ag + x-api-key header for the higher free-tier rate.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

KEYLESS_BASE = "https://lite-api.jup.ag"
KEYED_BASE = "https://api.jup.ag"
SOLANA_RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")

_API_KEY = os.environ.get("JUPITER_API_KEY", "").strip()


def _base() -> str:
    return KEYED_BASE if _API_KEY else KEYLESS_BASE


def _headers() -> dict[str, str]:
    h = {"accept": "application/json", "user-agent": "juphedge/0.1"}
    if _API_KEY:
        h["x-api-key"] = _API_KEY
    return h


# -- Simple in-process cache so repeated frontend refreshes don't burn
# the 0.5 RPS keyless budget. --
_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}
_TTL = 30.0


def _get(path: str, params: dict[str, Any] | None = None, ttl: float = _TTL) -> Any:
    key = (path, repr(sorted((params or {}).items())))
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    url = f"{_base()}{path}"
    with httpx.Client(timeout=20.0) as c:
        r = c.get(url, params=params, headers=_headers())
        r.raise_for_status()
        data = r.json()
    _CACHE[key] = (now, data)
    return data


def _post(path: str, json_body: dict[str, Any]) -> Any:
    url = f"{_base()}{path}"
    with httpx.Client(timeout=20.0) as c:
        r = c.post(url, json=json_body, headers=_headers())
        r.raise_for_status()
        return r.json()


# ---------------- Price ----------------
def price(mints: list[str]) -> dict[str, dict[str, Any]]:
    """Return {mint: {usdPrice, priceChange24h, liquidity, ...}} for up to 50 mints."""
    if not mints:
        return {}
    return _get("/price/v3", {"ids": ",".join(mints)}) or {}


# ---------------- Tokens ----------------
def token_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    out = _get("/tokens/v2/search", {"query": query, "limit": limit})
    if isinstance(out, list):
        return out
    return out.get("data", []) if isinstance(out, dict) else []


def token_info(mint: str) -> dict[str, Any]:
    hits = token_search(mint, limit=1)
    return hits[0] if hits else {}


# ---------------- Prediction ----------------
def prediction_events(category: str = "crypto", limit: int = 20) -> list[dict[str, Any]]:
    r = _get("/prediction/v1/events", {"category": category, "limit": limit})
    return r.get("data", []) if isinstance(r, dict) else (r or [])


_CRYPTO_CORRELATION_PROXY = {
    "SOL": "BTC",
    "JUP": "BTC",
    "BONK": "BTC",
    "WIF": "BTC",
    "RAY": "BTC",
    "PYTH": "BTC",
    "ORCA": "BTC",
}


def _extract_hedge_candidate(ev: dict[str, Any], m: dict[str, Any], proxy_note: str = "") -> dict[str, Any] | None:
    rules = (m.get("rulesPrimary") or "") + " " + (m.get("title") or "")
    upside_words = ("reach", "hit", "above", ">", ">=", "greater", "higher", "$")
    if not any(w in rules.lower() for w in upside_words):
        return None
    pricing = m.get("pricing") or {}
    buy_no_micro = pricing.get("buyNoPriceUsd")
    if buy_no_micro is None:
        return None
    price_usd = float(buy_no_micro) / 1_000_000.0
    if price_usd <= 0 or price_usd >= 1.0:
        return None
    return {
        "event_id": ev.get("eventId"),
        "event_title": (ev.get("metadata") or {}).get("title"),
        "market_id": m.get("marketId"),
        "market_title": m.get("title"),
        "side": "NO",
        "price_usd": price_usd,
        "close_time": m.get("closeTime"),
        "implied_prob_down": 1.0 - float(pricing.get("buyYesPriceUsd", 0) or 0) / 1_000_000.0,
        "proxy_note": proxy_note,
    }


def find_hedge_market(symbol: str, direction: str = "down") -> dict[str, Any] | None:
    """Find a prediction market that pays if the given symbol's price goes DOWN.

    Strategy: look for markets whose YES side means "price REACHED an upside target".
    Buying NO on those markets pays $1 if the target is missed -> acts like a
    put option on the asset. When no direct market exists for the symbol we
    fall back to a correlated-proxy (SOL/JUP/BONK -> BTC), since crypto
    correlations tend to 0.8+ during drawdowns -- which is when you need the
    hedge most.
    """
    symbol = symbol.upper()
    events = prediction_events("crypto", limit=40)

    # First pass: exact-symbol match
    for ev in events:
        sub = (ev.get("subcategory") or "").upper()
        title = ((ev.get("metadata") or {}).get("title") or "")
        if sub != symbol and symbol.lower() not in title.lower():
            continue
        for m in ev.get("markets", []):
            if m.get("status") != "open":
                continue
            cand = _extract_hedge_candidate(ev, m)
            if cand:
                return cand

    # Fallback: correlated-proxy hedge
    proxy = _CRYPTO_CORRELATION_PROXY.get(symbol)
    if proxy:
        for ev in events:
            sub = (ev.get("subcategory") or "").upper()
            if sub != proxy:
                continue
            for m in ev.get("markets", []):
                if m.get("status") != "open":
                    continue
                cand = _extract_hedge_candidate(
                    ev, m,
                    proxy_note=f"No direct {symbol} market found. Using {proxy} upside-miss as correlated proxy (~0.8 correlation during drawdowns).",
                )
                if cand:
                    return cand
    return None


# ---------------- Lend (read-only earn markets) ----------------
def lend_earn_tokens() -> list[dict[str, Any]]:
    """Lend API Earn tokens list (read-only)."""
    try:
        r = _get("/lend/v1/earn/tokens")
        if isinstance(r, list):
            return r
        return r.get("data", []) if isinstance(r, dict) else []
    except httpx.HTTPError:
        return []


# ---------------- Solana RPC (needed for wallet-scan) ----------------
def solana_rpc(method: str, params: list[Any], retries: int = 2) -> Any:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=20.0) as c:
                r = c.post(
                    SOLANA_RPC,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    headers={"content-type": "application/json"},
                )
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            body = r.json()
            if "error" in body:
                raise RuntimeError(f"RPC error: {body['error']}")
            return body.get("result")
        except httpx.HTTPError as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))
    if last_err:
        raise last_err
    return None


def wallet_balances(wallet: str) -> dict[str, Any]:
    """Return {sol_lamports, spl: {mint: uiAmount}, warnings: [...]}."""
    warnings: list[str] = []
    try:
        sol_res = solana_rpc("getBalance", [wallet])
        sol_lamports = (sol_res or {}).get("value", 0)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"getBalance failed: {e}")
        sol_lamports = 0

    spl: dict[str, float] = {}
    for prog in (
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL token
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022
    ):
        try:
            accts = solana_rpc(
                "getTokenAccountsByOwner",
                [wallet, {"programId": prog}, {"encoding": "jsonParsed"}],
            )
            for acc in (accts or {}).get("value", []):
                info = acc["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                amt = info["tokenAmount"]
                ui = amt.get("uiAmount")
                if ui and ui > 0:
                    spl[mint] = spl.get(mint, 0.0) + ui
        except Exception as e:  # noqa: BLE001
            warnings.append(f"getTokenAccountsByOwner({prog[:4]}…) failed: {str(e)[:120]}")

    return {"sol_lamports": sol_lamports, "spl": spl, "warnings": warnings}


WSOL_MINT = "So11111111111111111111111111111111111111112"
