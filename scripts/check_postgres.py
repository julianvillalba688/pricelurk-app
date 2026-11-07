"""Explicit disposable-schema PostgreSQL migration/persistence smoke check.

Requires RUN_POSTGRES_CHECK=1 and a local test PostgreSQL DATABASE_URL.
Never run against production; all fixture data is in an isolated random schema,
which is dropped in finally. No network scraping or Telegram.
"""
import importlib
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
settings = importlib.import_module("app.core.config").settings
migrate = importlib.import_module("app.db.migrate").migrate
models = importlib.import_module("app.models.models")
PriceSnapshot, Product = models.PriceSnapshot, models.Product

if os.getenv("RUN_POSTGRES_CHECK") != "1" or not settings.DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("Explicit local PostgreSQL smoke check required")

schema = "readiness_check_" + uuid.uuid4().hex
control = create_engine(settings.DATABASE_URL)
with control.begin() as conn:
    conn.execute(text(f"CREATE SCHEMA {schema}"))
engine = create_engine(settings.DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
try:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE products (id SERIAL PRIMARY KEY, user_id INTEGER, url TEXT, platform TEXT, title TEXT, current_price DOUBLE PRECISION, target_price DOUBLE PRECISION, image_url TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT now())"))
        conn.execute(text("CREATE TABLE price_snapshots (id SERIAL PRIMARY KEY, product_id INTEGER, price DOUBLE PRECISION, timestamp TIMESTAMPTZ DEFAULT now())"))
        conn.execute(text("INSERT INTO products (url, title, current_price, target_price) VALUES ('https://amazon.com/fixture', 'Legacy fixture', 12.34, 10)"))
        conn.execute(text("INSERT INTO price_snapshots (product_id, price) VALUES (1, 12.34)"))
    migrate(engine)
    migrate(engine)
    with Session(engine) as db:
        legacy = db.get(Product, 1)
        assert legacy.currency is None and legacy.target_currency is None
        assert legacy.source == "legacy_unverified"
        assert legacy.current_price == Decimal("12.34")
        assert db.get(PriceSnapshot, 1).source == "legacy_unverified"
        product = Product(url="https://amazon.com/fixture", current_price=Decimal("0.10"), target_price=Decimal("0.20"), currency="USD", target_currency="USD", title="Temporary fixture")
        db.add(product)
        db.commit()
        db.refresh(product)
        assert product.current_price + product.target_price == Decimal("0.30")
        db.add(PriceSnapshot(product_id=product.id, price=Decimal("0.10"), currency="USD"))
        db.commit()
        assert db.query(PriceSnapshot).count() == 2
    print("PostgreSQL legacy migration, idempotency and exact decimal persistence passed in disposable schema.")
finally:
    engine.dispose()
    with control.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    control.dispose()
