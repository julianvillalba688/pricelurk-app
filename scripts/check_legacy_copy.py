"""Migrate a private copy of the original SQLite; report counts only."""
import hashlib
import importlib
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
migrate = importlib.import_module("app.db.migrate").migrate

source = ROOT / "backend" / "pricelurk.db"
destination = ROOT / ".local" / "legacy-migration-check.db"
if not source.exists():
    raise RuntimeError("No original local database; use the automated fixture migration test instead")
before_hash = hashlib.sha256(source.read_bytes()).digest()
with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as original, sqlite3.connect(destination) as copy:
    original.backup(copy)
engine = create_engine(f"sqlite:///{destination.as_posix()}")
with engine.connect() as conn:
    counts = {name: conn.execute(text(f"SELECT count(*) FROM {name}")).scalar() for name in ("users", "products", "price_snapshots", "alerts")}
migrate(engine)
migrate(engine)
with engine.connect() as conn:
    for name, count in counts.items():
        assert conn.execute(text(f"SELECT count(*) FROM {name}")).scalar() == count
    for table, fields in [("products", ["current_price", "target_price"]), ("price_snapshots", ["price"])]:
        assert conn.execute(text(f"SELECT count(*) FROM {table} WHERE currency IS NOT NULL OR source != 'legacy_unverified'")).scalar() == 0
        for field in fields:
            for current, old in conn.execute(text(f"SELECT {field}, legacy_{field} FROM {table}")):
                assert current == str(old) or (current is None and old is None)
engine.dispose()
assert hashlib.sha256(source.read_bytes()).digest() == before_hash
print(f"Original SQLite unchanged; copy migrated twice with row counts preserved: {counts}")
