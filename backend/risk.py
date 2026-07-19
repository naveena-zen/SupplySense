def classify_stockout_risk(
    current_stock: int,
    reorder_point: int,
    safety_stock: int,
    average_daily_demand: float,
    lead_time_days: int
) -> dict:
    """
    Classify the stockout risk of an item based on inventory levels and demand.
    Returns:
        dict: {
            "risk_level": "none" | "low" | "medium" | "high" | "critical",
            "days_to_stockout": float,
            "reason": str
        }
    """
    if current_stock <= 0:
        return {
            "risk_level": "critical",
            "days_to_stockout": 0.0,
            "reason": "Item is already out of stock."
        }
    
    if average_daily_demand <= 0:
        return {
            "risk_level": "none",
            "days_to_stockout": float("inf"),
            "reason": "No active daily demand."
        }
    
    days_to_stockout = current_stock / average_daily_demand
    
    if days_to_stockout <= 0.0:
        risk_level = "critical"
        reason = "Stock is completely depleted."
    elif days_to_stockout <= 3.0:
        risk_level = "critical"
        reason = f"Critical stock level: only {days_to_stockout:.1f} days of stock remaining."
    elif days_to_stockout <= lead_time_days:
        risk_level = "high"
        reason = f"High risk: stock will run out in {days_to_stockout:.1f} days, which is less than lead time ({lead_time_days} days)."
    elif current_stock <= safety_stock:
        risk_level = "high"
        reason = f"Stock level ({current_stock}) is below safety stock ({safety_stock})."
    elif current_stock <= reorder_point:
        risk_level = "medium"
        reason = f"Stock level ({current_stock}) is below reorder point ({reorder_point}). Order should be placed."
    elif days_to_stockout <= reorder_point / average_daily_demand:
        risk_level = "low"
        reason = f"Stock is healthy but approaching reorder threshold."
    else:
        risk_level = "none"
        reason = f"Stock levels are healthy ({days_to_stockout:.1f} days remaining)."
        
    return {
        "risk_level": risk_level,
        "days_to_stockout": round(days_to_stockout, 2),
        "reason": reason
    }


def score_supplier_risk(
    geopolitical_risk: float,
    financial_risk: float,
    historical_delay_rate: float
) -> float:
    """
    Calculate a supplier's risk score as a float from 0.0 (completely safe) to 1.0 (extremely risky).
    Uses a weighted average of geopolitical risk, financial risk, and historical delivery performance.
    """
    # Weights: 30% geopolitical, 40% financial, 30% performance (historical delays)
    w_geo = 0.3
    w_fin = 0.4
    w_perf = 0.3
    
    score = (w_geo * geopolitical_risk) + (w_fin * financial_risk) + (w_perf * historical_delay_rate)
    return round(max(0.0, min(1.0, score)), 2)


def calculate_delay_impact(
    quantity: int,
    average_daily_demand: float,
    current_stock: int,
    safety_stock: int,
    delay_days: int = 5
) -> dict:
    """
    Evaluate the impact of a shipment delay on stock levels at the destination warehouse.
    Returns:
        dict: {
            "impact_level": "low" | "medium" | "high" | "critical",
            "projected_shortage": float,
            "run_out_before_delivery": bool,
            "reason": str
        }
    """
    if average_daily_demand <= 0:
        return {
            "impact_level": "low",
            "projected_shortage": 0.0,
            "run_out_before_delivery": False,
            "reason": "No daily demand; delay has no stockout impact."
        }
        
    days_to_stockout = current_stock / average_daily_demand
    projected_shortage = max(0.0, (delay_days * average_daily_demand) - current_stock)
    
    run_out = days_to_stockout < delay_days
    
    if run_out:
        impact_level = "critical"
        reason = f"Critical impact: warehouse will run out of stock in {days_to_stockout:.1f} days, before the delayed shipment arrives (expected in {delay_days} days)."
    elif current_stock - (delay_days * average_daily_demand) <= safety_stock:
        impact_level = "high"
        reason = f"High impact: delay of {delay_days} days will deplete inventory below the safety stock buffer ({safety_stock} units)."
    elif current_stock - (delay_days * average_daily_demand) <= safety_stock * 1.5:
        impact_level = "medium"
        reason = f"Medium impact: delay of {delay_days} days will eat significantly into the safety stock buffer."
    else:
        impact_level = "low"
        reason = f"Low impact: current stock is sufficient to absorb a {delay_days}-day delay without dipping below safety thresholds."
        
    return {
        "impact_level": impact_level,
        "projected_shortage": round(projected_shortage, 2),
        "run_out_before_delivery": run_out,
        "reason": reason
    }
