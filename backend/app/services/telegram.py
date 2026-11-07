import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def send_telegram(message: str) -> str:
    if not settings.telegram_enabled:
        return "disabled"
    # Never log request URLs or exceptions: Telegram embeds the token in the URL.
    async with httpx.AsyncClient(timeout=settings.TELEGRAM_TIMEOUT, trust_env=False, follow_redirects=False) as client:
        for attempt in range(settings.TELEGRAM_ATTEMPTS):
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": message[:4000]},
                )
                if response.status_code == 200 and response.json().get("ok") is True:
                    return "sent"
                # A 429 explicitly rejects delivery; wait a bounded delay before retrying.
                if response.status_code != 429:
                    return "failed"
            except (httpx.ConnectError, httpx.ConnectTimeout):
                pass  # No request delivered: safe, bounded retry.
            except (httpx.HTTPError, ValueError):
                return "unknown"  # Could have been delivered; don't send a duplicate.
            if attempt + 1 < settings.TELEGRAM_ATTEMPTS:
                await asyncio.sleep(min(2 ** attempt, 2))
    logger.warning("Telegram delivery attempts exhausted")
    return "failed"
