import logging
from datetime import datetime
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from backend.models import Warehouse, Supplier, SKU, Shipment
from backend.risk import classify_stockout_risk, score_supplier_risk, calculate_delay_impact

logger = logging.getLogger(__name__)

def get_inventory_status(db: Session, sku_query: str = None) -> list:
    """
    Get inventory status for SKUs matching the query, or all SKUs if no query is provided.
    Includes calculated stockout risk classification and days to stockout.
    """
    query = db.query(SKU)
    if sku_query:
        query = query.filter(SKU.name.ilike(f"%{sku_query}%"))
    skus = query.all()

    result = []
    for k in skus:
        risk_details = classify_stockout_risk(
            current_stock=k.current_stock,
            reorder_point=k.reorder_point,
            safety_stock=k.safety_stock,
            average_daily_demand=k.average_daily_demand,
            lead_time_days=k.lead_time_days
        )
        result.append({
            "sku_id": k.id,
            "name": k.name,
            "category": k.category,
            "unit_price": k.unit_price,
            "current_stock": k.current_stock,
            "reorder_point": k.reorder_point,
            "safety_stock": k.safety_stock,
            "average_daily_demand": k.average_daily_demand,
            "lead_time_days": k.lead_time_days,
            "risk_level": risk_details["risk_level"],
            "days_to_stockout": risk_details["days_to_stockout"],
            "reason": risk_details["reason"]
        })
    return result


def get_supplier_risk(db: Session, supplier_query: str = None) -> list:
    """
    Get risk details for suppliers matching the query, or all suppliers.
    """
    query = db.query(Supplier)
    if supplier_query:
        query = query.filter(Supplier.name.ilike(f"%{supplier_query}%"))
    suppliers = query.all()

    result = []
    for s in suppliers:
        result.append({
            "supplier_id": s.id,
            "name": s.name,
            "category": s.category,
            "geopolitical_risk": s.geopolitical_risk,
            "financial_risk": s.financial_risk,
            "composite_risk_score": s.risk_score,
            "contact_email": s.contact_email
        })
    return result


def get_shipment_delays(db: Session) -> list:
    """
    Get all shipments that are currently delayed or pending past their estimated delivery date,
    along with their calculated stockout impact on the destination warehouse.
    """
    now = datetime.utcnow()
    # Filter shipments that are delayed, or pending/transit with estimated delivery date in the past
    delays = db.query(Shipment).filter(
        or_(
            Shipment.status == "delayed",
            and_(
                Shipment.status.in_(["transit", "pending"]),
                Shipment.estimated_delivery_date < now
            )
        )
    ).all()

    result = []
    for sh in delays:
        sku = db.query(SKU).filter(SKU.id == sh.sku_id).first()
        wh = db.query(Warehouse).filter(Warehouse.id == sh.destination_warehouse_id).first()
        
        delay_days = 5
        overdue = now - sh.estimated_delivery_date
        if overdue.days > 0:
            delay_days = overdue.days
            
        impact = {}
        if sku:
            impact = calculate_delay_impact(
                quantity=sh.quantity,
                average_daily_demand=sku.average_daily_demand,
                current_stock=sku.current_stock,
                safety_stock=sku.safety_stock,
                delay_days=delay_days
            )

        result.append({
            "shipment_id": sh.id,
            "sku_name": sku.name if sku else "Unknown",
            "quantity": sh.quantity,
            "status": sh.status,
            "supplier_name": sh.supplier.name if sh.supplier else "Unknown",
            "warehouse_name": wh.name if wh else "Unknown",
            "estimated_delivery_date": sh.estimated_delivery_date.strftime("%Y-%m-%d"),
            "days_overdue": max(0, overdue.days),
            "delay_impact_level": impact.get("impact_level", "low"),
            "projected_shortage": impact.get("projected_shortage", 0.0),
            "reason": impact.get("reason", "")
        })
    return result


def recommend_warehouse(db: Session, sku_id_or_name: str, quantity: int) -> dict:
    """
    Recommend a warehouse to receive a shipment of a specific SKU based on remaining capacity.
    Calculates current simulated load (sum of active shipment quantities routed to each warehouse)
    against max capacity.
    """
    # Find SKU
    sku = db.query(SKU).filter(
        or_(SKU.id == sku_id_or_name, SKU.name.ilike(f"%{sku_id_or_name}%"))
    ).first()
    
    if not sku:
        return {"error": f"SKU '{sku_id_or_name}' not found."}

    warehouses = db.query(Warehouse).all()
    recommendations = []

    for w in warehouses:
        # Calculate current active incoming shipment quantities for this warehouse
        incoming_qty = db.query(Shipment).filter(
            and_(
                Shipment.destination_warehouse_id == w.id,
                Shipment.status.in_(["transit", "pending", "delayed"])
            )
        ).all()
        current_load = sum(sh.quantity for sh in incoming_qty)
        
        available_capacity = w.max_capacity_units - current_load
        can_fit = available_capacity >= quantity
        
        recommendations.append({
            "warehouse_id": w.id,
            "name": w.name,
            "location": w.location,
            "max_capacity_units": w.max_capacity_units,
            "current_allocated_units": current_load,
            "available_capacity_units": available_capacity,
            "occupancy_rate": round((current_load / w.max_capacity_units) * 100, 1) if w.max_capacity_units > 0 else 100,
            "can_fit": can_fit
        })

    # Sort warehouses by available capacity descending (most empty first)
    recommendations.sort(key=lambda x: x["available_capacity_units"], reverse=True)
    
    best_recommendation = recommendations[0] if recommendations else None
    
    return {
        "sku_name": sku.name,
        "quantity_to_route": quantity,
        "best_warehouse_recommendation": best_recommendation["name"] if best_recommendation else "None",
        "warehouses_evaluation": recommendations
    }


def get_top_risks(db: Session, limit: int = 5) -> dict:
    """
    Returns a unified prioritized list of the top risk items in the supply chain:
    1. Critical/High Stockout SKUs
    2. High composite risk suppliers
    3. Severe delay impact shipments
    """
    # 1. Evaluate stockout risks
    skus = db.query(SKU).all()
    sku_risks = []
    for k in skus:
        risk_details = classify_stockout_risk(
            current_stock=k.current_stock,
            reorder_point=k.reorder_point,
            safety_stock=k.safety_stock,
            average_daily_demand=k.average_daily_demand,
            lead_time_days=k.lead_time_days
        )
        if risk_details["risk_level"] in ["critical", "high"]:
            sku_risks.append({
                "type": "SKU_STOCKOUT_RISK",
                "severity": risk_details["risk_level"],
                "subject": k.name,
                "subject_id": k.id,
                "detail": risk_details["reason"]
            })
            
    # 2. Evaluate high-risk suppliers (risk_score >= 0.45)
    suppliers = db.query(Supplier).filter(Supplier.risk_score >= 0.45).all()
    supplier_risks = []
    for s in suppliers:
        supplier_risks.append({
            "type": "SUPPLIER_RISK",
            "severity": "high" if s.risk_score < 0.65 else "critical",
            "subject": s.name,
            "subject_id": s.id,
            "detail": f"Supplier composite risk is {s.risk_score:.2f} (geopolitical: {s.geopolitical_risk:.2f}, financial: {s.financial_risk:.2f})"
        })

    # 3. Evaluate shipment delays
    del_shipments = get_shipment_delays(db)
    shipment_risks = []
    for sh in del_shipments:
        if sh["delay_impact_level"] in ["critical", "high"]:
            shipment_risks.append({
                "type": "SHIPMENT_DELAY_RISK",
                "severity": sh["delay_impact_level"],
                "subject": f"Shipment of {sh['quantity']}x {sh['sku_name']} from {sh['supplier_name']}",
                "subject_id": sh["shipment_id"],
                "detail": f"Overdue by {sh['days_overdue']} days. Destination: {sh['warehouse_name']}. {sh['reason']}"
            })

    # Merge and prioritize
    all_risks = sku_risks + supplier_risks + shipment_risks
    
    # Sort: critical first, then high
    def severity_rank(r):
        return 0 if r["severity"] == "critical" else 1

    all_risks.sort(key=severity_rank)
    
    return {
        "total_risks_found": len(all_risks),
        "top_risks": all_risks[:limit]
    }


def suggest_alternate_supplier(db: Session, sku_id_or_name: str) -> dict:
    """
    Find alternate suppliers for a given SKU's category, sorted by lowest risk score (safest first).
    """
    sku = db.query(SKU).filter(
        or_(SKU.id == sku_id_or_name, SKU.name.ilike(f"%{sku_id_or_name}%"))
    ).first()
    
    if not sku:
        return {"error": f"SKU '{sku_id_or_name}' not found."}
        
    category = sku.category
    
    # Find all suppliers of that category
    alternates = db.query(Supplier).filter(Supplier.category == category).all()
    
    results = []
    for s in alternates:
        results.append({
            "supplier_id": s.id,
            "name": s.name,
            "category": s.category,
            "composite_risk_score": s.risk_score,
            "geopolitical_risk": s.geopolitical_risk,
            "financial_risk": s.financial_risk
        })
        
    # Sort by risk score ascending (safest first)
    results.sort(key=lambda x: x["composite_risk_score"])
    
    return {
        "sku_name": sku.name,
        "sku_category": category,
        "current_stock": sku.current_stock,
        "suggested_suppliers": results
    }
