from backend.database import SessionLocal
from backend.tools import (
    get_inventory_status,
    get_supplier_risk,
    get_shipment_delays,
    recommend_warehouse,
    get_top_risks,
    suggest_alternate_supplier
)

def test_database_tools():
    db = SessionLocal()
    try:
        # 1. Test get_inventory_status
        inv = get_inventory_status(db)
        assert len(inv) > 0
        # Search check
        inv_filtered = get_inventory_status(db, sku_query="MCU")
        assert len(inv_filtered) > 0
        assert any("MCU" in k["name"] for k in inv_filtered)

        # 2. Test get_supplier_risk
        suppliers = get_supplier_risk(db)
        assert len(suppliers) == 15
        
        # 3. Test get_shipment_delays
        delays = get_shipment_delays(db)
        assert isinstance(delays, list)
        
        # 4. Test recommend_warehouse
        recommend = recommend_warehouse(db, sku_id_or_name="MCU-32-Core", quantity=100)
        assert "sku_name" in recommend
        assert recommend["sku_name"] == "MCU-32-Core"
        assert len(recommend["warehouses_evaluation"]) == 6
        
        # 5. Test get_top_risks
        risks = get_top_risks(db, limit=3)
        assert "top_risks" in risks
        assert len(risks["top_risks"]) <= 3
        
        # 6. Test suggest_alternate_supplier
        alternates = suggest_alternate_supplier(db, sku_id_or_name="MCU-32-Core")
        assert "sku_name" in alternates
        assert alternates["sku_name"] == "MCU-32-Core"
        assert alternates["sku_category"] == "Semiconductors"
        assert len(alternates["suggested_suppliers"]) > 0

    finally:
        db.close()
