import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Warehouse, Supplier, SKU, Shipment, AgentRun, AgentDecision
from backend.risk import score_supplier_risk

def seed_db():
    db = SessionLocal()
    try:
        print("Cleaning existing database records...")
        db.query(AgentDecision).delete()
        db.query(AgentRun).delete()
        db.query(Shipment).delete()
        db.query(SKU).delete()
        db.query(Supplier).delete()
        db.query(Warehouse).delete()
        db.commit()

        # Deterministic random number generator
        rng = random.Random(42)
        now = datetime.utcnow()

        print("Seeding warehouses...")
        warehouses_data = [
            {"name": "Global Hub Chicago", "location": "Chicago, IL", "capacity_sqft": 250000, "max_capacity_units": 100000},
            {"name": "West Coast Logistics", "location": "Los Angeles, CA", "capacity_sqft": 180000, "max_capacity_units": 75000},
            {"name": "East Coast Distribution", "location": "Newark, NJ", "capacity_sqft": 200000, "max_capacity_units": 80000},
            {"name": "Southern Fulfillment", "location": "Dallas, TX", "capacity_sqft": 150000, "max_capacity_units": 60000},
            {"name": "Midwest Depot", "location": "Indianapolis, IN", "capacity_sqft": 120000, "max_capacity_units": 50000},
            {"name": "Pacific Northwest Hub", "location": "Seattle, WA", "capacity_sqft": 100000, "max_capacity_units": 40000},
        ]
        warehouses = [Warehouse(**data) for data in warehouses_data]
        db.add_all(warehouses)
        db.commit()

        print("Seeding suppliers...")
        suppliers_data = [
            {"name": "Apex Semiconductor", "contact_email": "ops@apexsemi.com", "category": "Semiconductors", "geopolitical_risk": 0.1, "financial_risk": 0.15},
            {"name": "Shenzhen ElectroTech", "contact_email": "sales@sz-electrotech.cn", "category": "Semiconductors", "geopolitical_risk": 0.75, "financial_risk": 0.20},
            {"name": "Kyoto Precision Sensors", "contact_email": "support@kyotosensors.co.jp", "category": "Sensors", "geopolitical_risk": 0.15, "financial_risk": 0.10},
            {"name": "Taipei Tech Circuits", "contact_email": "info@taipeicircuits.tw", "category": "Semiconductors", "geopolitical_risk": 0.80, "financial_risk": 0.25},
            {"name": "Berlin Metallurgical", "contact_email": "contracts@berlinmetal.de", "category": "Raw Metals", "geopolitical_risk": 0.10, "financial_risk": 0.10},
            {"name": "Detroit Plastic Molders", "contact_email": "rfq@detroitplastics.com", "category": "Plastics", "geopolitical_risk": 0.05, "financial_risk": 0.70},  # High financial risk
            {"name": "Seoul Lithium Corp", "contact_email": "logistics@seoullithium.com", "category": "Batteries", "geopolitical_risk": 0.25, "financial_risk": 0.15},
            {"name": "Santiago Copper Mining", "contact_email": "export@santiagomining.cl", "category": "Raw Metals", "geopolitical_risk": 0.40, "financial_risk": 0.45},
            {"name": "Hanoi Sensor Systems", "contact_email": "contact@hanoisensors.vn", "category": "Sensors", "geopolitical_risk": 0.45, "financial_risk": 0.35},
            {"name": "Guangzhou Battery Tech", "contact_email": "supply@gzbattery.cn", "category": "Batteries", "geopolitical_risk": 0.65, "financial_risk": 0.50},
            {"name": "Munich Optical Group", "contact_email": "info@munichoptical.de", "category": "Sensors", "geopolitical_risk": 0.10, "financial_risk": 0.10},
            {"name": "São Paulo Polymer Ltd", "contact_email": "vendas@saopaulopolymer.com.br", "category": "Plastics", "geopolitical_risk": 0.35, "financial_risk": 0.65},  # High financial risk
            {"name": "Arizona Silicon Works", "contact_email": "orders@arizonasilicon.com", "category": "Semiconductors", "geopolitical_risk": 0.10, "financial_risk": 0.15},
            {"name": "Bangalore Software & Chips", "contact_email": "partner@bangalorechips.in", "category": "Sensors", "geopolitical_risk": 0.20, "financial_risk": 0.25},
            {"name": "Jakarta Chemical Corp", "contact_email": "trade@jakartachemical.id", "category": "Plastics", "geopolitical_risk": 0.50, "financial_risk": 0.55},
        ]
        
        # We will create suppliers, but risk_score will be updated after shipments are simulated
        suppliers = []
        for s in suppliers_data:
            supplier = Supplier(
                name=s["name"],
                contact_email=s["contact_email"],
                category=s["category"],
                geopolitical_risk=s["geopolitical_risk"],
                financial_risk=s["financial_risk"],
                risk_score=0.0  # Temporary
            )
            db.add(supplier)
            suppliers.append(supplier)
        db.commit()

        print("Seeding SKUs...")
        sku_categories = ["Semiconductors", "Sensors", "Raw Metals", "Plastics", "Batteries"]
        
        # Specifically design some SKUs with critical/high risk configurations
        # standard fields: current_stock, reorder_point, safety_stock, average_daily_demand, lead_time_days
        skus = []
        
        sku_templates = [
            # Semiconductors
            {"name": "MCU-32-Core", "description": "32-bit Microcontroller Core Chip", "category": "Semiconductors", "unit_price": 45.50, "current_stock": 50, "reorder_point": 200, "safety_stock": 100, "average_daily_demand": 15.0, "lead_time_days": 14}, # HIGH RISK: Stock out in 3.3 days, lead time is 14
            {"name": "FPGA-Alpha-9", "description": "Field Programmable Gate Array Series 9", "category": "Semiconductors", "unit_price": 320.00, "current_stock": 5, "reorder_point": 15, "safety_stock": 8, "average_daily_demand": 1.2, "lead_time_days": 20}, # HIGH RISK: Below safety stock, stockout in 4.1 days
            {"name": "RAM-DDR5-8G", "description": "8GB DDR5 RAM modules", "category": "Semiconductors", "unit_price": 28.00, "current_stock": 2500, "reorder_point": 1000, "safety_stock": 500, "average_daily_demand": 80.0, "lead_time_days": 10}, # Healthy
            {"name": "ASIC-Crypto-V1", "description": "Application Specific IC for Cryptography", "category": "Semiconductors", "unit_price": 125.00, "current_stock": 0, "reorder_point": 50, "safety_stock": 20, "average_daily_demand": 3.5, "lead_time_days": 15}, # CRITICAL: Out of stock!
            
            # Batteries
            {"name": "LIPO-5000", "description": "5000mAh Lithium Polymer Battery Cell", "category": "Batteries", "unit_price": 18.20, "current_stock": 120, "reorder_point": 400, "safety_stock": 200, "average_daily_demand": 25.0, "lead_time_days": 12}, # HIGH RISK: stockout in 4.8 days
            {"name": "LIFEPO4-Pack-24V", "description": "24V LiFePO4 battery storage pack", "category": "Batteries", "unit_price": 450.00, "current_stock": 80, "reorder_point": 60, "safety_stock": 30, "average_daily_demand": 2.0, "lead_time_days": 18}, # Healthy
            
            # Sensors
            {"name": "LIDAR-Scanner-Pro", "description": "High resolution LiDAR sensor", "category": "Sensors", "unit_price": 899.00, "current_stock": 8, "reorder_point": 25, "safety_stock": 12, "average_daily_demand": 1.5, "lead_time_days": 21}, # HIGH RISK: below safety, days remaining 5.3
            {"name": "TEMP-THERMO-1", "description": "Digital thermometer sensor probe", "category": "Sensors", "unit_price": 4.50, "current_stock": 1500, "reorder_point": 800, "safety_stock": 400, "average_daily_demand": 50.0, "lead_time_days": 8}, # Healthy
            
            # Raw Metals & Plastics
            {"name": "COPPER-ROD-8MM", "description": "High conductivity copper rods 8mm", "category": "Raw Metals", "unit_price": 75.00, "current_stock": 400, "reorder_point": 1200, "safety_stock": 600, "average_daily_demand": 70.0, "lead_time_days": 7}, # HIGH RISK: stockout in 5.7 days
            {"name": "ALUMINUM-SHEET-2MM", "description": "Structural aluminum sheets 2mm", "category": "Raw Metals", "unit_price": 45.00, "current_stock": 850, "reorder_point": 800, "safety_stock": 400, "average_daily_demand": 35.0, "lead_time_days": 10}, # Healthy
            {"name": "POLYMER-ABS-G1", "description": "Acrylonitrile Butadiene Styrene Grade 1 Pellets", "category": "Plastics", "unit_price": 12.00, "current_stock": 12000, "reorder_point": 10000, "safety_stock": 5000, "average_daily_demand": 800.0, "lead_time_days": 5}, # Below reorder point, stock out in 15 days, lead time is 5 (Medium Risk)
        ]

        # Populate templates first
        for t in sku_templates:
            sku = SKU(**t)
            db.add(sku)
            skus.append(sku)
        db.commit()

        # Generate remaining SKUs dynamically to reach exactly 40 SKUs
        existing_names = {t["name"] for t in sku_templates}
        cat_items = {
            "Semiconductors": ["MCU-16-Core", "MCU-8-Core", "RF-Transceiver", "PMIC-Power-Controller", "DAC-Converter", "ADC-Precision"],
            "Sensors": ["IMU-6AXIS", "PRESS-BARO-2", "HUMID-SENS-A", "GYRO-OPTICAL", "FLOW-LIQUID", "GAS-CO2-MONITOR"],
            "Raw Metals": ["STEEL-BEAM-H", "TITANIUM-TUBE", "NICKEL-PLATE", "SILICON-INGOT-9N", "TUNGSTEN-WIRE"],
            "Plastics": ["POLYMER-PC-CLEAR", "POLYMER-PP-HD", "NYLON-ROD-G2", "SILICONE-ELAST-R"],
            "Batteries": ["LIPO-3000", "LION-18650", "NMC-CATHODE", "LTO-ANODE", "CELL-SPACER-P"]
        }

        while len(skus) < 40:
            cat = rng.choice(sku_categories)
            item_list = cat_items[cat]
            name = rng.choice(item_list)
            if name in existing_names:
                name = f"{name}-{rng.randint(10, 99)}"
            existing_names.add(name)
            
            unit_price = round(rng.uniform(10.0, 500.0), 2)
            average_daily_demand = round(rng.uniform(2.0, 50.0), 2)
            lead_time_days = rng.randint(5, 20)
            safety_stock = int(average_daily_demand * lead_time_days * rng.uniform(0.5, 1.0))
            reorder_point = int(safety_stock + (average_daily_demand * lead_time_days))
            # Healthy stock: reorder point + safety stock
            current_stock = int(reorder_point * rng.uniform(0.8, 1.8))
            
            sku = SKU(
                name=name,
                description=f"Standard component: {name} in category {cat}",
                category=cat,
                unit_price=unit_price,
                current_stock=current_stock,
                reorder_point=reorder_point,
                safety_stock=safety_stock,
                average_daily_demand=average_daily_demand,
                lead_time_days=lead_time_days
            )
            db.add(sku)
            skus.append(sku)
        db.commit()

        print("Seeding shipments (60 total)...")
        # To calculate historical delay rate for suppliers, we simulate historical shipments.
        # Let's say each supplier has 10 historical shipments (delivered).
        # We will create exactly 60 active or recently delivered shipments,
        # but keep track of delivery performance to set risk scores.
        
        statuses = ["delivered", "delivered", "delivered", "transit", "pending", "delayed"]
        
        # Map suppliers by category so we map shipments realistically
        suppliers_by_cat = {}
        for s in suppliers:
            if s.category not in suppliers_by_cat:
                suppliers_by_cat[s.category] = []
            suppliers_by_cat[s.category].append(s)

        shipments = []
        # Generate 60 shipments
        for i in range(60):
            # Pick a random SKU and map to a supplier of the same category
            sku = skus[i % len(skus)]
            cat = sku.category
            valid_suppliers = suppliers_by_cat.get(cat, suppliers)
            supplier = rng.choice(valid_suppliers)
            warehouse = rng.choice(warehouses)
            
            quantity = int(sku.average_daily_demand * rng.randint(10, 40))
            
            # Status distribution:
            # Let's seed specific delayed/transit shipments to cause stock issues or highlight supplier failure.
            if i < 8:
                # Delayed active shipments
                status = "delayed"
                est_days = rng.randint(-10, -2)  # Estimated delivery is in the past!
                est_delivery = now + timedelta(days=est_days)
                actual_delivery = None
            elif i < 15:
                # Active transit shipments (on time)
                status = "transit"
                est_days = rng.randint(2, 10)
                est_delivery = now + timedelta(days=est_days)
                actual_delivery = None
            elif i < 20:
                # Pending orders (not shipped yet)
                status = "pending"
                est_days = rng.randint(5, 15)
                est_delivery = now + timedelta(days=est_days)
                actual_delivery = None
            else:
                # Delivered (historical)
                status = "delivered"
                # Delivered in the past
                ship_days_ago = rng.randint(5, 40)
                est_delivery = now - timedelta(days=ship_days_ago)
                # Some are delivered late
                if rng.random() < 0.25:  # 25% delay rate generally
                    actual_delivery = est_delivery + timedelta(days=rng.randint(2, 8))
                else:
                    actual_delivery = est_delivery - timedelta(days=rng.randint(0, 3))

            shipping_cost = round(quantity * sku.unit_price * rng.uniform(0.05, 0.12), 2)

            shipment = Shipment(
                sku_id=sku.id,
                supplier_id=supplier.id,
                destination_warehouse_id=warehouse.id,
                quantity=quantity,
                status=status,
                estimated_delivery_date=est_delivery,
                actual_delivery_date=actual_delivery,
                shipping_cost=shipping_cost
            )
            db.add(shipment)
            shipments.append(shipment)
        db.commit()

        # Update historical delay rate and composite risk score for each supplier
        print("Calculating supplier risk scores based on simulated history...")
        for s in suppliers:
            # Find all shipments for this supplier
            supp_shipments = [ship for ship in shipments if ship.supplier_id == s.id]
            
            # Calculate delay rate: (delayed shipments + delivered late) / total shipments
            total = len(supp_shipments)
            if total == 0:
                delay_rate = 0.15  # Default baseline
            else:
                delayed_count = 0
                for ship in supp_shipments:
                    if ship.status == "delayed":
                        delayed_count += 1
                    elif ship.status == "delivered" and ship.actual_delivery_date and ship.actual_delivery_date > ship.estimated_delivery_date:
                        delayed_count += 1
                delay_rate = delayed_count / total

            # Compute risk_score using pure function
            s.risk_score = score_supplier_risk(
                geopolitical_risk=s.geopolitical_risk,
                financial_risk=s.financial_risk,
                historical_delay_rate=delay_rate
            )
            
        db.commit()
        print(f"Database seeded successfully. {len(warehouses)} warehouses, {len(suppliers)} suppliers, {len(skus)} SKUs, and {len(shipments)} shipments created.")
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
