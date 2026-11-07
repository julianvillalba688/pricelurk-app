"""All store HTTP traffic uses a resolver that validates the actual connection IP.

No ambient proxies, automatic redirects or DNS check-then-reconnect race.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp
from aiohttp.abc import AbstractResolver

STORES = {
    "amazon.com": "amazon",
    "amazon.es": "amazon",
    "mercadolibre.com.co": "mercadolibre",
    "aliexpress.com": "aliexpress",
}
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


class UnsafeDestination(ValueError):
    pass


def validate_url(url: str) -> tuple[str, str]:
    if len(url) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise UnsafeDestination("URL inválida.")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("https", "http") or parsed.username is not None or parsed.password is not None:
            raise ValueError
        if parsed.port not in (None, 443 if parsed.scheme == "https" else 80):
            raise ValueError
        platform = next((value for domain, value in STORES.items() if host == domain or host.endswith("." + domain)), None)
        if not platform:
            raise ValueError
        host.encode("ascii")
    except (ValueError, UnicodeError) as exc:
        raise UnsafeDestination("Usa una URL HTTP(S) de una tienda admitida, sin credenciales ni puertos especiales.") from exc
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")), platform


async def resolve_addresses(host, port):
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list({info[4][0] for info in infos})


class PublicResolver(AbstractResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        addresses = await asyncio.wait_for(resolve_addresses(host, port), timeout=4)
        if not addresses:
            raise UnsafeDestination("Destino no resoluble.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global or (ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo)):
                raise UnsafeDestination("Destino de red no público.")
        return [{"hostname": host, "host": ip, "port": port,
                 "family": socket.AF_INET6 if ":" in ip else socket.AF_INET,
                 "proto": 0, "flags": socket.AI_NUMERICHOST} for ip in addresses]

    async def close(self):
        pass


async def fetch_document(url: str, max_bytes=MAX_BYTES) -> tuple[bytes, str, str]:
    """Limits include redirects, DNS, response bytes and total time.

    Require identity encoding: avoid decompressing a small compressed body into
    unbounded memory before the stream-size check can run.
    """
    async with asyncio.timeout(20):
        connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False, limit=2)
        async with aiohttp.ClientSession(connector=connector, trust_env=False, auto_decompress=False,
                                         timeout=aiohttp.ClientTimeout(total=10),
                                         headers={"User-Agent": "PriceLurk/1.0", "Accept-Encoding": "identity"}) as client:
            for hop in range(MAX_REDIRECTS + 1):
                url, _ = validate_url(url)
                async with client.get(url, allow_redirects=False) as response:
                    if response.status in (301, 302, 303, 307, 308):
                        if hop == MAX_REDIRECTS or "Location" not in response.headers:
                            raise UnsafeDestination("Demasiadas redirecciones.")
                        url, _ = validate_url(urljoin(url, response.headers["Location"]))
                        continue
                    response.raise_for_status()
                    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise UnsafeDestination("Respuesta comprimida no admitida.")
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise UnsafeDestination("Respuesta demasiado grande.")
                    return bytes(body), str(response.url), response.headers.get("Content-Type", "text/html")
    raise UnsafeDestination("No se pudo recuperar el documento.")
