import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints import products
from app.core.config import settings


@asynccontextmanager
async def lifespan(app):
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not settings.telegram_enabled:
        logging.getLogger(__name__).warning("Telegram notifications disabled (credentials absent or demo mode)")
    yield


app = FastAPI(title="PriceLurk API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                   allow_credentials=False, allow_methods=["GET", "POST", "DELETE"],
                   allow_headers=["Content-Type", "X-API-Key"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    # Do not echo submitted input, URLs, headers or internal validator context.
    return JSONResponse(status_code=422, content={"detail": "Datos inválidos. Verifica URL, precio y moneda admitida."})


@app.exception_handler(Exception)
async def internal_error(request: Request, exc):
    logging.getLogger(__name__).error("Unhandled request failure")
    return JSONResponse(status_code=500, content={"detail": "No se pudo completar la operación."})


@app.get("/api/v1/status")
def status():
    return {"notifications_enabled": settings.telegram_enabled,
            "writes_enabled": bool(settings.WRITE_API_KEY) and not settings.DEMO_MODE,
            "demo": settings.DEMO_MODE, "currencies": ["USD", "EUR", "COP", "JPY"]}


@app.get("/")
def root():
    return {"message": "PriceLurk API", "status": "/api/v1/status"}
