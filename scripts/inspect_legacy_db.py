"""Print schema and counts only. Never print personal data or stored values."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parents[1] / "backend" / "pricelurk.db"
with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as db:
    for name in ("users", "products", "price_snapshots", "alerts"):
        columns = [row[1] for row in db.execute(f"PRAGMA table_info({name})")]
        count = db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name}: {count} rows; columns={','.join(columns)}")
