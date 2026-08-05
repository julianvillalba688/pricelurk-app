import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine
from app.api.endpoints import products

# Create db tables
Base.metadata.create_all(bind=engine)

# --- FIX PARA PLAYWRIGHT EN WINDOWS ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="PriceLurk API")

# Configurar el middleware de CORS para desarrollo local
origins = [
    "http://localhost:5173",  # Vite Dev Server
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api/v1/products", tags=["products"])

@app.on_event("startup")
async def startup_event():
    print("Starting up PriceLurk Backend...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down PriceLurk Backend...")

@app.get("/")
def read_root():
    return {"message": "Welcome to PriceLurk API"}
