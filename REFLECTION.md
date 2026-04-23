# REFLECTION — what sucked building juphedge

This is the honest "what went wrong" section the bounty asks for. No polish.
Written in the order things broke.

## 1. I started planning before I read the docs

I wrote a PLAN.md with five API legs composed together before I had any
keyless endpoint responses. Two legs that looked fine on paper turned out to
be partially blocked keyless:

- **Portfolio** endpoint (`/portfolio/v1/positions`) — route returned
  `Route not found` without a signed-in account. I swapped to a raw Solana
  RPC `getTokenAccountsByOwner` scan instead, which means I pay for my own
  correlation between mint addresses and token metadata rather than letting
  Jupiter do it. Dropping Portfolio cost me the staking positions and any
  Jupiter-product positions the raw RPC can't see.
- **Lend** (`/lend/v1/earn/tokens`) — the read-only endpoint exists but
  returned nothing usable keyless during this build. I now fall back to a
  "USDC, APY unknown" placeholder, which is a bad user experience. With a
  keyed Developer plan this should return real APYs.

Lesson: on future Jupiter builds, run `curl` on every endpoint I plan to use
**before** touching the design doc. The docs are good; what they don't tell
you is which routes silently require an API key.

## 2. Solana RPC rate-limits are the real bottleneck, not Jupiter rate-limits

I hit 429 on `api.mainnet-beta.solana.com` almost immediately when scanning a
whale wallet (`getTokenAccountsByOwner` returns a blob proportional to the
number of ATAs). The free public RPCs I tried next all reject the call:

- `publicnode` — `blocked parameter: params.1.programId`
- `rpcpool` / `free.rpcpool` / `drpc.org` — `blocked` / paid-tier-only
- `helius` demo key — `invalid api key`
- `zan.top` — requires Origin header (browser only)

So juphedge defaults back to `api.mainnet-beta.solana.com` with exponential
backoff and graceful warnings, but for any serious deployment the operator
needs a real RPC provider. **Jupiter's keyless 0.5 RPS is not the bottleneck.
Solana RPC auth is.** A "Portfolio" API that hides this complexity would be
a huge win for agents like this — that's what I thought Portfolio was, which
is why #1 hurt.

## 3. `getTokenAccountsByOwner` doesn't scale to big wallets

JUP DAO multisig (`CapuXNQoDviLvU1PxFiizLgPNQCxrsag1uMeyk6zLVps`) blew up
with `scan aborted: The accumulated scan results exceeded the limit`. I
caught it in a try/except and kept going, but this means juphedge degrades
for the wallets that would benefit most from automation (big treasuries).
The fix is to use Solana RPC's `getProgramAccounts` with a filter on owner
**plus** a `dataSize`+`memcmp` filter that only returns ATAs — but that
requires `getProgramAccounts` access which most public RPCs rate-limit even
harder. No great answer without a paid RPC.

## 4. Prediction Markets have very few open events

`/prediction/v1/events?category=crypto&limit=100` returned **10 events**.
All were BTC / ETH / XRP. No SOL, no JUP, no BONK. For a "Solana-first"
platform, there's a surprising amount of non-Solana event supply — most
markets are sourced from Polymarket (`POLY-…` event IDs).

This forced the correlated-proxy fallback I built (SOL → BTC, with a note
to the user). It's a reasonable engineering decision — crypto correlations
do spike to 0.8+ in drawdowns — but it's also a real gap in the product. If
Jupiter wants Prediction Markets to serve Solana traders it needs more
Solana-native event supply.

## 5. The "insurance leg" math is hand-wavy

I'm calling "30% of spot value / cost-per-NO-contract = number of contracts"
a hedge. That's not a proper portfolio-math hedge — a real hedge would:

- Back-test SOL/BTC correlation by regime.
- Size by delta × exposure, not by a flat 30% coverage rule.
- Account for event-resolution timing vs. the drawdown horizon.
- Consider the basis risk of Polymarket-sourced events settling
  independently of Jupiter-native markets.

I left this crude because the point of the submission was to compose APIs
Jupiter didn't design to be composed, not to ship a production hedge book.
Saying so out loud because the bounty asks for it.

## 6. Deployment surprise — `fastapi[standard]`

First Fly deploy crashed with `RuntimeError: To use the fastapi command,
please install "fastapi[standard]"`. The `deploy backend` helper invokes
`fastapi run` in the generated Dockerfile, which requires the `[standard]`
extras. Plain `fastapi` + `uvicorn[standard]` isn't enough. Five-minute
fix but worth knowing.

## 7. What I did NOT build and would next

- **Actual signing + execution.** Everything in juphedge is plan-only. A
  follow-on version would take an optional keypair path, build the Jupiter
  transactions, simulate them, and execute with a `--confirm` gate.
- **Backtesting UI.** Let the user pass a historical wallet snapshot and see
  what juphedge would have recommended a month ago vs. what actually
  happened. Without this the "hedge" claim is just a vibe.
- **Skill file distribution.** `SKILL.md` is in this repo but not yet in
  the `npx skills` registry. Next step is to PR it into jup-ag/skills.
- **Portfolio API fallback.** If the keyed Portfolio API is available, skip
  the raw Solana RPC scan entirely. Faster, broader coverage.
- **More asset classes in the hedge leg.** Sports / politics / tech events
  could hedge sector-specific alt-concentration (e.g. short gaming-token
  drawdown with a "X game wins esports event" market). Didn't get to it.

## 8. Meta

What I liked about Jupiter's platform: the keyless tier is a legitimate
prototyping tier (0.5 RPS is enough for one-at-a-time agent calls), the
error messages are clear, and `llms.txt` is actually useful for an agent
boot-strapping from zero. What I'd change: Portfolio v1 gated keyless is
the single biggest pain point for agent-first use cases; fix that and every
agent builder's first-week Jupiter experience gets dramatically better.
