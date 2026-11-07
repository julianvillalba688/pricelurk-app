"""Explicit offline fixture seed. Never reachable from an HTTP endpoint."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.migrate import migrate
from app.models.models import PriceSnapshot, Product


def seed():
    if not settings.DEMO_MODE or settings.ENVIRONMENT == "production" or "demo" not in settings.DATABASE_URL.lower():
        raise RuntimeError("Requires DEMO_MODE=true, non-production and a separate demo database")
    migrate()
    with SessionLocal() as db:
        if db.query(Product).filter(Product.source != "demo").first():
            raise RuntimeError("Refusing to seed a database containing non-demo products")
        if db.query(Product).count():
            print("Demo already seeded; no additional data inserted.")
            return
        now = datetime.now(timezone.utc)
        for title, values, currency, target in [
            ("DEMO · Auriculares de ejemplo", ["129.90", "124.90", "119.90"], "USD", "110.00"),
            ("DEMO · Teclado de ejemplo", ["250000.00", "245000.00", "239900.00"], "COP", "230000.00"),
        ]:
            product = Product(title=title, url="https://www.amazon.com/dp/DEMO-NOT-A-PRODUCT", platform="fixture",
                              current_price=Decimal(values[-1]), target_price=Decimal(target), currency=currency,
                              target_currency=currency, source="demo", image_url="")
            db.add(product)
            db.flush()
            for i, value in enumerate(values):
                db.add(PriceSnapshot(product_id=product.id, price=Decimal(value), currency=currency, source="demo", timestamp=now - timedelta(days=2-i)))
        db.commit()
    print("Explicit synthetic demo fixtures inserted. Telegram and writes disabled.")


if __name__ == "__main__":
    seed()
