# PriceLurk

Plataforma de E-Commerce Intelligence para monitoreo y alerta de volatilidad de precios.

## Requisitos
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

## Backend
1. `cd backend`
2. `python -m venv .venv`
3. `source .venv/bin/activate` o `.\.venv\Scripts\activate` en Windows
4. `pip install -r requirements.txt`
5. Copiar `.env.example` a `.env` y configurar
6. Iniciar servidor: `uvicorn app.main:app --reload`
7. Iniciar celery: `celery -A app.workers.celery_app worker --loglevel=info`

## Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`
