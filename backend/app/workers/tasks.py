from app.workers.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.models import Product, PriceSnapshot, Alert
import asyncio
from app.services.scraper import scrape_product
from datetime import datetime

@celery_app.task
def check_product_prices():
    db = SessionLocal()
    products = db.query(Product).filter(Product.is_active == True).all()
    
    for product in products:
        # We need to run the async scraper synchronously inside the Celery task
        # or use a synchronous scraper. For this boilerplate, we'll mock the call.
        scraped_data = asyncio.run(scrape_product(product.url))
        if scraped_data:
            current_price = scraped_data["price"]
            
            # Save snapshot
            snapshot = PriceSnapshot(product_id=product.id, price=current_price)
            db.add(snapshot)
            
            # Update product current price
            product.current_price = current_price
            
            # Check for alert
            if current_price <= product.target_price:
                alert = Alert(product_id=product.id, channel="telegram", status="triggered", triggered_at=datetime.utcnow())
                db.add(alert)
                # Send notification logic here...
                
    db.commit()
    db.close()
