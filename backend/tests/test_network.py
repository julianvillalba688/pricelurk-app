from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import network
from app.services.browser import BrowserBudget, MAX_REQUESTS


def response(status=200, headers=None, chunks=None):
    result = MagicMock()
    result.status = status
    result.headers = headers or {}
    result.url = "https://amazon.com/item"
    result.__aenter__ = AsyncMock(return_value=result)
    result.__aexit__ = AsyncMock(return_value=False)
    async def stream(size):
        for chunk in chunks or [b"fixture"]:
            yield chunk
    result.content.iter_chunked = stream
    return result


async def test_redirect_rejected_before_request():
    client = MagicMock()
    client.get.return_value = response(302, {"Location": "http://169.254.169.254/latest/meta-data/"})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.network.aiohttp.ClientSession", return_value=client):
        with pytest.raises(network.UnsafeDestination):
            await network.fetch_document("https://amazon.com/item")
    assert client.get.call_count == 1
    assert client.get.call_args.kwargs["allow_redirects"] is False


async def test_redirect_loop_limited():
    client = MagicMock()
    client.get.return_value = response(302, {"Location": "/loop"})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.network.aiohttp.ClientSession", return_value=client):
        with pytest.raises(network.UnsafeDestination):
            await network.fetch_document("https://amazon.com/item")
    assert client.get.call_count == network.MAX_REDIRECTS + 1


async def test_response_size_limited():
    client = MagicMock()
    client.get.return_value = response(chunks=[b"x" * (network.MAX_BYTES + 1)])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.network.aiohttp.ClientSession", return_value=client):
        with pytest.raises(network.UnsafeDestination):
            await network.fetch_document("https://amazon.com/item")


async def test_compressed_response_rejected_before_reading():
    client = MagicMock()
    client.get.return_value = response(headers={"Content-Encoding": "gzip"})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.network.aiohttp.ClientSession", return_value=client) as factory:
        with pytest.raises(network.UnsafeDestination, match="comprimida"):
            await network.fetch_document("https://amazon.com/item")
        assert factory.call_args.kwargs["auto_decompress"] is False


async def test_connection_resolver_returns_only_validated_ips():
    with patch("app.services.network.resolve_addresses", AsyncMock(return_value=["1.1.1.1"])):
        assert (await network.PublicResolver().resolve("amazon.com", 443))[0]["host"] == "1.1.1.1"
    with patch("app.services.network.resolve_addresses", AsyncMock(return_value=["1.1.1.1", "192.168.1.1"])):
        with pytest.raises(network.UnsafeDestination):
            await network.PublicResolver().resolve("amazon.com", 443)


@pytest.mark.parametrize("url,kind,method", [("http://localhost/internal", "xhr", "GET"), ("https://evil.example/a", "script", "GET"), ("https://amazon.com/a", "image", "GET"), ("https://amazon.com/a", "fetch", "POST")])
async def test_browser_secondary_request_blocked(url, kind, method):
    route = MagicMock()
    route.request.url = url
    route.request.resource_type = kind
    route.request.method = method
    route.abort = AsyncMock()
    route.fulfill = AsyncMock()
    with patch("app.services.browser.fetch_document", AsyncMock()) as fetch:
        await BrowserBudget().handle(route)
    fetch.assert_not_called()
    route.abort.assert_awaited_once()


async def test_browser_uses_safe_transport_and_budget():
    route = MagicMock()
    route.request.url = "https://amazon.com/a"
    route.request.resource_type = "document"
    route.request.method = "GET"
    route.fulfill = AsyncMock()
    route.abort = AsyncMock()
    budget = BrowserBudget()
    with patch("app.services.browser.fetch_document", AsyncMock(return_value=(b"fixture", route.request.url, "text/html"))) as fetch:
        await budget.handle(route)
        route.fulfill.assert_awaited_once()
        budget.requests = MAX_REQUESTS
        await budget.handle(route)
        assert fetch.call_count == 1
    route.abort.assert_awaited_once()
