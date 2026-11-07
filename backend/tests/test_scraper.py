from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.services.scraper import ParsingError, ScrapingError, clean_price, parse_product, scrape_product


@pytest.mark.parametrize("value,expected", [("1250000.00", "1250000"), ("0.10", "0.10"), ("4599.99", "4599.99"), ("12345", "12345")])
def test_machine_decimal(value, expected):
    assert clean_price(value) == Decimal(expected)


@pytest.mark.parametrize("value", ["1,250.00 USD", "$ 1.250.000", "1,250", "1.250,99", "invalid", "", None, "NaN", "-1"])
def test_reject_ambiguous_price(value):
    with pytest.raises(ParsingError):
        clean_price(value)


def html(currency="USD", price="45.99"):
    return '<script type="application/ld+json">{"@type":"Product","name":"Fixture","offers":{"@type":"Offer","price":"' + price + '","priceCurrency":"' + currency + '"}}</script>'


@pytest.mark.parametrize("url,platform", [("https://www.amazon.com/dp/fixture", "amazon"), ("https://articulo.mercadolibre.com.co/MCO-fixture", "mercadolibre"), ("https://es.aliexpress.com/item/fixture", "aliexpress")])
async def test_supported_store_fixture(url, platform):
    with patch("app.services.scraper.fetch_document", AsyncMock(return_value=(html().encode(), url, "text/html"))):
        result = await scrape_product(url)
    assert result["platform"] == platform
    assert result["price"] == Decimal("45.99")
    assert result["currency"] == "USD"


@pytest.mark.parametrize("currency", ["", "$", "unknown", "usd"])
def test_currency_not_inferred(currency):
    with pytest.raises(ParsingError):
        parse_product(html(currency), "https://amazon.com/a")


def test_metadata_pair():
    doc = '<meta property="og:title" content="Fixture"><meta property="product:price:amount" content="123.45"><meta property="product:price:currency" content="COP">'
    assert parse_product(doc, "https://mercadolibre.com.co/a")["currency"] == "COP"
    with pytest.raises(ParsingError):
        parse_product(doc.replace("product:price:currency", "og:price:currency"), "https://mercadolibre.com.co/a")


def test_multiple_products_not_arbitrarily_selected():
    with pytest.raises(ParsingError, match="varios productos"):
        parse_product(html() + html("COP", "10000"), "https://amazon.com/a")


async def test_transport_failure_is_generic():
    with patch("app.services.scraper.fetch_document", AsyncMock(side_effect=RuntimeError("internal credentials"))):
        with pytest.raises(ScrapingError, match="No se pudo consultar"):
            await scrape_product("https://amazon.com/a")
