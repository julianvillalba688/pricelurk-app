"""Optional Chromium fallback. Chromium never opens store sockets directly.

All admitted requests are fulfilled through the same DNS-validating transport.
A dead proxy also blocks browser traffic outside interception (e.g. WebRTC).
"""
import asyncio

from playwright.async_api import async_playwright

from app.services.network import MAX_BYTES, fetch_document, validate_url

MAX_REQUESTS = 24
MAX_TOTAL_BYTES = 4 * 1024 * 1024
ALLOWED_TYPES = {"document", "script", "xhr", "fetch", "stylesheet"}


async def fetch_dynamic_html(url):
    validate_url(url)
    async with asyncio.timeout(30), async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, args=[
            "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
            "--disable-background-networking", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        ])
        try:
            context = await browser.new_context(service_workers="block", accept_downloads=False)
            await context.route_web_socket("**/*", lambda ws: ws.close())
            budget = BrowserBudget()
            await context.route("**/*", budget.handle)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1000)
            html = await page.content()
            if len(html.encode()) > MAX_TOTAL_BYTES:
                raise ValueError("Browser document exceeds budget")
            return html
        finally:
            await browser.close()


class BrowserBudget:
    def __init__(self):
        self.requests = 0
        self.bytes = 0
        self.lock = asyncio.Lock()

    async def handle(self, route):
        self.requests += 1
        if self.requests > MAX_REQUESTS or route.request.resource_type not in ALLOWED_TYPES or route.request.method != "GET":
            await route.abort()
            return
        try:
            validate_url(route.request.url)
            async with self.lock:
                remaining = MAX_TOTAL_BYTES - self.bytes
                if remaining <= 0:
                    raise ValueError("Resource budget exceeded")
                body, _, content_type = await fetch_document(route.request.url, max_bytes=min(MAX_BYTES, remaining))
                self.bytes += len(body)
                if self.bytes > MAX_TOTAL_BYTES:
                    raise ValueError("Resource budget exceeded")
                await route.fulfill(status=200, body=body, content_type=content_type,
                                    headers={"Content-Security-Policy": "worker-src 'none'; frame-src 'none'; object-src 'none'"})
        except Exception:
            await route.abort()
