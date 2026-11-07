"""Additive idempotent migration; run once with all services stopped.

Legacy columns remain for recovery. No guessed currency or legacy history is
promoted to an observation. Back up the database before running this command.
"""
from decimal import Decimal

from sqlalchemy import inspect, text

from app.db.database import Base, engine
from app.models import models  # noqa: F401


def migrate(bind=engine):
    if "products" not in inspect(bind).get_table_names():
        Base.metadata.create_all(bind)
        return
    with bind.begin() as conn:
        # sqlite3 legacy transaction mode otherwise executes initial DDL outside
        # a transaction. Force an explicit lock/transaction before any rename.
        if bind.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        for table, prices in [("products", ["current_price", "target_price"]), ("price_snapshots", ["price"])]:
            cols = {col["name"] for col in inspect(conn).get_columns(table)}
            if "currency" in cols:
                continue
            for name in prices:
                conn.execute(text(f'ALTER TABLE {table} RENAME COLUMN {name} TO legacy_{name}'))
                sql_type = "TEXT" if bind.dialect.name == "sqlite" else "NUMERIC(20,4)"
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
                rows = conn.execute(text(f"SELECT id, legacy_{name} FROM {table}")).all()
                for row_id, old in rows:
                    value = format(Decimal(str(old)), "f") if old is not None else None
                    conn.execute(text(f"UPDATE {table} SET {name}=:value WHERE id=:id"), {"value": value, "id": row_id})
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN currency VARCHAR(3)"))
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN source VARCHAR NOT NULL DEFAULT 'legacy_unverified'"))
            if table == "products":
                conn.execute(text("ALTER TABLE products ADD COLUMN target_currency VARCHAR(3)"))
                conn.execute(text("ALTER TABLE products ADD COLUMN alert_active BOOLEAN NOT NULL DEFAULT FALSE"))
    Base.metadata.create_all(bind)


if __name__ == "__main__":
    migrate()
    print("Schema ready. Legacy records retain unknown currency and unverified provenance.")
