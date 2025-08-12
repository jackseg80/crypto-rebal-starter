from fastapi import FastAPI, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from connectors.cointracking import get_current_balances
from engine.plan import build_plan
from connectors.cointracking import ct_raw,  get_current_balances
from api.taxonomy import Taxonomy

STABLES = {"USDT","USDC","FDUSD","TUSD","DAI","EURT","USDCE","USDBC","BUSD","FDUSD","EUR","USD","UST","USTC"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status":"ok"}

class Target(BaseModel):
    symbol: str
    target_weight: float = Field(..., ge=0.0, le=1.0)

class Constraints(BaseModel):
    min_trade_usd: float = 25.0
    fee_bps: float = 10.0

class PlanRequest(BaseModel):
    source: str = "stub"            # stub|csv|cointracking
    csv_current: Optional[str] = None
    csv_by_exchange: Optional[str] = None
    targets: List[Target]
    constraints: Constraints = Constraints()

@app.get("/balances/current")
async def balances_current(
    source: str = Query("stub", pattern="^(stub|csv|cointracking)$"),
    min_usd: float = Query(1.0, ge=0),
    alias: str = Query("safe", pattern="^(none|safe|wrappers|all)$")
):
    data = await get_current_balances(source=source, min_usd=min_usd, alias_mode=alias)
    return {"source": source, "items": data}

@app.post("/balances/current")
async def balances_current_post(body: Dict[str, Any] = Body(...)):
    source = body.get("source", "stub")
    csv_current = body.get("csv_current")
    csv_by_exchange = body.get("csv_by_exchange")
    min_usd = float(body.get("min_usd", 1.0))
    alias = body.get("alias", "safe")  # "none"|"safe"|"wrappers"|"all"
    data = await get_current_balances(source=source,
                                      csv_current=csv_current,
                                      csv_by_exchange=csv_by_exchange,
                                      min_usd=min_usd,
                                      alias_mode=alias)
    return {"source": source, "items": data}

@app.post("/rebalance/plan")
async def rebalance_plan(req: PlanRequest):
    balances = await get_current_balances(
        source=req.source, csv_current=req.csv_current, csv_by_exchange=req.csv_by_exchange
    )
    plan = build_plan(balances, [t.model_dump() for t in req.targets], req.constraints.model_dump())
    return plan

@app.get("/debug/env")
def debug_env():
    import os
    return {
        "ct_key_present": bool(os.getenv("COINTRACKING_KEY")),
        "ct_secret_present": bool(os.getenv("COINTRACKING_SECRET"))
    }

@app.get("/debug/ct/raw")
async def debug_ct_raw(method: str = "getBalance"):
    return await ct_raw(method)

@app.get("/portfolio/summary")
async def portfolio_summary(
    source: str = Query("cointracking", pattern="^(stub|csv|cointracking)$"),
    min_usd: float = Query(1.0, ge=0),
    alias: str = Query("safe", pattern="^(none|safe|wrappers|all)$"),
    top_n: int = Query(10, ge=1, le=100)
):
    items = await get_current_balances(source=source, min_usd=min_usd, alias_mode=alias)
    total = sum(x["usd_value"] for x in items) or 0.0
    out = []
    for x in items:
        w = (x["usd_value"] / total) * 100 if total else 0.0
        out.append({**x, "weight_pct": round(w, 4), "is_stable": x["symbol"] in STABLES})
    out.sort(key=lambda r: r["usd_value"], reverse=True)

    stables_total = sum(x["usd_value"] for x in out if x["is_stable"])
    nonstables_total = total - stables_total

    return {
        "total_usd": round(total, 2),
        "n_positions": len(out),
        "stables_total_usd": round(stables_total, 2),
        "nonstables_total_usd": round(nonstables_total, 2),
        "top": out[:top_n],
        "items": out  # complet si tu veux tout afficher côté front
    }
    
# --- DEBUG SNAPSHOT ----------------------------------------------------------
@app.get("/debug/snapshot")
async def debug_snapshot(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0, ge=0.0),
):
    """
    Retourne l’agrégat par groupes + alias pour inspection.
    """
    rows = await get_current_balances(source=source)
    taxo = Taxonomy()
    snap = taxo.aggregate(rows, min_usd=min_usd)
    return {
        "source": source,
        "min_usd": min_usd,
        **snap
    }