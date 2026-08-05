import logging
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Product, PriceSnapshot
from app.services.scraper import scrape_product
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class ProductTrackRequest(BaseModel):
    url: str
    target_price: float

class PriceSnapshotResponse(BaseModel):
    id: int
    price: float
    timestamp: str

    class Config:
        from_attributes = True

class ProductResponse(BaseModel):
    id: int
    url: str
    title: str
    platform: str
    current_price: float
    target_price: float
    image_url: str
    is_active: bool

    class Config:
        from_attributes = True

@router.post("/track", response_model=ProductResponse)
async def track_product(data: ProductTrackRequest, db: Session = Depends(get_db)):
    try:
        scraped_data = await scrape_product(data.url)
        if not scraped_data or not scraped_data.get("price") or not scraped_data.get("title"):
            raise HTTPException(
                status_code=400,
                detail="No se pudieron extraer el título o precio del producto.",
            )
        
        product = Product(
            url=data.url,
            platform=scraped_data.get("platform", "generic"),
            title=scraped_data["title"],
            current_price=scraped_data["price"],
            target_price=data.target_price,
            image_url=scraped_data.get("image_url", "")
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        
        snapshot = PriceSnapshot(product_id=product.id, price=product.current_price)
        db.add(snapshot)
        db.commit()
        
        return product
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"[Track Product Error] Fallo al procesar URL {data.url}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al guardar el producto: {str(e)}",
        )

@router.get("", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.is_active == True).all()
    return products

@router.get("/{id}/history")
def get_product_history(id: int, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    snapshots = db.query(PriceSnapshot).filter(PriceSnapshot.product_id == id).order_by(PriceSnapshot.timestamp.asc()).all()
    
    if not snapshots:
        # Si no hay snapshots aún, devolver punto inicial basado en el precio actual
        product = db.query(Product).filter(Product.id == id).first()
        if product:
            now = datetime.utcnow()
            history = [
                {"id": -1, "price": product.current_price, "timestamp": (now - timedelta(hours=1)).isoformat()},
                {"id": -2, "price": product.current_price, "timestamp": now.isoformat()},
            ]
            stats = {"lowest_price": product.current_price, "highest_price": product.current_price, "average_price": product.current_price}
            return {"stats": stats, "history": history}
        return {"stats": {"lowest_price": 0, "highest_price": 0, "average_price": 0}, "history": []}
    
    prices = [s.price for s in snapshots]
    stats = {
        "lowest_price": min(prices),
        "highest_price": max(prices),
        "average_price": sum(prices) / len(prices)
    }
    history = [{"id": s.id, "price": s.price, "timestamp": s.timestamp.isoformat()} for s in snapshots]
    
    # Si solo hay 1 punto, duplicarlo con 1h de diferencia para que la gráfica renderice
    if len(history) == 1:
        from datetime import datetime, timedelta
        first_ts = datetime.fromisoformat(history[0]["timestamp"])
        history.insert(0, {"id": -1, "price": history[0]["price"], "timestamp": (first_ts - timedelta(hours=1)).isoformat()})
    
    return {"stats": stats, "history": history}

@router.post("/{id}/seed-history")
def seed_product_history(id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    import random
    from datetime import datetime, timedelta
    
    base_price = product.current_price
    for i in range(30, 0, -1):
        price_variation = base_price * random.uniform(0.9, 1.1)
        snap_time = datetime.utcnow() - timedelta(days=i)
        snapshot = PriceSnapshot(product_id=id, price=round(price_variation, 2), timestamp=snap_time)
        db.add(snapshot)
    
    db.commit()
    return {"detail": "Seed data inserted"}

@router.post("/{id}/refresh")
async def refresh_product(id: int, db: Session = Depends(get_db)):
    """Re-raspa el producto y guarda un nuevo snapshot de precio."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        scraped_data = await scrape_product(product.url)
        if scraped_data and scraped_data.get("price"):
            product.current_price = scraped_data["price"]
            if scraped_data.get("image_url"):
                product.image_url = scraped_data["image_url"]
            snapshot = PriceSnapshot(product_id=product.id, price=product.current_price)
            db.add(snapshot)
            db.commit()
            db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        logger.exception(f"[Refresh Product Error] ID {id}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

@router.delete("/{id}")
def delete_product(id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    db.commit()
    return {"detail": "Product deactivated"}
