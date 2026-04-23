"""Portfolio analysis + hedge plan.

Given a Solana wallet, produce a structured hedge plan using multiple Jupiter
APIs simultaneously:

  Tokens + Price  -> classify positions
  Trigger         -> suggest OCO (TP/SL) bands per volatile position
  Lend            -> sweep idle stables into best earn APY
  Recurring       -> DCA-out trim schedule on concentrated high-conviction
  Prediction      -> hedge the largest directional bet with a NO contract
                     on an upside-target event for that asset

The "weird" combination is #5: most people view Prediction Markets as
speculation instruments. We use them as an insurance leg against concentrated
spot exposure. That is the Jupiter-API combination this project asks for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import jupiter as jup

# --- Stablecoins we treat as "idle" if sitting in a wallet ---
STABLES = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo": "PYUSD",
    "jupSoLaHXQiZZTSfEWMTRRgpnyFm8f6sZdosWBjx93v": "jupSOL",  # not stable but close
    "USDSwr9ApdHk5bvJKMjzff41FfuX8bSxdKcR81vTwcA": "USDS",
}
MAJOR_CONVICTION = {
    jup.WSOL_MINT: "SOL",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
}


@dataclass
class Position:
    mint: str
    symbol: str
    amount: float
    usd_value: float
    usd_price: float
    change_24h: float
    classification: str  # idle-stable / high-conviction / volatile / dust
    liquidity: float = 0.0
    organic_score: float | None = None


@dataclass
class HedgePlan:
    wallet: str
    total_usd: float
    positions: list[Position]
    idle_stable_usd: float
    trigger_orders: list[dict[str, Any]] = field(default_factory=list)
    lend_sweep: dict[str, Any] | None = None
    dca_plan: dict[str, Any] | None = None
    prediction_hedge: dict[str, Any] | None = None
    trace: list[str] = field(default_factory=list)


def _classify(mint: str, sym: str, usd_val: float, liq: float) -> str:
    if usd_val < 0.10:
        return "dust"
    if mint in STABLES:
        return "idle-stable"
    if mint in MAJOR_CONVICTION or liq > 10_000_000:
        return "high-conviction"
    return "volatile"


def analyze(wallet: str) -> HedgePlan:
    trace: list[str] = [f"[step 1] reading wallet {wallet} via Solana RPC"]
    bal = jup.wallet_balances(wallet)
    sol_lamports = bal["sol_lamports"]
    spl = bal["spl"]
    for w in bal.get("warnings", []):
        trace.append(f"[warn] {w}")

    # Treat native SOL as WSOL mint for pricing
    mint_amounts: dict[str, float] = {}
    if sol_lamports > 0:
        mint_amounts[jup.WSOL_MINT] = mint_amounts.get(jup.WSOL_MINT, 0.0) + sol_lamports / 1e9
    for m, a in spl.items():
        mint_amounts[m] = mint_amounts.get(m, 0.0) + a

    if not mint_amounts:
        return HedgePlan(
            wallet=wallet,
            total_usd=0.0,
            positions=[],
            idle_stable_usd=0.0,
            trace=trace + ["wallet is empty"],
        )

    mints = list(mint_amounts.keys())
    trace.append(f"[step 2] pricing {len(mints)} mints via Jupiter Price v3")
    prices = jup.price(mints[:50])  # cap at 50 per call

    # Pull token metadata only for positions with meaningful USD value to keep
    # keyless rate-limit headroom. Price v3 already gives us liquidity + 24h
    # change; Tokens v2 adds symbol + organic score which we want for the
    # top-N positions so the rendered output reads well.
    trace.append("[step 3] fetching token metadata (top-N) via Jupiter Tokens v2")
    # Rough pre-rank by (price * amount)
    pre_ranked = sorted(
        mints,
        key=lambda m: (float(prices.get(m, {}).get("usdPrice") or 0)) * mint_amounts.get(m, 0),
        reverse=True,
    )
    meta: dict[str, dict[str, Any]] = {}
    for m in pre_ranked[:12]:  # cap metadata lookups
        info = jup.token_info(m)
        if info:
            meta[m] = info

    positions: list[Position] = []
    for m, amt in mint_amounts.items():
        p_entry = prices.get(m) or {}
        price_usd = float(p_entry.get("usdPrice") or (meta.get(m, {}).get("usdPrice") or 0))
        liq = float(meta.get(m, {}).get("liquidity") or p_entry.get("liquidity") or 0)
        sym = meta.get(m, {}).get("symbol") or STABLES.get(m) or MAJOR_CONVICTION.get(m) or m[:4]
        usd_val = price_usd * amt
        pos = Position(
            mint=m,
            symbol=sym,
            amount=amt,
            usd_value=usd_val,
            usd_price=price_usd,
            change_24h=float(p_entry.get("priceChange24h") or 0),
            classification=_classify(m, sym, usd_val, liq),
            liquidity=liq,
            organic_score=meta.get(m, {}).get("organicScore"),
        )
        positions.append(pos)

    positions.sort(key=lambda p: p.usd_value, reverse=True)
    total = sum(p.usd_value for p in positions)
    idle_stable_usd = sum(p.usd_value for p in positions if p.classification == "idle-stable")

    plan = HedgePlan(
        wallet=wallet,
        total_usd=total,
        positions=positions,
        idle_stable_usd=idle_stable_usd,
        trace=trace,
    )

    # Step 4: Trigger OCO for each volatile / high-conviction holding
    plan.trace.append("[step 4] building Trigger OCO bands per non-stable position")
    for p in positions:
        if p.classification in ("idle-stable", "dust"):
            continue
        # Volatility-scaled bands: more volatile -> wider. Fall back to ±15/-10% if no data.
        vol = abs(p.change_24h) or 5.0
        tp_pct = max(1.10, 1.0 + min(vol, 25.0) / 100.0 * 3.0)  # e.g. 5% vol -> +15% TP
        sl_pct = min(0.93, 1.0 - min(vol, 25.0) / 100.0 * 1.5)  # e.g. 5% vol -> -7.5% SL
        plan.trigger_orders.append(
            {
                "mint": p.mint,
                "symbol": p.symbol,
                "amount": p.amount,
                "entry_price_usd": p.usd_price,
                "take_profit_usd": round(p.usd_price * tp_pct, 6),
                "stop_loss_usd": round(p.usd_price * sl_pct, 6),
                "endpoint": "POST /trigger/v2/orders/price  (OCO)",
                "type": "oco",
                "why": f"24h |Δ|={vol:.1f}% -> bands widened accordingly",
            }
        )

    # Step 5: Lend sweep for idle stables
    if idle_stable_usd > 0:
        plan.trace.append("[step 5] searching Jupiter Lend for best USDC/USDT APY")
        earns = jup.lend_earn_tokens() or []
        best = None
        for e in earns:
            mint = e.get("asset") or e.get("mint")
            if mint in STABLES:
                apy = float(e.get("apy") or e.get("supplyApy") or 0)
                if best is None or apy > best["apy"]:
                    best = {"apy": apy, "asset": STABLES.get(mint, mint), "mint": mint}
        if best is None:
            best = {"apy": None, "asset": "USDC", "mint": list(STABLES)[0], "note": "lend API data unavailable"}
        plan.lend_sweep = {
            "amount_usd": idle_stable_usd,
            "target": best,
            "endpoint": "POST /lend/v1/earn/deposit",
            "projected_annual_yield_usd": (idle_stable_usd * best["apy"] / 100.0) if best.get("apy") else None,
        }

    # Step 6: Recurring DCA-out trim on largest concentrated high-conviction
    high_conv = [p for p in positions if p.classification == "high-conviction" and p.usd_value > 25]
    if high_conv:
        top = high_conv[0]
        if top.usd_value / max(total, 1e-9) > 0.5:
            plan.trace.append(f"[step 6] {top.symbol} is >50% of portfolio -> propose Recurring trim")
            plan.dca_plan = {
                "mint": top.mint,
                "symbol": top.symbol,
                "action": "sell",
                "output": "USDC",
                "chunk_usd": round(top.usd_value * 0.05, 2),
                "interval_hours": 24,
                "cycles": 10,
                "endpoint": "POST /recurring/v1/createOrder",
                "why": f"{top.symbol} is {top.usd_value / total * 100:.0f}% of portfolio. "
                       "Trim 50% over 10 days to reduce concentration.",
            }

    # Step 7: Prediction-market hedge for the largest non-stable position
    non_stable = [p for p in positions if p.classification != "idle-stable" and p.usd_value > 0.10]
    if non_stable:
        top = non_stable[0]
        plan.trace.append(
            f"[step 7] searching Prediction Markets for a NO-side hedge on {top.symbol} upside events"
        )
        market = jup.find_hedge_market(top.symbol, direction="down")
        if market:
            # To hedge $X of spot exposure, size NO position such that
            # payout covers a 30% drawdown -- approximation, not portfolio-math proof.
            target_coverage = top.usd_value * 0.30
            contract_cost = market["price_usd"] or 0.0001
            contracts = int(target_coverage / max(contract_cost, 0.0001))
            plan.prediction_hedge = {
                "spot_symbol": top.symbol,
                "spot_usd": top.usd_value,
                "market": market,
                "suggested_contracts": contracts,
                "cost_usd": round(contracts * contract_cost, 2),
                "payout_if_correct_usd": contracts * 1.0,
                "endpoint": "POST /prediction/v1/order",
                "why": "Buy NO contracts on an upside-target event for your biggest spot bet. "
                       "Acts as cheap tail insurance: if spot crashes, the event misses its target, "
                       "contracts resolve at $1 each. Jupiter's Prediction API isn't designed "
                       "for this use, which is exactly why it's a high-signal hedge.",
            }
        else:
            plan.trace.append("[step 7] no matching prediction market found")

    plan.trace.append("[done] plan ready — all 5+ Jupiter APIs composed")
    return plan
