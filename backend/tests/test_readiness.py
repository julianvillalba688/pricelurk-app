from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.models.models import Product, PriceSnapshot
from app.services.money import amount, currency_code
from app.services.network import UnsafeDestination, validate_url, PublicResolver
from app.workers.celery_app import celery_app
from app.workers.tasks import check_product_prices


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://localhost/a", "https://127.0.0.1/",
    "https://amazon.com.evil.example/", "https://evil.example/amazon.com",
    "https://amazon.com@127.0.0.1/", "https://www.amazon.com:444/",
    "https://www.amazon.com\\@localhost/", "https://[::1]/",
    "https://2130706433/", "https://user:pass@www.amazon.com/",
])
def test_reject_destinations(url):
    with pytest.raises(UnsafeDestination):
        validate_url(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1", "::ffff:127.0.0.1", "100.64.0.1"])
@pytest.mark.asyncio
async def test_dns_rejects_non_public(ip):
    with patch("app.services.network.resolve_addresses", AsyncMock(return_value=[ip])):
        with pytest.raises(UnsafeDestination):
            await PublicResolver().resolve("www.amazon.com", 443)


def test_decimal_currency():
    assert amount("0.10", "USD") + amount("0.20", "USD") == Decimal("0.30")
    assert currency_code("COP") == "COP"
    for value in ["NaN", "Infinity", "-1", "1.001", "10000000000000000"]:
        with pytest.raises(ValueError):
            amount(value, "USD")
    with pytest.raises(ValueError):
        amount("1.1", "JPY")
    with pytest.raises(ValueError):
        currency_code("$")


@pytest.fixture
def client(sessions, monkeypatch):
    monkeypatch.setattr(settings, "WRITE_API_KEY", "test-only-key")
    def db():
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = db
    # Startup migrations run separately; no real application DB in tests.
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


OBSERVATION = {"title": "Fixture product", "price": Decimal("12.30"), "currency": "USD", "platform": "amazon", "image_url": ""}
HEADERS = {"X-API-Key": "test-only-key"}


def test_complete_product_flow(client, sessions):
    body = {"url": "https://www.amazon.com/dp/fixture", "target_price": "10.00", "currency": "USD"}
    with patch("app.api.endpoints.products.scrape_product", AsyncMock(return_value=OBSERVATION)):
        assert client.post("/api/v1/products/track", json=body).status_code == 403
        result = client.post("/api/v1/products/track", json=body, headers=HEADERS)
        assert result.status_code == 200, result.text
        product = result.json()
        assert product["current_price"] == "12.30"
        product_id = product["id"]
        assert len(client.get("/api/v1/products").json()) == 1
        history = client.get(f"/api/v1/products/{product_id}/history").json()
        assert len(history["history"]) == 1
        assert history["history"][0]["id"] > 0
        assert history["history"][0]["timestamp"].endswith("Z")
        assert client.post(f"/api/v1/products/{product_id}/refresh", headers=HEADERS).status_code == 200
        assert len(client.get(f"/api/v1/products/{product_id}/history").json()["history"]) == 2
        assert client.post(f"/api/v1/products/{product_id}/seed-history", headers=HEADERS).status_code in (404, 405)
        assert client.delete(f"/api/v1/products/{product_id}", headers=HEADERS).status_code == 200
        assert client.get("/api/v1/products").json() == []
    with sessions() as db:
        assert db.query(PriceSnapshot).count() == 2


def test_currency_mismatch_atomic(client, sessions):
    with patch("app.api.endpoints.products.scrape_product", AsyncMock(return_value=OBSERVATION)):
        result = client.post("/api/v1/products/track", json={"url": "https://amazon.com/a", "target_price": "10", "currency": "COP"}, headers=HEADERS)
    assert result.status_code == 422
    with sessions() as db:
        assert db.query(Product).count() == 0


def test_api_price_requires_exact_decimal_string(client):
    with patch("app.api.endpoints.products.scrape_product", AsyncMock()) as scrape:
        result = client.post("/api/v1/products/track", json={"url": "https://amazon.com/a", "target_price": 10.1, "currency": "USD"}, headers=HEADERS)
    assert result.status_code == 422
    scrape.assert_not_awaited()


def test_internal_errors_not_exposed_and_no_partial_product(client, sessions):
    with patch("app.api.endpoints.products.scrape_product", AsyncMock(side_effect=RuntimeError("secret-internal-value"))):
        result = client.post("/api/v1/products/track", json={"url": "https://amazon.com/a", "target_price": "10", "currency": "USD"}, headers=HEADERS)
    assert result.status_code == 500
    assert "secret-internal-value" not in result.text
    with sessions() as db:
        assert db.query(Product).count() == 0


def test_legacy_history_excluded_and_unknown_target_never_assigned(client, sessions):
    with sessions() as db:
        product = Product(url="https://amazon.com/a", title="Legacy", current_price=Decimal("123.456"), target_price=Decimal("100"), currency=None, target_currency=None, source="legacy_unverified")
        db.add(product)
        db.flush()
        db.add(PriceSnapshot(product_id=product.id, price=Decimal("123.456"), source="legacy_unverified", currency=None))
        db.commit()
        product_id = product.id
    before = client.get(f"/api/v1/products/{product_id}/history").json()
    assert before["history"] == []
    assert before["stats"] is None
    assert before["excluded_legacy_count"] == 1
    with patch("app.api.endpoints.products.scrape_product", AsyncMock(return_value=OBSERVATION)):
        refreshed = client.post(f"/api/v1/products/{product_id}/refresh", headers=HEADERS).json()
    assert refreshed["currency"] == "USD"
    assert refreshed["target_currency"] is None
    assert len(client.get(f"/api/v1/products/{product_id}/history").json()["history"]) == 1


def test_missing_key_disables_writes_even_on_loopback(client, monkeypatch):
    monkeypatch.setattr(settings, "WRITE_API_KEY", "")
    assert client.get("/api/v1/status").json()["writes_enabled"] is False
    assert client.delete("/api/v1/products/1", headers=HEADERS).status_code == 403


def test_demo_read_only(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert client.get("/api/v1/status").json()["notifications_enabled"] is False
    assert client.delete("/api/v1/products/1", headers=HEADERS).status_code == 403


def test_beat_registered_and_routed():
    celery_app.loader.import_default_modules()
    name = "app.workers.tasks.check_product_prices"
    assert name in celery_app.tasks
    schedule = celery_app.conf.beat_schedule["monitor-prices"]
    assert schedule["task"] == name
    assert schedule["options"]["queue"] == settings.CELERY_QUEUE
    assert celery_app.conf.task_default_queue == settings.CELERY_QUEUE


def test_worker_isolation_and_dedup(sessions, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "fixture-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "fixture-chat")
    with sessions() as db:
        for i in range(3):
            db.add(Product(url=f"https://amazon.com/{i}", title="Fixture", platform="amazon", current_price=Decimal("15"), target_price=Decimal("13"), currency="USD", target_currency="USD"))
        db.commit()
    async def scrape(url):
        if url.endswith("/0"):
            raise ValueError("private internal error")
        return OBSERVATION
    monkeypatch.setattr("app.workers.tasks.SessionLocal", sessions)
    monkeypatch.setattr("app.workers.tasks.scrape_product", scrape)
    send = AsyncMock(return_value="sent")
    monkeypatch.setattr("app.services.monitoring.send_telegram", send)
    check_product_prices()
    check_product_prices()
    assert send.call_count == 2
    with sessions() as db:
        assert db.query(PriceSnapshot).count() == 4
        assert db.get(Product, 1).current_price == Decimal("15")
        assert db.get(Product, 2).current_price == Decimal("12.30")


def test_worker_rolls_back_partial_observation_and_continues(sessions, monkeypatch):
    from app.services.monitoring import finish_observation, record_observation
    with sessions() as db:
        for i in range(2):
            db.add(Product(url=f"https://amazon.com/{i}", title="Fixture", current_price=Decimal("20"), target_price=Decimal("10"), currency="USD", target_currency="USD"))
        db.commit()
    async def fail_first(db, product, data):
        if product.id == 1:
            record_observation(db, product, data)
            raise RuntimeError("Persistence failure after flush")
        return await finish_observation(db, product, data)
    monkeypatch.setattr("app.workers.tasks.SessionLocal", sessions)
    monkeypatch.setattr("app.workers.tasks.scrape_product", AsyncMock(return_value=OBSERVATION))
    monkeypatch.setattr("app.workers.tasks.finish_observation", fail_first)
    assert check_product_prices() == {"updated": 1, "failed": 1}
    with sessions() as db:
        assert db.get(Product, 1).current_price == Decimal("20")
        assert db.get(Product, 2).current_price == Decimal("12.30")
        assert db.query(PriceSnapshot).count() == 1
