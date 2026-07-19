from backend.risk import classify_stockout_risk, score_supplier_risk, calculate_delay_impact

def test_classify_stockout_risk():
    # 1. Out of stock / depleted
    res = classify_stockout_risk(
        current_stock=0,
        reorder_point=50,
        safety_stock=20,
        average_daily_demand=5.0,
        lead_time_days=10
    )
    assert res["risk_level"] == "critical"
    assert res["days_to_stockout"] == 0.0

    # 2. Critical level (<= 3 days left)
    res = classify_stockout_risk(
        current_stock=10,
        reorder_point=50,
        safety_stock=20,
        average_daily_demand=5.0,
        lead_time_days=10
    )
    assert res["risk_level"] == "critical"
    assert res["days_to_stockout"] == 2.0

    # 3. High risk (< lead time days)
    res = classify_stockout_risk(
        current_stock=35,
        reorder_point=50,
        safety_stock=20,
        average_daily_demand=5.0,
        lead_time_days=10
    )
    assert res["risk_level"] == "high"
    assert res["days_to_stockout"] == 7.0

    # 4. High risk (below safety stock but not critical)
    res = classify_stockout_risk(
        current_stock=18,
        reorder_point=50,
        safety_stock=20,
        average_daily_demand=1.0,
        lead_time_days=10
    )
    assert res["risk_level"] == "high"
    assert "safety stock" in res["reason"]

    # 5. Medium risk (below reorder point)
    res = classify_stockout_risk(
        current_stock=40,
        reorder_point=50,
        safety_stock=20,
        average_daily_demand=1.0,
        lead_time_days=10
    )
    assert res["risk_level"] == "medium"
    assert "reorder point" in res["reason"]

    # 6. Healthy stock
    res = classify_stockout_risk(
        current_stock=100,
        reorder_point=50,
        safety_stock=20,
        average_daily_demand=2.0,
        lead_time_days=10
    )
    assert res["risk_level"] == "none"
    assert res["days_to_stockout"] == 50.0


def test_score_supplier_risk():
    # Weights: 0.3 * geo + 0.4 * fin + 0.3 * delay
    # Geo = 0.5, Fin = 0.8, Delay = 0.2
    # Score = 0.3*0.5 + 0.4*0.8 + 0.3*0.2 = 0.15 + 0.32 + 0.06 = 0.53
    score = score_supplier_risk(0.5, 0.8, 0.2)
    assert score == 0.53

    # Boundary checks
    assert score_supplier_risk(0.0, 0.0, 0.0) == 0.0
    assert score_supplier_risk(1.0, 1.0, 1.0) == 1.0


def test_calculate_delay_impact():
    # 1. Run out of stock before delivery (critical)
    # Current stock = 10, demand = 5, delay = 5 days.
    # Stock runs out in 2 days.
    res = calculate_delay_impact(
        quantity=100,
        average_daily_demand=5.0,
        current_stock=10,
        safety_stock=20,
        delay_days=5
    )
    assert res["impact_level"] == "critical"
    assert res["run_out_before_delivery"] is True
    assert res["projected_shortage"] == 15.0  # 5*5 - 10 = 15

    # 2. Dip below safety stock (high)
    # Current stock = 40, demand = 5, safety = 20, delay = 5 days.
    # Remaining stock after delay = 40 - 25 = 15 (which is <= safety_stock of 20).
    res = calculate_delay_impact(
        quantity=100,
        average_daily_demand=5.0,
        current_stock=40,
        safety_stock=20,
        delay_days=5
    )
    assert res["impact_level"] == "high"
    assert res["run_out_before_delivery"] is False

    # 3. Healthy/Low impact
    # Current stock = 100, demand = 5, safety = 20, delay = 5 days.
    # Remaining = 100 - 25 = 75 (which is > safety_stock * 1.5 of 30).
    res = calculate_delay_impact(
        quantity=100,
        average_daily_demand=5.0,
        current_stock=100,
        safety_stock=20,
        delay_days=5
    )
    assert res["impact_level"] == "low"
    assert res["run_out_before_delivery"] is False
