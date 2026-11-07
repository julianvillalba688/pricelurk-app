import hmac
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.models import PriceSnapshot, Product
from app.services.money import CURRENCIES, amount, currency_code
from app.services.monitoring import finish_observation
from app.services.network import validate_url
from app.services.scraper import ScrapingError, scrape_product

logger = logging.getLogger(__name__)
router = APIRouter()


def require_write(x_api_key: str = Header(default="")):
    if settings.DEMO_MODE or not settings.WRITE_API_KEY or not hmac.compare_digest(x_api_key.encode(), settings.WRITE_API_KEY.encode()):
        raise HTTPException(403, "Escritura deshabilitada o clave de acceso incorrecta.")


class ProductTrackRequest(BaseModel):
    url: str = Field(max_length=2048)
    target_price: Decimal = Field(gt=0, lt=Decimal("10000000000000000"))
    currency: str

    @field_validator("target_price", mode="before")
    @classmethod
    def require_decimal_string(cls, value):
        if not isinstance(value, str):
            raise ValueError("Envía el precio como texto decimal para conservar precisión.")
        return value

    @model_validator(mode="after")
    def validate_input(self):
        validate_url(self.url)
        self.currency = currency_code(self.currency)
        self.target_price = amount(self.target_price, self.currency)
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    title: str | None
    platform: str | None
    current_price: Decimal | None
    target_price: Decimal | None
    currency: str | None
    target_currency: str | None
    image_url: str | None
    is_active: bool
    source: str


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    price: Decimal
    currency: str
    source: str
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def timestamp_utc(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def find_product(db, product_id):
    product = db.get(Product, product_id)
    if not product or not product.is_active or ((product.source == "demo") != settings.DEMO_MODE):
        raise HTTPException(404, "Producto no encontrado.")
    return product


@router.post("/track", response_model=ProductResponse, dependencies=[Depends(require_write)])
async def track_product(data: ProductTrackRequest, db: Session = Depends(get_db)):
    try:
        scraped = await scrape_product(data.url)
        if scraped["currency"] != data.currency:
            raise ValueError("La moneda del objetivo no coincide con la observada.")
        product = Product(url=data.url, platform=scraped["platform"], target_price=data.target_price,
                          target_currency=data.currency, image_url="")
        db.add(product)
        db.flush()
        return await finish_observation(db, product, scraped)
    except (ValueError, ScrapingError) as exc:
        db.rollback()
        raise HTTPException(422, "No se pudo verificar precio y moneda. Revisa URL, moneda y disponibilidad de la tienda.") from exc
    except Exception as exc:
        db.rollback()
        logger.error("Product creation failed")
        raise HTTPException(500, "No se pudo guardar el producto.") from exc


@router.get("", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    query = db.query(Product).filter(Product.is_active.is_(True))
    query = query.filter(Product.source == "demo") if settings.DEMO_MODE else query.filter(Product.source != "demo")
    return query.order_by(Product.id).all()


@router.get("/{id}/history")
def get_product_history(id: int, db: Session = Depends(get_db)):
    product = find_product(db, id)
    source = "demo" if settings.DEMO_MODE else "observed"
    query = db.query(PriceSnapshot).filter(PriceSnapshot.product_id == id)
    excluded = query.filter(PriceSnapshot.source == "legacy_unverified").count()
    snapshots = query.filter(PriceSnapshot.source == source, PriceSnapshot.currency == product.currency).order_by(PriceSnapshot.timestamp, PriceSnapshot.id).all()
    prices = [snapshot.price for snapshot in snapshots]
    stats = None
    if prices:
        unit = Decimal(1).scaleb(-CURRENCIES[product.currency])
        stats = {"lowest_price": str(min(prices)), "highest_price": str(max(prices)),
                 "average_price": str((sum(prices) / len(prices)).quantize(unit)), "currency": product.currency}
    return {"stats": stats, "history": [SnapshotResponse.model_validate(s).model_dump(mode="json") for s in snapshots],
            "excluded_legacy_count": excluded, "source": source}


@router.post("/{id}/refresh", response_model=ProductResponse, dependencies=[Depends(require_write)])
async def refresh_product(id: int, db: Session = Depends(get_db)):
    product = find_product(db, id)
    try:
        return await finish_observation(db, product, await scrape_product(product.url))
    except (ValueError, ScrapingError) as exc:
        db.rollback()
        raise HTTPException(422, "No se pudo verificar un precio en la misma moneda.") from exc
    except Exception as exc:
        db.rollback()
        logger.error("Product refresh failed: id=%s", id)
        raise HTTPException(500, "No se pudo actualizar el producto.") from exc


@router.delete("/{id}", dependencies=[Depends(require_write)])
def delete_product(id: int, db: Session = Depends(get_db)):
    product = find_product(db, id)
    product.is_active = False
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, "No se pudo eliminar el producto.") from exc
    return {"detail": "Producto desactivado; historial conservado."}
