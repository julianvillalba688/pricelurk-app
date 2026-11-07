"""Conservative product extraction: explicit, paired amount/currency metadata only."""
import asyncio
import json
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.core.config import settings
from app.services.money import amount, currency_code
from app.services.network import fetch_document, validate_url


class ScrapingError(Exception):
    pass


class ProductNotFoundError(ScrapingError):
    pass


class ParsingError(ScrapingError):
    pass


def clean_price(value):
    """Only unambiguous machine-readable decimal amounts; no locale guessing."""
    try:
        if not isinstance(value, (str, int, Decimal)) or not str(value).replace(".", "", 1).isdigit():
            raise ValueError
        return Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ParsingError("Precio no estructurado o ambiguo.") from exc


def _nodes(value, depth=0):
    if depth > 12:
        return
    if isinstance(value, list):
        for item in value[:100]:
            yield from _nodes(item, depth + 1)
    elif isinstance(value, dict):
        yield value
        if "@graph" in value:
            yield from _nodes(value["@graph"], depth + 1)


def parse_product(html: str, url: str) -> dict:
    _, platform = validate_url(url)
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "", parse_float=Decimal)
            for node in _nodes(data):
                types = node.get("@type", [])
                if "Product" not in ([types] if isinstance(types, str) else types):
                    continue
                products.append(node)
        except (ValueError, TypeError, RecursionError):
            continue
    if len(products) > 1:
        raise ParsingError("La página contiene varios productos; no se elegirá uno arbitrariamente.")
    if products:
        node = products[0]
        offers = node.get("offers", {})
        offers = offers if isinstance(offers, list) else [offers]
        # Multiple offers may differ by variant/currency: require one concrete Offer.
        if len(offers) != 1 or not isinstance(offers[0], dict) or offers[0].get("@type") not in (None, "Offer"):
            raise ParsingError("Oferta de producto ambigua.")
        offer = offers[0]
        return observation(node.get("name"), offer.get("price"), offer.get("priceCurrency"), platform)
    def meta(key):
        tag = soup.find("meta", property=key)
        return tag.get("content") if tag else None
    # Require a matched namespace; don't pair unrelated price and currency fields.
    for prefix in ("product:price", "og:price"):
        if meta(prefix + ":amount") and meta(prefix + ":currency"):
            return observation(meta("og:title"), meta(prefix + ":amount"), meta(prefix + ":currency"), platform)
    raise ParsingError("La tienda no ofrece título, precio y moneda explícitos compatibles.")


def observation(title, price, currency, platform):
    if not isinstance(title, str) or not title.strip():
        raise ParsingError("Falta el título del producto.")
    try:
        currency = currency_code(currency)
        value = amount(clean_price(price), currency)
    except ValueError as exc:
        raise ParsingError("Precio o moneda no compatibles.") from exc
    # External image URLs are not loaded in clients; avoid leaking viewers' IPs.
    return {"title": title.strip()[:500], "price": value, "currency": currency,
            "platform": platform, "image_url": ""}


async def scrape_product_url(url: str) -> dict:
    validate_url(url)
    try:
        body, final_url, content_type = await fetch_document(url)
        if "html" not in content_type:
            raise ParsingError("La respuesta no es HTML.")
        try:
            return parse_product(body.decode("utf-8", errors="replace"), final_url)
        except ParsingError:
            if not settings.BROWSER_FALLBACK:
                raise
            from app.services.browser import fetch_dynamic_html
            return parse_product(await fetch_dynamic_html(url), url)
    except (ScrapingError, ValueError):
        raise
    except Exception as exc:
        raise ScrapingError("No se pudo consultar la tienda.") from exc


async def scrape_product(url):
    async with asyncio.timeout(55):
        return await scrape_product_url(url)
