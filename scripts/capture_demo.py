"""Capture the running, explicitly labelled demo. No image generation or API mocks.

Start the README demo on port 8001 and frontend on 5174 (allow that CORS origin).
Run with backend's Python/Playwright from the repository root.
"""
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

output = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    page.goto("http://127.0.0.1:5174/", wait_until="networkidle")
    expect(page.get_by_text("Modo DEMO:", exact=False)).to_be_visible()
    page.get_by_role("button", name="Ver historial").first.click()
    expect(page.get_by_text("3 observaciones sintéticas (DEMO)", exact=True)).to_be_visible()
    page.locator(".recharts-line").wait_for()
    page.screenshot(path=str(output / "demo-desktop.png"), full_page=True, animations="disabled")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(output / "demo-mobile.png"), full_page=True, animations="disabled")
    browser.close()
print("Saved real browser captures of the labelled synthetic demo.")
