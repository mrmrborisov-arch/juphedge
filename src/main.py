"""juphedge — one-command Solana portfolio hedger.

FastAPI entrypoint. Reads a Solana wallet, composes 5+ Jupiter APIs
(Price + Tokens + Trigger + Lend + Recurring + Prediction), and returns
a structured hedge plan.

Submission to Superteam Earn x Jupiter "Not Your Regular Bounty".
"""
from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from . import analyzer, jupiter

app = FastAPI(
    title="juphedge",
    description=(
        "Solana portfolio hedger. Composes Jupiter Price + Tokens + Trigger + "
        "Lend + Recurring + Prediction APIs into a single hedge plan. "
        "Prediction Markets used as an insurance leg, not as speculation — "
        "that's the weird combo."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/api/analyze")
def analyze_endpoint(wallet: str = Query(..., min_length=32, max_length=44)) -> JSONResponse:
    try:
        plan = analyzer.analyze(wallet)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))

    # Dataclass -> dict, positions included
    return JSONResponse(
        {
            "wallet": plan.wallet,
            "total_usd": round(plan.total_usd, 4),
            "idle_stable_usd": round(plan.idle_stable_usd, 4),
            "positions": [asdict(p) for p in plan.positions],
            "trigger_orders": plan.trigger_orders,
            "lend_sweep": plan.lend_sweep,
            "dca_plan": plan.dca_plan,
            "prediction_hedge": plan.prediction_hedge,
            "trace": plan.trace,
            "jupiter_apis_used": [
                "Price v3",
                "Tokens v2",
                "Trigger v2 (plan only)",
                "Lend v1 (plan only)",
                "Recurring v1 (plan only)",
                "Prediction v1 (plan only)",
                "Solana RPC (read-only wallet scan)",
            ],
            "meta": {
                "note": "This endpoint only returns a PLAN. No transactions are signed. "
                        "An agent consumer calls the corresponding Jupiter endpoints "
                        "with its own signer to execute.",
            },
        }
    )


@app.get("/api/markets")
def markets_endpoint(category: str = "crypto", limit: int = 20) -> JSONResponse:
    evs = jupiter.prediction_events(category, limit)
    return JSONResponse(evs)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


INDEX_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>juphedge — Solana portfolio hedger</title>
<style>
  body{font-family:-apple-system,Segoe UI,Inter,sans-serif;margin:0;background:#0b0b10;color:#eceef2;line-height:1.5}
  main{max-width:960px;margin:0 auto;padding:32px 24px}
  h1{font-weight:600;font-size:26px;margin:0 0 6px}
  h1 span{background:linear-gradient(135deg,#f5c25e,#e06c4f);-webkit-background-clip:text;color:transparent;font-weight:700}
  p.sub{color:#9aa0ac;margin:0 0 24px}
  .card{background:#15161d;border:1px solid #232530;border-radius:10px;padding:16px 18px;margin-bottom:14px}
  .row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  input{flex:1;min-width:320px;padding:10px 12px;font-family:ui-monospace,Menlo,monospace;background:#0b0b10;border:1px solid #2a2c37;color:#eceef2;border-radius:6px}
  button{padding:10px 18px;background:#f5c25e;color:#0b0b10;border:0;border-radius:6px;font-weight:600;cursor:pointer}
  button:disabled{opacity:.5;cursor:wait}
  pre{background:#07070c;color:#b9bdc8;padding:12px;border-radius:6px;overflow:auto;font-size:12.5px;max-height:640px;white-space:pre-wrap}
  .kpi{display:inline-block;margin-right:18px;font-size:14px}
  .kpi b{font-size:18px;color:#f5c25e}
  .trace{color:#6f7382;font-size:12px;font-family:ui-monospace,Menlo,monospace;white-space:pre-wrap;margin-top:10px}
  a{color:#f5c25e}
  .tag{display:inline-block;padding:2px 8px;font-size:11px;border-radius:4px;background:#232530;color:#b9bdc8;margin-right:4px}
  .hedge{border-left:3px solid #e06c4f}
  code{background:#232530;padding:2px 4px;border-radius:3px;font-size:12px}
  .footnote{color:#6f7382;font-size:12px;margin-top:24px}
</style></head>
<body>
<main>
<h1><span>juphedge</span> &nbsp; solana portfolio hedger</h1>
<p class="sub">One read-only endpoint composes five+ Jupiter APIs into a structured hedge plan.
Prediction Markets are used as an <b>insurance leg</b>, not as speculation —
the combination Jupiter did not explicitly design for.</p>

<div class="card">
  <div class="row">
    <input id="w" placeholder="Solana wallet address" value="3peKKmQYfYCtnLDci8aDqadmjEFArtLuijEBR9ceoWPz">
    <button id="go">Scan &amp; hedge</button>
  </div>
</div>

<div id="out" class="card" style="display:none"></div>

<p class="footnote">
  Backend: <a href="/docs">OpenAPI</a>. Source &amp; design notes: <a href="https://github.com/mrmrborisov-arch/juphedge">github</a>.
  Jupiter APIs used: Price v3, Tokens v2, Trigger v2, Lend v1, Recurring v1, Prediction v1.
  No transactions are signed by this service — an agent consumer executes plan items.
</p>

<script>
const go=document.getElementById("go"), out=document.getElementById("out"), w=document.getElementById("w");
go.onclick=async()=>{
  go.disabled=true; out.style.display="block"; out.innerHTML="<div class='trace'>Scanning…</div>";
  try{
    const r=await fetch("/api/analyze?wallet="+encodeURIComponent(w.value));
    const d=await r.json();
    if(!r.ok){ out.innerHTML="<pre>"+JSON.stringify(d,null,2)+"</pre>"; return; }
    render(d);
  }catch(e){ out.innerHTML="<pre>"+e.message+"</pre>"; }
  finally{ go.disabled=false; }
};

function render(d){
  const parts=[];
  parts.push(`<div class='kpi'>Total <b>$${d.total_usd.toFixed(2)}</b></div>
             <div class='kpi'>Idle stable <b>$${d.idle_stable_usd.toFixed(2)}</b></div>
             <div class='kpi'>Positions <b>${d.positions.length}</b></div>`);

  if(d.positions.length){
    parts.push("<h3>Positions</h3><pre>"+
      d.positions.map(p=>`${(p.symbol||'').padEnd(8)} ${String(p.amount).padStart(14)} × $${p.usd_price.toFixed(6)} = $${p.usd_value.toFixed(2)}  [${p.classification}]  Δ24h ${p.change_24h.toFixed(2)}%`).join("\\n")+"</pre>");
  }

  if(d.trigger_orders.length){
    parts.push("<h3>1. Trigger OCO bands (<code>POST /trigger/v2/orders/price</code>)</h3><pre>"+
      d.trigger_orders.map(o=>`${(o.symbol||'').padEnd(8)} entry $${o.entry_price_usd.toFixed(6)}  TP $${o.take_profit_usd.toFixed(6)}  SL $${o.stop_loss_usd.toFixed(6)}  (${o.why})`).join("\\n")+"</pre>");
  }

  if(d.lend_sweep){
    const y = d.lend_sweep.projected_annual_yield_usd;
    parts.push("<h3>2. Lend sweep (<code>POST /lend/v1/earn/deposit</code>)</h3><pre>"+
      `Deposit $${d.lend_sweep.amount_usd.toFixed(2)} of idle ${d.lend_sweep.target.asset} at ${d.lend_sweep.target.apy ?? '?'}% APY. ` +
      (y!=null ? `Est. annual yield: $${y.toFixed(2)}.` : "(APY unavailable keyless)")+"</pre>");
  }

  if(d.dca_plan){
    parts.push("<h3>3. Recurring trim (<code>POST /recurring/v1/createOrder</code>)</h3><pre>"+
      `Sell ${d.dca_plan.symbol} -> ${d.dca_plan.output} in $${d.dca_plan.chunk_usd} chunks every ${d.dca_plan.interval_hours}h × ${d.dca_plan.cycles} cycles.\\n${d.dca_plan.why}`+"</pre>");
  }

  if(d.prediction_hedge){
    const h=d.prediction_hedge;
    parts.push(`<div class="card hedge"><h3>4. Prediction-Market hedge <span class="tag">the weird one</span></h3>
      <div>Spot bet: <b>${h.spot_symbol}</b> = $${h.spot_usd.toFixed(2)}</div>
      <div>Market: <b>${h.market.event_title}</b> → <b>${h.market.market_title}</b></div>
      <div>Buy <b>${h.suggested_contracts}</b> <b>${h.market.side}</b> contracts @ $${h.market.price_usd.toFixed(4)} each</div>
      <div>Cost: <b>$${h.cost_usd}</b>. Payout if event misses target: <b>$${h.payout_if_correct_usd}</b></div>
      <div style="margin-top:6px;color:#9aa0ac">${h.why}</div>
      <div style="margin-top:6px"><code>${h.endpoint}</code></div>
    </div>`);
  }
  parts.push("<h3>API trace</h3><div class='trace'>"+d.trace.join("\\n")+"</div>");
  parts.push("<details><summary>Raw JSON</summary><pre>"+JSON.stringify(d,null,2)+"</pre></details>");
  out.innerHTML = parts.join("");
}
</script>
</main>
</body></html>
"""
