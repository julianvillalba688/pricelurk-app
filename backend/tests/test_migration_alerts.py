from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import create_engine, text

from app.core.config import Settings, settings
from app.db.migrate import migrate
from app.models.models import PriceSnapshot, Product
from app.services.monitoring import finish_observation
from app.services.telegram import send_telegram


def test_legacy_migration_preserves_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, current_price FLOAT, target_price FLOAT)"))
        conn.execute(text("CREATE TABLE price_snapshots (id INTEGER PRIMARY KEY, product_id INTEGER, price FLOAT)"))
        conn.execute(text("INSERT INTO products VALUES (1, 1234.56, 1200.00)"))
        conn.execute(text("INSERT INTO price_snapshots VALUES (1, 1, 1222.22)"))
    migrate(engine)
    migrate(engine)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT current_price, legacy_current_price, currency, target_currency, source FROM products")).one()
        assert row == ("1234.56", 1234.56, None, None, "legacy_unverified")
        assert conn.execute(text("SELECT count(*) FROM price_snapshots")).scalar() == 1
        assert conn.execute(text("SELECT currency, source FROM price_snapshots")).one() == (None, "legacy_unverified")
    engine.dispose()


async def test_alert_rearms_only_after_recovery(sessions, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "fixture-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "fixture-chat")
    send = AsyncMock(return_value="sent")
    monkeypatch.setattr("app.services.monitoring.send_telegram", send)
    with sessions() as db:
        product = Product(url="https://amazon.com/a", title="Fixture", target_price=Decimal("10"), currency="USD", target_currency="USD", platform="amazon")
        db.add(product)
        db.commit()
        for price in ["9", "8", "12", "9", "9"]:
            await finish_observation(db, product, {"title": "Fixture", "currency": "USD", "price": price})
        assert send.call_count == 2
        assert db.query(PriceSnapshot).count() == 5


async def test_currency_change_rolls_back(sessions):
    with sessions() as db:
        product = Product(url="https://amazon.com/a", current_price=Decimal("5.10"), currency="USD", target_currency="USD", target_price=Decimal("4"))
        db.add(product)
        db.commit()
        with pytest.raises(ValueError):
            await finish_observation(db, product, {"title": "Fixture", "currency": "COP", "price": "10000"})
        db.rollback()
        assert product.current_price == Decimal("5.10")
        assert db.query(PriceSnapshot).count() == 0


async def test_telegram_disabled_no_network(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "")
    with patch("httpx.AsyncClient") as client:
        assert await send_telegram("fixture") == "disabled"
        client.assert_not_called()


async def test_telegram_success_and_nonretryable_failure(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "fixture-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "fixture-chat")
    for status, body, expected in [(200, {"ok": True}, "sent"), (403, {"ok": False}, "failed")]:
        post = AsyncMock(return_value=httpx.Response(status, json=body))
        with patch("httpx.AsyncClient") as factory:
            factory.return_value.__aenter__.return_value.post = post
            assert await send_telegram("fixture") == expected
        post.assert_awaited_once()


async def test_telegram_429_bounded(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "fixture-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "fixture-chat")
    post = AsyncMock(return_value=httpx.Response(429, json={"ok": False}))
    with patch("httpx.AsyncClient") as factory, patch("app.services.telegram.asyncio.sleep", AsyncMock()):
        factory.return_value.__aenter__.return_value.post = post
        assert await send_telegram("fixture") == "failed"
    assert post.call_count == 3


def test_exact_sqlite_storage(sessions):
    with sessions() as db:
        db.add(Product(url="https://amazon.com/a", current_price=Decimal("0.10"), target_price=Decimal("0.20"), currency="USD", target_currency="USD"))
        db.commit()
        assert db.execute(text("SELECT current_price, typeof(current_price) FROM products")).one() == ("0.10", "text")


@pytest.mark.parametrize("failure,expected,count", [(httpx.ConnectTimeout("fixture"), "failed", 3), (httpx.ReadTimeout("fixture"), "unknown", 1)])
async def test_telegram_bounded_safe_retries(monkeypatch, failure, expected, count):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "fixture-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "fixture-chat")
    post = AsyncMock(side_effect=failure)
    with patch("httpx.AsyncClient") as factory, patch("app.services.telegram.asyncio.sleep", AsyncMock()):
        factory.return_value.__aenter__.return_value.post = post
        assert await send_telegram("fixture") == expected
    assert post.call_count == count


def test_demo_requires_explicit_separate_database():
    with pytest.raises(ValueError):
        Settings(DEMO_MODE=True, ENVIRONMENT="production", DATABASE_URL="sqlite:///demo.db", _env_file=None)
    with pytest.raises(ValueError):
        Settings(DEMO_MODE=True, DATABASE_URL="sqlite:///real.db", _env_file=None)


def test_generic_postgres_url_uses_installed_driver():
    config = Settings(DATABASE_URL="postgresql://localhost/pricelurk", _env_file=None)
    assert config.DATABASE_URL == "postgresql+psycopg2://localhost/pricelurk"


def test_demo_seed_is_explicit_and_idempotent(sessions, monkeypatch):
    from app.db import demo
    monkeypatch.setattr(demo, "SessionLocal", sessions)
    monkeypatch.setattr(demo, "migrate", lambda: None)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(RuntimeError):
        demo.seed()
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///test-demo.db")
    demo.seed()
    demo.seed()
    with sessions() as db:
        assert db.query(Product).count() == 2
        assert db.query(PriceSnapshot).count() == 6
        assert {p.source for p in db.query(Product)} == {"demo"}


def test_demo_cannot_seed_existing_real_products(sessions, monkeypatch):
    from app.db import demo
    monkeypatch.setattr(demo, "SessionLocal", sessions)
    monkeypatch.setattr(demo, "migrate", lambda: None)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///test-demo.db")
    with sessions() as db:
        db.add(Product(url="https://amazon.com/a", title="Observed", source="observed"))
        db.commit()
    with pytest.raises(RuntimeError):
        demo.seed()
