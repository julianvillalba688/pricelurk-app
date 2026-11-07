from unittest.mock import AsyncMock, patch
import sys

import pytest
from playwright.async_api import Error

from app.services.browser import fetch_dynamic_html


async def test_real_chromium_blocks_secondary_private_and_unlisted_requests():
    # Chromium runs, but every admitted document is an offline fixture.
    document = b'''<html><head><title>Offline fixture</title></head><body>
    <script>fetch('http://127.0.0.1:8765/private').catch(() => {});</script>
    <script src="https://unlisted.example/attack.js"></script>
    <p id="fixture">Safe offline browser fixture</p></body></html>'''
    fetch = AsyncMock(return_value=(document, "https://amazon.com/fixture", "text/html"))
    with patch("app.services.browser.fetch_document", fetch):
        try:
            html = await fetch_dynamic_html("https://amazon.com/fixture")
        except Error as exc:
            if sys.platform == "linux" and ("Chromium sandboxing failed" in str(exc) or "No usable sandbox" in str(exc)):
                pytest.skip("Host does not support Chromium OS sandbox; fallback fails closed. Network routing unit tests still run.")
            raise
    assert "Safe offline browser fixture" in html
    assert fetch.call_count == 1
    assert fetch.call_args.args == ("https://amazon.com/fixture",)
