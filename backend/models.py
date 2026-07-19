import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from backend.database import Base

class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    location = Column(String, nullable=False)
    capacity_sqft = Column(Integer, nullable=False)
    max_capacity_units = Column(Integer, nullable=False)

    shipments = relationship("Shipment", back_populates="warehouse")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    contact_email = Column(String, nullable=False)
    risk_score = Column(Float, default=0.0)  # Calculated metric between 0.0 and 1.0
    category = Column(String, nullable=False)  # e.g., Electronics, Metals, Plastics
    geopolitical_risk = Column(Float, default=0.0)  # 0.0 to 1.0
    financial_risk = Column(Float, default=0.0)  # 0.0 to 1.0

    shipments = relationship("Shipment", back_populates="supplier")


class SKU(Base):
    __tablename__ = "skus"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    category = Column(String, nullable=False)
    unit_price = Column(Float, nullable=False)
    current_stock = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)
    average_daily_demand = Column(Float, default=0.0)
    lead_time_days = Column(Integer, default=0)

    shipments = relationship("Shipment", back_populates="sku")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sku_id = Column(String, ForeignKey("skus.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    destination_warehouse_id = Column(String, ForeignKey("warehouses.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # pending, transit, delivered, delayed
    estimated_delivery_date = Column(DateTime, nullable=False)
    actual_delivery_date = Column(DateTime, nullable=True)
    shipping_cost = Column(Float, default=0.0)

    sku = relationship("SKU", back_populates="shipments")
    supplier = relationship("Supplier", back_populates="shipments")
    warehouse = relationship("Warehouse", back_populates="shipments")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_type = Column(String, nullable=False)  # autonomous, reactive
    status = Column(String, nullable=False)  # running, success, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    summary = Column(String, nullable=True)

    decisions = relationship("AgentDecision", back_populates="run", cascade="all, delete-orphan")


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("agent_runs.id"), nullable=False)
    decision_type = Column(String, nullable=False)  # stockout_risk, supplier_warning, shipment_delay, restock_recommendation
    severity = Column(String, nullable=False)  # low, medium, high, critical
    subject_id = Column(String, nullable=False)  # ID of SKU, Supplier, or Shipment
    reasoning = Column(JSON, nullable=False)  # JSONB dictionary detailing the decision logic
    recommended_action = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AgentRun", back_populates="decisions")
