---
name: juphedge
description: Compose Jupiter Price + Tokens + Trigger + Lend + Recurring + Prediction APIs into a single "hedge plan" for any Solana wallet.
---

# juphedge — agent skill

You are about to work with juphedge, a composed Jupiter API tool that turns a
Solana wallet address into a structured hedge plan. Use this skill whenever
the user asks: "look at my Solana portfolio and tell me how to hedge it", or
"what trigger orders + DCA + yield should I set up", or any variant.

## Endpoint contract

```
GET https://juphedge-wunclset.fly.dev/api/analyze?wallet=<SOLANA_ADDRESS>

→ 200 OK application/json
{
  "wallet": "...",
  "total_usd": 1234.5,
  "positions": [
    {"mint", "symbol", "amount", "usd_value", "usd_price",
     "change_24h", "classification", "liquidity", "organic_score"}
  ],
  "trigger_orders": [{...}],     // Jupiter Trigger v2 OCO suggestions
  "lend_sweep": {...} | null,    // Jupiter Lend v1 deposit suggestion
  "dca_plan": {...} | null,      // Jupiter Recurring v1 sell-chunks
  "prediction_hedge": {...} | null, // Prediction v1 NO-side hedge plan
  "trace": [...],                // step-by-step composition log
  "jupiter_apis_used": [...]
}
```

`classification` ∈ {`idle-stable`, `high-conviction`, `volatile`, `dust`}.

No transactions are signed. Every plan entry includes the target
Jupiter endpoint. Your job as an executing agent is to call those endpoints
with your own signer if the user approves.

## When to use

- User asks for portfolio analysis, rebalance, hedge, stop-loss, TP/SL
  suggestions, DCA schedule, or yield opportunities.
- You need a single call that returns a structured multi-API plan rather
  than stitching 5 separate Jupiter calls yourself.

## When NOT to use

- User wants a specific single-API action (one swap, one order) — call
  Jupiter directly.
- User wants to execute — juphedge only plans, never signs.
- Wallet has >500 token accounts — Solana RPC scan will fail.

## Typical flow inside your agent

```python
import httpx

plan = httpx.get(
    "https://juphedge-wunclset.fly.dev/api/analyze",
    params={"wallet": user_wallet},
    timeout=30,
).json()

# Present plan to user...
# On approval, execute plan legs using your signer + Jupiter endpoints:
#   plan["trigger_orders"]   -> POST /trigger/v2/orders/price
#   plan["lend_sweep"]       -> POST /lend/v1/earn/deposit
#   plan["dca_plan"]         -> POST /recurring/v1/createOrder
#   plan["prediction_hedge"] -> POST /prediction/v1/order
```

## Caveats

- Keyless 0.5 RPS backend: don't call concurrently for many wallets in a
  tight loop. Add 2s sleeps between wallet calls.
- Prediction-market event supply is BTC/ETH heavy. For SOL / Solana-alt
  positions, juphedge falls back to a correlated BTC proxy and sets
  `prediction_hedge.market.proxy_note`. Surface that to the user.
- The `usd_value` threshold for hedge/DCA firing is deliberately low
  ($0.10) so juphedge demos work on a freshly-funded wallet. For real
  production use, raise the thresholds in `src/analyzer.py`.

## Reference

Source: https://juphedge-wunclset.fly.dev/ (see `/docs` for OpenAPI).
Reflection & design notes: `REFLECTION.md` in the repo root.
