from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base
from app.services.money import Money


class User(Base):
    """Legacy schema only. No account or authentication routes are provided."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    url = Column(String, nullable=False)
    platform = Column(String)
    title = Column(String)
    current_price = Column(Money)
    target_price = Column(Money)
    currency = Column(String(3), nullable=True)
    target_currency = Column(String(3), nullable=True)
    image_url = Column(String, default="")
    is_active = Column(Boolean, default=True)
    alert_active = Column(Boolean, default=False, nullable=False)
    source = Column(String, default="observed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Money)
    currency = Column(String(3), nullable=True)
    source = Column(String, default="observed", nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    channel = Column(String)
    status = Column(String, default="pending")
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
