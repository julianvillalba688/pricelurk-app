from datetime import datetime, timezone

from sqlalchemy import update

from app.core.config import settings
from app.models.models import Alert, PriceSnapshot, Product
from app.services.money import amount, currency_code
from app.services.telegram import send_telegram


def record_observation(db, product, data):
    currency = currency_code(data["currency"])
    price = amount(data["price"], currency)
    if product.currency and product.currency != currency:
        raise ValueError("La moneda observada cambió; no se mezclarán precios.")
    product.current_price = price
    product.currency = currency
    product.title = data["title"]
    product.source = "observed"
    product.image_url = ""
    db.add(PriceSnapshot(product_id=product.id, price=price, currency=currency, source="observed"))
    reached = product.target_currency == currency and product.target_price is not None and price <= product.target_price
    if not reached:
        product.alert_active = False
    db.flush()
    return reached


async def finish_observation(db, product, data):
    reached = record_observation(db, product, data)
    alert = None
    message = ""
    if reached and settings.telegram_enabled:
        # Atomic claim also protects overlapping workers/manual refreshes.
        claimed = db.execute(update(Product).where(Product.id == product.id, Product.alert_active.is_(False))
                             .values(alert_active=True).execution_options(synchronize_session=False)).rowcount
        if claimed:
            alert = Alert(product_id=product.id, channel="telegram", status="claimed", triggered_at=datetime.now(timezone.utc))
            db.add(alert)
            message = f"{product.title}: {data['price']} {data['currency']} (objetivo {product.target_price})"
    # Persist claim before sending. Crash may miss a message, never replay a claim.
    db.commit()
    if alert:
        alert.status = await send_telegram(message)
        db.commit()
    db.refresh(product)
    return product
