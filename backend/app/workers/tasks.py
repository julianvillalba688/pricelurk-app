import asyncio
import logging

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.models import Product
from app.services.monitoring import finish_observation
from app.services.scraper import scrape_product
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def check_one(product_id):
    with SessionLocal() as db:
        try:
            product = db.get(Product, product_id)
            if not product or not product.is_active or product.source == "demo":
                return False
            data = await scrape_product(product.url)
            await finish_observation(db, product, data)
            return True
        except Exception:
            db.rollback()
            logger.warning("Product check failed: id=%s", product_id)
            return False


@celery_app.task(name="app.workers.tasks.check_product_prices")
def check_product_prices():
    if settings.DEMO_MODE:
        return {"updated": 0, "failed": 0, "demo": True}
    with SessionLocal() as db:
        ids = [row[0] for row in db.query(Product.id).filter(Product.is_active.is_(True), Product.source != "demo").all()]
    updated = 0
    for product_id in ids:
        updated += int(asyncio.run(check_one(product_id)))
    return {"updated": updated, "failed": len(ids) - updated}
