# Superteam Earn — "Not Your Regular Bounty" ($3000 jupUSD)

Agent: `devin-0x3peK` / Superteam username `devin-0x3pek-brown-16`.
Listing: `not-your-regular-bounty` (id `9a42cdbf-f931-4560-9663-99afe37e5656`).
Status: OPEN. Access: AGENT_ALLOWED. Deadline: **2026-05-12T11:59 UTC** (19 days).

Claim code (for user to claim payout if we win): stored in `/home/ubuntu/.wallet/superteam.env`.

## What Jupiter explicitly wants

1. A **working thing** that uses one or more Jupiter APIs through the Developer Platform.
2. An **honest reflection** on what sucked during the build.
3. "Weird" is encouraged — "combine APIs in ways we didn't design for" — "if we have to sit with your submission for a minute before we realize it's genius, that's what we're looking for."

## Jupiter APIs on offer

| API | What it does |
|---|---|
| Swap V2 | `/order` + `/execute` (managed) or `/build` (raw ix). Gasless built in. |
| Tokens | Search / metadata / verification status / organic scores / trading metrics. |
| Price | USD pricing of all Solana tokens. |
| Lend | Yield on deposits, borrowing, flashloans. |
| Trigger | Limit orders — single, OCO (TP/SL), OTOCO. **NEW.** |
| Recurring | Time-based DCA. |
| Prediction Markets | Binary markets on real-world events. |
| Perps | Leveraged perpetuals on Solana. |
| Jupiter CLI | JSON-native non-interactive — Telegram + agent-friendly. |
| Jupiter AI Stack | Agent Skills / Docs MCP / llms.txt. |

## Proposed concept (1st pass) — `juphedge`

One-command Solana portfolio auto-hedger. Given a wallet address + risk budget, it:

1. Reads holdings via Token + Price.
2. Classifies each position as "high-conviction / volatile / idle-stable".
3. **Trigger** → places OCO (TP/SL) on every high-conviction volatile position.
4. **Prediction Markets** → opens an offsetting binary position (e.g. "SOL > $X by date") to hedge directional drawdown risk on the largest concentrated holding — *this is the "weird" API combo that Jupiter didn't explicitly design for*.
5. **Lend** → sweeps idle stables into yield.
6. **Recurring** → DCA out of volatile winners / into undervalued tokens per a policy file.
7. Prints an audit trail: "for each API call, which was chosen and why."

Why this wins "non-regular":
- Uses 5+ APIs in one flow.
- **Prediction Markets as a hedge instrument, not a speculation instrument** — that's the unexpected combination they can't help but notice.
- Agent-native: single JSON-in / JSON-out CLI, ships a Jupiter skill file other agents can consume.
- Demo mode runs on any wallet address (read-only) without funds — makes the judging demo frictionless.

## Deliverables

1. **CLI binary** (Python or TS) deployed as a public endpoint via `devinapps.com` (frontend dashboard + API).
2. **Agent skill.md** that makes this consumable by Claude Code / Cursor / Devin etc.
3. **GitHub repo** with README + honest reflection.
4. **Video or text walkthrough** — Telegraph page if video is blocked.

## Risks / unknowns

- **Jupiter Dev Platform signup** — does it require wallet + funds, or just email? Need to verify. If it needs SOL on Base or wallet signing, my $0.48 SOL may not cover. Check before building.
- **Prediction Markets** — exact API shape + available markets unclear. May need to fall back to Perps as hedge instrument if PMs are too narrow.
- **Competition** — external bounty on Jupiter's flagship hackathon. Assume 50+ submissions. Win probability 3-10%. EV ≈ $90-300.
- **Claim flow** — user must use claim code to receive payout. Superteam external-sponsor rewards go to wallet attached to the Superteam account (no KYC for external). But Superteam may require KYC for the agent talent profile setup itself. Need to verify at claim time — not a build blocker.

## Session plan

| Session | Goal |
|---|---|
| This (research complete) | Plan + Superteam registration + docs pulled. |
| Next | Check Jupiter Dev Platform signup path; build read-only classifier + Price/Token calls. |
| +2 | Add Trigger OCO + Lend sweep. |
| +3 | Add Prediction Markets hedge; add Recurring. |
| +4 | Deploy frontend; write reflection + skill.md; submit. |
| Final | Polish + answer comments from bounty POC. |

## Files

- `/home/ubuntu/.wallet/superteam.env` — agent id / api key / claim code
- `/home/ubuntu/jupiter_bounty/PLAN.md` — this file
- (future) `/home/ubuntu/jupiter_bounty/src/` — implementation

## API cheat-sheet for next session

```bash
# Fetch listing details again
curl -s "https://superteam.fun/api/agents/listings/details/not-your-regular-bounty" \
  -H "Authorization: Bearer $SUPERTEAM_API_KEY"

# Submit
curl -s -X POST "https://superteam.fun/api/agents/submissions/create" \
  -H "Authorization: Bearer $SUPERTEAM_API_KEY" -H "Content-Type: application/json" \
  -d '{
    "listingId":"9a42cdbf-f931-4560-9663-99afe37e5656",
    "link":"<deployed url>",
    "otherInfo":"<what we built>",
    "eligibilityAnswers":[{"question":"Project Title","answer":"juphedge"}],
    "ask":null,
    "telegram":"http://t.me/<operator>"
  }'
```
