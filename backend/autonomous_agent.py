import json
import logging
import re
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models import Warehouse, Supplier, SKU, Shipment, AgentRun, AgentDecision
from backend.risk import classify_stockout_risk, calculate_delay_impact
from backend.llm import call_llm

logger = logging.getLogger(__name__)

def build_snapshot_context(db: Session) -> dict:
    """
    Query the database to build a highly compact structured representation of the current supply chain state,
    excluding delivered shipments and stripping verbose fields to prevent token rate limits.
    """
    warehouses = db.query(Warehouse).all()
    suppliers = db.query(Supplier).all()
    skus = db.query(SKU).all()
    shipments = db.query(Shipment).filter(Shipment.status != "delivered").all()

    # Format Warehouses
    wh_list = []
    for w in warehouses:
        wh_list.append({
            "id": w.id,
            "name": w.name,
            "max_units": w.max_capacity_units
        })

    # Format Suppliers
    supp_list = []
    for s in suppliers:
        supp_list.append({
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "risk_score": s.risk_score
        })

    # Format SKUs (only include at-risk SKUs)
    sku_list = []
    for k in skus:
        risk_details = classify_stockout_risk(
            current_stock=k.current_stock,
            reorder_point=k.reorder_point,
            safety_stock=k.safety_stock,
            average_daily_demand=k.average_daily_demand,
            lead_time_days=k.lead_time_days
        )
        if risk_details["risk_level"] == "none":
            continue
        sku_list.append({
            "id": k.id,
            "name": k.name,
            "category": k.category,
            "stock": k.current_stock,
            "reorder": k.reorder_point,
            "safety": k.safety_stock,
            "demand": k.average_daily_demand,
            "lead_time": k.lead_time_days,
            "risk": risk_details["risk_level"],
            "days_left": risk_details["days_to_stockout"]
        })

    # Format Active Shipments
    ship_list = []
    for sh in shipments:
        sku = db.query(SKU).filter(SKU.id == sh.sku_id).first()
        
        delay_analysis = {}
        if sku:
            days_overdue = 5
            if sh.status == "delayed":
                overdue = datetime.utcnow() - sh.estimated_delivery_date
                days_overdue = max(1, overdue.days)
                
            delay_analysis = calculate_delay_impact(
                quantity=sh.quantity,
                average_daily_demand=sku.average_daily_demand,
                current_stock=sku.current_stock,
                safety_stock=sku.safety_stock,
                delay_days=days_overdue
            )

        ship_list.append({
            "id": sh.id,
            "sku_name": sku.name if sku else "Unknown",
            "sku_id": sh.sku_id,
            "supplier_name": sh.supplier.name if sh.supplier else "Unknown",
            "supplier_id": sh.supplier_id,
            "qty": sh.quantity,
            "status": sh.status,
            "est_delivery": sh.estimated_delivery_date.strftime("%Y-%m-%d"),
            "delay_impact": delay_analysis.get("impact_level", "none")
        })

    return {
        "warehouses": wh_list,
        "suppliers": supp_list,
        "skus": sku_list,
        "active_shipments": ship_list
    }

SYSTEM_PROMPT = """You are an expert AI Autonomous Supply Chain Monitor and Ops Analyst.
Your task is to analyze the complete, real-time snapshot of the supply chain state and identify operational risks, stockout warnings, supplier red flags, and shipping delays.

You MUST reason over the actual numbers provided:
- Identify SKUs with critical stockout risks (e.g. days_to_stockout is very low).
- Identify suppliers with high risk scores or severe financial/geopolitical vulnerabilities.
- Identify delayed shipments that have a high/critical impact on warehouse stock levels.
- Formulate concrete, actionable recommendations (e.g. re-ordering from specific alternate suppliers of the same category, re-routing shipments, or requesting expedited shipping).

You must return a STRICT JSON list of decisions.
DO NOT wrap the response in markdown code blocks (e.g. do NOT use ```json). Return ONLY raw JSON text.
Each decision in the list must exactly follow this schema:
[
  {
    "decision_type": "stockout_risk" | "supplier_warning" | "shipment_delay" | "restock_recommendation",
    "severity": "low" | "medium" | "high" | "critical",
    "subject_id": "<ID of the SKU, Supplier, or Shipment affected>",
    "reasoning": {
      "metric_cited": "<CITE REAL NUMBERS FROM THE DATA: e.g. 'Current stock is 5 units, average demand is 1.2 units/day, leaving 4.2 days of stock. Lead time is 20 days.'>",
      "impact": "<Specific downstream business or manufacturing impact of this issue>",
      "context": "<Detailed analysis of what caused this issue>"
    },
    "recommended_action": "<A specific, concrete mitigation plan. For stockout_risk, specify which alternate supplier in the same category can fulfill a restock, and recommend a quantity. Cite real names.>"
  }
]
"""

async def run_autonomous_monitor(db: Session) -> str:
    """
    Executes the autonomous monitor agent:
    1. Creates a running AgentRun record.
    2. Snapshots database state.
    3. Prompts LLM for decisions.
    4. Parses, validates, and persists decisions.
    5. Updates AgentRun to successful/failed.
    Returns:
        str: The run ID.
    """
    # Create the run record
    run = AgentRun(
        run_type="autonomous",
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(run)
    db.commit()
    
    try:
        # Snapshot full state
        state = build_snapshot_context(db)
        user_prompt = f"Here is the complete supply chain state snapshot:\n\n{json.dumps(state, indent=2)}"
        
        # Call the LLM
        response_text = await call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True
        )
        
        # Handle LLM wrapped in markdown code blocks if any
        cleaned_response = response_text.strip()
        if cleaned_response.startswith("```"):
            # strip off ```json and ```
            cleaned_response = re.sub(r"^```(?:json)?\n", "", cleaned_response)
            cleaned_response = re.sub(r"\n```$", "", cleaned_response)
            cleaned_response = cleaned_response.strip()

        # Parse decisions
        decisions_json = json.loads(cleaned_response)
        if not isinstance(decisions_json, list):
            raise ValueError("LLM response is not a JSON list of decisions.")

        persisted_decisions_count = 0
        for item in decisions_json:
            # Validate required fields
            req_fields = ["decision_type", "severity", "subject_id", "reasoning", "recommended_action"]
            if not all(field in item for field in req_fields):
                logger.warning(f"Skipping malformed LLM decision object: {item}")
                continue
                
            decision = AgentDecision(
                run_id=run.id,
                decision_type=item["decision_type"],
                severity=item["severity"],
                subject_id=item["subject_id"],
                reasoning=item["reasoning"],
                recommended_action=item["recommended_action"],
                created_at=datetime.utcnow()
            )
            db.add(decision)
            persisted_decisions_count += 1
            
        run.status = "success"
        run.completed_at = datetime.utcnow()
        run.summary = f"Completed successfully. Identified and persisted {persisted_decisions_count} supply chain decisions."
        db.commit()
        
        print(f"Autonomous monitor run {run.id} complete. Persisted {persisted_decisions_count} decisions.")
        return run.id
        
    except Exception as e:
        logger.exception("Error executing autonomous monitor agent")
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.summary = f"Failed with error: {str(e)}"
        db.commit()
        raise e
