# juphedge

[![ci](https://github.com/mrmrborisov-arch/juphedge/actions/workflows/ci.yml/badge.svg)](https://github.com/mrmrborisov-arch/juphedge/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

One-command Solana portfolio hedger that composes **five+ Jupiter APIs** into a
single structured "hedge plan" for any wallet address.

**Live demo:** https://juphedge-wunclset.fly.dev/
**Source:** https://github.com/mrmrborisov-arch/juphedge

Type any Solana wallet → get back a plan that covers:

| # | Leg                       | Jupiter API                           |
|---|---------------------------|---------------------------------------|
| 1 | Classify positions        | Price v3 + Tokens v2                  |
| 2 | Trigger OCO (TP/SL) bands | `POST /trigger/v2/orders/price`       |
| 3 | Idle-stable yield sweep   | `POST /lend/v1/earn/deposit`          |
| 4 | Concentration DCA trim    | `POST /recurring/v1/createOrder`      |
| 5 | **Prediction-market hedge** | `POST /prediction/v1/order`         |

Everything runs keyless on `lite-api.jup.ag` (0.5 RPS) — no sign-up required
to try it.

## The weird combo

Jupiter's Prediction Markets are pitched as a way to **speculate on events**
(crypto price targets, sports outcomes, politics). juphedge turns them into
**insurance instruments**: for your biggest concentrated spot position we find
an upside-target prediction event on the same asset (or a correlated proxy,
e.g. SOL → BTC) and suggest buying **NO** contracts.

The math is a crude analog to an out-of-the-money put:

- Each NO contract pays **$1** if the asset misses its upside target.
- If you own `$X` of SOL spot, size contracts so payout covers ~30% of `X`.
- Cost is small (NO side on "BTC hits $150k by 2026-12-31" currently trades
  at ≈ $0.89, i.e. the market thinks there's an 89% chance BTC does **not**
  reach that target — so this specific market is a weak hedge; juphedge
  reports the implied probability so you can pick sharper markets).
- Crypto correlations rise during drawdowns, which is exactly when the hedge
  needs to pay — a property of correlation that's a feature here, not a bug.

Prediction Markets weren't built for this. That's what makes the combination
interesting — and what the bounty is asking for.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn src.main:app --port 8848
open http://localhost:8848
```

Optionally set `JUPITER_API_KEY` to upgrade from the keyless 0.5 RPS tier, and
`SOLANA_RPC` to override the mainnet-beta RPC.

## API

```bash
curl -s "https://juphedge-wunclset.fly.dev/api/analyze?wallet=<ADDR>"
```

Returns one JSON plan with: positions, trigger_orders, lend_sweep, dca_plan,
prediction_hedge, trace, and jupiter_apis_used. No transactions are signed —
an agent consumer executes plan items with its own signer.

## Agent skill

`SKILL.md` is published in the repo root so any coding agent (Devin / Cursor /
Claude Code) can consume it via `npx skills add` or by pointing their skill
scanner at this repo.

## Honest reflection

See [REFLECTION.md](REFLECTION.md) — what went wrong during the build, what I
hated about the API shape, and where the "insurance leg" idea is currently
hand-wavy.

## Structure

```
src/
  main.py       FastAPI app + dashboard
  analyzer.py   Portfolio classifier + plan composer
  jupiter.py    Jupiter + Solana RPC client
docs/           Jupiter API docs scraped during build (for offline reference)
PLAN.md         Original design doc
REFLECTION.md   What sucked
SKILL.md        Agent-facing skill file
```
