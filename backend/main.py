import logging
import json
import asyncio
import threading
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import engine, Base, get_db, SessionLocal
from backend.models import AgentRun, AgentDecision, SKU, Supplier, Shipment
from backend.autonomous_agent import run_autonomous_monitor, build_snapshot_context
from backend.reactive_agent import run_reactive_agent
from backend.llm import call_llm
from backend import tools

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backend.main")

# Initialize FastAPI app
app = FastAPI(title="SupplySense API", description="AI Supply Chain Risk & Inventory Intelligence API")

import os

# Add CORS middleware for frontend communication
frontend_url = os.getenv("FRONTEND_URL")
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if frontend_url:
    if "," in frontend_url:
        origins.extend([o.strip() for o in frontend_url.split(",")])
    else:
        origins.append(frontend_url)
else:
    origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

def run_background_monitor():
    logger.info("Starting background scheduler autonomous monitor job...")
    db = SessionLocal()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_autonomous_monitor(db))
        loop.close()
    except Exception as e:
        logger.error(f"Scheduled autonomous monitor run failed: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    # Start the scheduler — run every 60 min to avoid exhausting free-tier TPM quota
    scheduler.add_job(run_background_monitor, 'interval', minutes=60)
    scheduler.start()
    logger.info("APScheduler background scheduler started (60-min interval).")

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logger.info("APScheduler background scheduler shut down.")

# Request models
class QuestionRequest(BaseModel):
    question: str

class SuggestAlternateRequest(BaseModel):
    sku_id_or_name: str

# API Routes
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/dashboard-summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Fetch KPI numbers for the dashboard cards."""
    try:
        total_skus = db.query(SKU).count()
        total_suppliers = db.query(Supplier).count()
        
        # Calculate at-risk SKUs
        skus = db.query(SKU).all()
        at_risk_skus_count = 0
        for k in skus:
            # Reuse the pure classification function
            from backend.risk import classify_stockout_risk
            risk_details = classify_stockout_risk(
                current_stock=k.current_stock,
                reorder_point=k.reorder_point,
                safety_stock=k.safety_stock,
                average_daily_demand=k.average_daily_demand,
                lead_time_days=k.lead_time_days
            )
            if risk_details["risk_level"] in ["critical", "high"]:
                at_risk_skus_count += 1
                
        # Active delayed shipments
        from backend.tools import get_shipment_delays
        delays = get_shipment_delays(db)
        delayed_shipments_count = len(delays)
        
        # Active decisions
        active_decisions = db.query(AgentDecision).order_by(AgentDecision.created_at.desc()).limit(15).all()
        
        # Latest run status
        latest_run = db.query(AgentRun).order_by(AgentRun.started_at.desc()).first()
        
        return {
            "total_skus": total_skus,
            "total_suppliers": total_suppliers,
            "at_risk_skus": at_risk_skus_count,
            "delayed_shipments": delayed_shipments_count,
            "latest_run_status": latest_run.status if latest_run else "N/A",
            "latest_run_time": latest_run.started_at.isoformat() if latest_run else None,
            "decisions_count": len(active_decisions)
        }
    except Exception as e:
        logger.exception("Error loading dashboard summary")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inventory-risk")
def get_inventory_risk(q: str = Query(None), db: Session = Depends(get_db)):
    """Expose SKU inventory and stockout risk classifications."""
    try:
        return tools.get_inventory_status(db, sku_query=q)
    except Exception as e:
        logger.exception("Error in /inventory-risk")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/suppliers")
def get_suppliers(q: str = Query(None), db: Session = Depends(get_db)):
    """List suppliers and their composite risk metrics."""
    try:
        return tools.get_supplier_risk(db, supplier_query=q)
    except Exception as e:
        logger.exception("Error in /suppliers")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/suppliers/suggest-alternate")
def suggest_alternate_supplier(req: SuggestAlternateRequest, db: Session = Depends(get_db)):
    """Suggest alternate suppliers for a given SKU category sorted by risk safety."""
    try:
        res = tools.suggest_alternate_supplier(db, sku_id_or_name=req.sku_id_or_name)
        if "error" in res:
            raise HTTPException(status_code=404, detail=res["error"])
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /suppliers/suggest-alternate")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/shipments/delays")
def get_shipments_delays(db: Session = Depends(get_db)):
    """Get active shipment delays and their calculated stockout impact."""
    try:
        return tools.get_shipment_delays(db)
    except Exception as e:
        logger.exception("Error in /shipments/delays")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/ask")
async def ask_agent(req: QuestionRequest, db: Session = Depends(get_db)):
    """Ask a question to the Reactive Agent loop."""
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        res = await run_reactive_agent(db, req.question)
        return res
    except Exception as e:
        logger.exception("Error in /agent/ask")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/monitor/run")
async def trigger_monitor_run(db: Session = Depends(get_db)):
    """Manually trigger a run of the Autonomous Monitor Agent."""
    try:
        run_id = await run_autonomous_monitor(db)
        return {"status": "success", "run_id": run_id}
    except Exception as e:
        logger.exception("Error manually triggering monitor run")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/monitor/decisions")
def get_monitor_decisions(db: Session = Depends(get_db)):
    """Fetch past decisions made by the Autonomous Monitor Agent."""
    try:
        decisions = db.query(AgentDecision).order_by(AgentDecision.created_at.desc()).all()
        # Format dates and return
        result = []
        for d in decisions:
            # Try to fetch SKU/Supplier name for subject_id if possible
            subject_name = "Unknown"
            sku = db.query(SKU).filter(SKU.id == d.subject_id).first()
            if sku:
                subject_name = sku.name
            else:
                supp = db.query(Supplier).filter(Supplier.id == d.subject_id).first()
                if supp:
                    subject_name = supp.name
                else:
                    ship = db.query(Shipment).filter(Shipment.id == d.subject_id).first()
                    if ship:
                        ship_sku = db.query(SKU).filter(SKU.id == ship.sku_id).first()
                        subject_name = f"Shipment ({ship_sku.name if ship_sku else 'ID: ' + ship.id})"
            
            result.append({
                "id": d.id,
                "run_id": d.run_id,
                "decision_type": d.decision_type,
                "severity": d.severity,
                "subject_id": d.subject_id,
                "subject_name": subject_name,
                "reasoning": d.reasoning,
                "recommended_action": d.recommended_action,
                "created_at": d.created_at.isoformat()
            })
        return result
    except Exception as e:
        logger.exception("Error in /agent/monitor/decisions")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/monitor/runs")
def get_monitor_runs(db: Session = Depends(get_db)):
    """Fetch the history of autonomous monitor runs."""
    try:
        runs = db.query(AgentRun).filter(AgentRun.run_type == "autonomous").order_by(AgentRun.started_at.desc()).all()
        result = []
        for r in runs:
            result.append({
                "id": r.id,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "summary": r.summary
            })
        return result
    except Exception as e:
        logger.exception("Error in /agent/monitor/runs")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/exec-summary")
async def generate_exec_summary(db: Session = Depends(get_db)):
    """Generate a high-level executive text summary of the current supply chain state."""
    try:
        state = build_snapshot_context(db)

        # Trim to top 5 highest-risk SKUs and top 5 shipments to stay under free-tier TPM limits
        skus_sorted = sorted(state.get("skus", []), key=lambda x: x.get("days_left") or 999)[:5]
        ships_sorted = state.get("active_shipments", [])[:5]
        compact_state = {
            "warehouses": state.get("warehouses", []),
            "suppliers": state.get("suppliers", [])[:8],
            "skus": skus_sorted,
            "active_shipments": ships_sorted,
        }

        system_prompt = (
            "You are an AI Supply Chain Executive. "
            "Review this supply chain snapshot and write a concise 2-paragraph executive summary. "
            "Highlight the top risks, delayed shipments, and critical stockout SKUs with real figures. "
            "Be direct and professional. No markdown headers."
        )
        user_prompt = f"Supply chain state:\n{json.dumps(compact_state)}"

        summary_text = await call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False
        )

        return {"summary": summary_text}
    except Exception as e:
        logger.exception("Error generating executive summary")
        raise HTTPException(status_code=500, detail=str(e))
