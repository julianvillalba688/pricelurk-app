import re
import json
import asyncio
import httpx
import logging
import traceback
from typing import Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from curl_cffi.requests import AsyncSession

logger = logging.getLogger("scraper")

class ScrapingError(Exception):
    """Excepción base para errores de scraping y red."""
    pass

class ProductNotFoundError(ScrapingError):
    """Excepción cuando el producto no existe o responde 404."""
    pass

class ParsingError(ScrapingError):
    """Excepción cuando falla la extracción de datos (título, precio)."""
    pass

from playwright.sync_api import sync_playwright

def _fetch_dynamic_html_sync(url: str) -> str:
    """Función interna síncrona para ejecutar Playwright sin depender del Event Loop de Uvicorn."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="es-CO",
        )
        # Ocultar la propiedad navigator.webdriver en JS
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        # Interceptar recursos pesados no requeridos
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2}",
            lambda route: route.abort(),
        )

        try:
            # 1. Esperar 'load' (todo cargado) en vez de solo domcontentloaded
            page.goto(url, wait_until="load", timeout=20000)

            # 2. Intentar esperar el precio explícitamente (hasta 6s)
            try:
                page.wait_for_selector(".andes-money-amount__integer", timeout=6000)
            except Exception:
                # Si no aparece el selector, esperar tiempo fijo
                page.wait_for_timeout(6000)

            content = page.content()
            return content
        except Exception as e:
            logger.error(
                f"[Playwright Error] Fallo al cargar {url} dinámicamente:"
                f" {str(e)}"
            )
            raise ParsingError(f"Error al cargar la página dinámica: {str(e)}")
        finally:
            browser.close()

async def fetch_dynamic_html(url: str) -> str:
    """Ejecuta Playwright en un hilo separado para evadir restricciones de asyncio en Windows."""
    return await asyncio.to_thread(_fetch_dynamic_html_sync, url)

async def fetch_html(url: str, is_mobile: bool = False) -> tuple[str, str, int]:
    """Realiza una petición GET asíncrona segura simulando un navegador real."""
    if is_mobile:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)"
                " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6"
                " Mobile/15E148 Safari/604.1"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-CO,es-419;q=0.9,es;q=0.8,en;q=0.7",
        }
        impersonate_target = "safari15_5"
    else:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-CO,es-419;q=0.9,es;q=0.8,en;q=0.7",
        }
        impersonate_target = "chrome120"

    try:
        async with AsyncSession(
            impersonate=impersonate_target, allow_redirects=True, timeout=15
        ) as session:
            response = await session.get(url, headers=headers)
            logger.info(
                f"[Scraper] Status {response.status_code} para URL: {url}"
            )

            if response.status_code == 404:
                raise ProductNotFoundError(f"Producto no encontrado (404): {url}")

            if response.status_code not in (200, 201):
                raise ScrapingError(
                    f"La tienda devolvió status HTTP {response.status_code}"
                )

            return response.text, str(response.url), response.status_code
    except ScrapingError:
        raise
    except Exception as e:
        logger.error(f"[Scraper] Error de red al consultar {url}: {str(e)}")
        raise ScrapingError(f"Error de conexión con la tienda: {str(e)}")

def clean_price(price_str: str) -> float:
    """Limpia cadenas de precios y retorna un float."""
    if not price_str:
        return 0.0
    # Remover símbolos de moneda y caracteres inválidos
    price_str = re.sub(r'[^\d.,]', '', price_str)
    
    # Manejar formatos comunes:
    # 1.250.000 -> 1250000
    # 1.250,00 -> 1250.00
    # 1,250.00 -> 1250.00
    # Identificar el separador decimal
    if ',' in price_str and '.' in price_str:
        if price_str.rfind(',') > price_str.rfind('.'):
            # Formato europeo/latam: 1.250,00
            price_str = price_str.replace('.', '').replace(',', '.')
        else:
            # Formato US: 1,250.00
            price_str = price_str.replace(',', '')
    elif ',' in price_str:
        # Solo tiene comas, pueden ser separadores de miles o decimal.
        # Si tiene 3 dígitos después de la coma (ej. 1,250), suele ser mil.
        parts = price_str.split(',')
        if len(parts[-1]) == 3 and len(parts) > 1:
            price_str = price_str.replace(',', '')
        else:
            price_str = price_str.replace(',', '.')
    elif '.' in price_str:
        # Solo tiene puntos
        if price_str.count('.') > 1:
            # 1.250.000 -> 1250000.0 o 4.599.99 -> 4599.99
            parts = price_str.rsplit('.', 1)
            if len(parts[1]) == 3:
                price_str = price_str.replace('.', '')
            else:
                price_str = parts[0].replace('.', '') + '.' + parts[1]
        else:
            parts = price_str.split('.')
            if len(parts[-1]) == 3 and len(parts) > 1:
                price_str = price_str.replace('.', '')
        
    try:
        return float(price_str)
    except ValueError:
        raise ParsingError(f"No se pudo parsear el precio: {price_str}")

def clean_text(text: str) -> str:
    """Limpia espacios y caracteres invisibles de un texto."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def clean_product_url(url: str) -> str:
    """Sanea URLs eliminando parámetros de rastreo manteniendo los IDs reales."""
    if not url:
        return url

    # Mercado Libre: preservar/extraer wid o item_id si existe en URLs de catálogo
    if "mercadolibre" in url.lower():
        # Buscar wid= o item_id= en query params Y en fragmento (#)
        # Patrón: wid=MCO... o item_id=MCO... (con = literal)
        wid_match = re.search(
            r'(?:wid|item_id)[=%](?:3D)?([A-Z]{3}\d+)', url, re.IGNORECASE
        )
        if wid_match:
            item_id = wid_match.group(1).upper()
            # Reconstruir URL canónica directa al artículo del vendedor
            return f"https://articulo.mercadolibre.com.co/{item_id[:3]}-{item_id[3:]}"

        # URLs /p/ de catálogo: limpiar AMBOS ? y # (el # causa login redirect en ML)
        if "/p/" in url:
            return url.split("?")[0].split("#")[0]

        # URLs /up/ de usuarios: retornar tal cual (wid se extraerá del raw URL en el parser)
        if "/up/" in url:
            return url

        item_match = re.search(r'(M[A-Z]{2})-?(\d{8,12})', url)
        if item_match:
            return f"https://articulo.mercadolibre.com.co/{item_match.group(1)}-{item_match.group(2)}"

        return url.split("?")[0]

    # AliExpress: Convertir a la estructura estándar /item/{id}.html
    if "aliexpress" in url.lower():
        match = re.search(r'/item/(\d+)\.html', url)
        if match:
            return f"https://es.aliexpress.com/item/{match.group(1)}.html"

    # Amazon: Convertir a formato canónico /dp/{ASIN}
    if "amazon" in url.lower():
        match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
        if match:
            return f"https://www.amazon.com/dp/{match.group(1)}"

    return url

async def _parse_mercadolibre(soup: BeautifulSoup, url: str, html: str = "", original_url: str = "") -> dict:
    title = None
    price = None
    image_url = None
    # Conservar la URL original para extraer wid= del fragmento (#)
    raw_url = original_url or url

    # --- 0. EXTRACCION RAPIDA POR API SI LA URL TIENE wid= EN EL FRAGMENTO ---
    # Para URLs /up/ el wid está en el fragmento (#...) no en los query params
    quick_id_match = re.search(r'(?:wid|item_id)[=]([A-Z]{3}\d+)', raw_url, re.IGNORECASE)
    catalog_match = re.search(r'/p/(M[A-Z]{2}\d+)', raw_url, re.IGNORECASE)

    if quick_id_match:
        quick_id = quick_id_match.group(1).upper()
        logger.warning(f"[ML-STEP0] wid={quick_id} detectado, consultando API...")
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
                res = await client.get(f"https://api.mercadolibre.com/items/{quick_id}", headers=headers)
                logger.warning(f"[ML-STEP0] API status={res.status_code}")
                if res.status_code == 200:
                    data = res.json()
                    logger.warning(
                        f"[ML-STEP0] price={data.get('price')} | base={data.get('base_price')} | "
                        f"orig={data.get('original_price')} | status={data.get('status')}"
                    )
                    title = data.get("title")
                    price = (
                        data.get("price")
                        or data.get("base_price")
                        or data.get("original_price")
                        or data.get("sale_price")
                    )
                    if not price and data.get("variations"):
                        for v in data.get("variations", []):
                            p = v.get("price")
                            if isinstance(p, (int, float)) and p > 0:
                                price = p
                                break
                    if not price:
                        logger.warning(f"[ML-STEP0] PRECIO NULO. Claves: {list(data.keys())[:20]}")
                    pics = data.get("pictures", [])
                    if pics:
                        image_url = pics[0].get("secure_url") or pics[0].get("url")
                    if title and price:
                        logger.warning(f"[ML-STEP0] OK: title={title} price={price}")
        except Exception as e:
            logger.warning(f"[ML-STEP0] Error: {e}")

    elif catalog_match:
        catalog_id = catalog_match.group(1).upper()
        logger.warning(f"[ML-STEP0] catalog_id={catalog_id} — consultando Search API pública...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                }
                # 1. Endpoint de búsqueda pública por catalog_product_id (no requiere auth)
                search_url = f"https://api.mercadolibre.com/sites/MCO/search?catalog_product_id={catalog_id}&limit=1"
                res = await client.get(search_url, headers=headers)
                logger.warning(f"[ML-STEP0] Search API status={res.status_code}")
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    logger.warning(f"[ML-STEP0] Search results count={len(results)}")
                    if results:
                        first = results[0]
                        title = title or first.get("title")
                        price = price or first.get("price")
                        logger.warning(f"[ML-STEP0] search OK: {title!r} @ {price}")
                        pics = first.get("thumbnail", "")
                        if pics and not image_url:
                            image_url = pics
                if not price:
                    # 2. Fallback: buscar por título usando el slug de la URL
                    slug_match = re.search(r'mercadolibre\.com\.co/([^/]+)/(?:p/|MCO)', url)
                    if slug_match:
                        slug = slug_match.group(1).replace("-", " ")
                        res2 = await client.get(
                            f"https://api.mercadolibre.com/sites/MCO/search?q={slug}&limit=1",
                            headers=headers,
                        )
                        if res2.status_code == 200:
                            data2 = res2.json()
                            results2 = data2.get("results", [])
                            logger.warning(f"[ML-STEP0] slug search results={len(results2)}")
                            if results2:
                                first2 = results2[0]
                                title = title or first2.get("title")
                                price = price or first2.get("price")
                                if not image_url:
                                    image_url = first2.get("thumbnail", "")
                                logger.warning(f"[ML-STEP0] slug search OK: {title!r} @ {price}")
        except Exception as e:
            logger.warning(f"[ML-STEP0] Search API Error: {e}")
    else:
        logger.warning(f"[ML-STEP0] Sin wid= ni /p/ en raw_url={raw_url[:80]}")


    # --- 1. EXTRACCIÓN BÁSICA DESDE HTML ESTÁTICO ---
    if html and (not title or not price):
        og_title_match = re.search(
            r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\'\n]+)["\']',
            html,
            re.IGNORECASE,
        )
        if og_title_match:
            full_og = og_title_match.group(1)
            logger.warning(f"[ML-STEP1] og:title encontrado: {full_og!r}")
            if " - $" in full_og:
                parts = full_og.rsplit(" - $", 1)
                title = title or parts[0].strip()
                price = price or clean_price(parts[1])
                logger.warning(f"[ML-STEP1] precio extraido de og:title: {price}")
            else:
                title = title or full_og.strip()
        else:
            # Buscar og:title con atributos en orden inverso
            og_title_match2 = re.search(
                r'<meta\s+content=["\']([^"\'\n]+)["\']\s+(?:property|name)=["\']og:title["\']',
                html, re.IGNORECASE
            )
            if og_title_match2:
                full_og = og_title_match2.group(1)
                logger.warning(f"[ML-STEP1] og:title (orden inverso): {full_og!r}")
                if " - $" in full_og:
                    parts = full_og.rsplit(" - $", 1)
                    title = title or parts[0].strip()
                    price = price or clean_price(parts[1])
            else:
                logger.warning(f"[ML-STEP1] og:title NO encontrado en HTML (len={len(html)})")

        if not title:
            title_tag_match = re.search(
                r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE
            )
            if title_tag_match:
                raw_title = title_tag_match.group(1)
                title = (
                    raw_title.split("|")[0]
                    .split("- Mercado")[0]
                    .split("- $")[0]
                    .strip()
                )

        og_img_match = re.search(
            r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\']([^"\'\n]+)["\']',
            html,
            re.IGNORECASE,
        )
        if og_img_match:
            image_url = image_url or og_img_match.group(1)

        # Buscar precio en el HTML: priorizar "localItemPrice" y "actual_price" antes de "price"
        if not price:
            # localItemPrice es el precio en moneda local (más confiable que "price" en USD)
            for pattern in [
                r'"localItemPrice"\s*:\s*(\d+(?:\.\d+)?)',
                r'"actual_price"\s*:\s*(\d+(?:\.\d+)?)',
                r'"price"\s*:\s*(\d+(?:\.\d+)?)',
            ]:
                p_matches = re.findall(pattern, html)
                for cand in p_matches:
                    try:
                        val = float(cand)
                        # Umbral: 100 COP mínimo (cubre productos baratos como vinilos)
                        if val > 100:
                            price = val
                            break
                    except ValueError:
                        pass
                if price:
                    break

    # --- 2. CONSULTA API REST SI FALTA ALGO ---
    if not title or not price:
        item_id = None
        # Buscar en URL limpia (puede ser articulo.mercadolibre.co/MCO-...)
        param_match = re.search(r'[?&#](?:wid|item_id)=([A-Z0-9]+)', raw_url, re.IGNORECASE)
        if param_match:
            item_id = param_match.group(1).upper()

        if not item_id:
            item_match = re.search(r'/(M[A-Z]{2})-(\d{8,12})', url)
            if item_match:
                item_id = f"{item_match.group(1)}{item_match.group(2)}"

        if item_id:
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
                    res = await client.get(f"https://api.mercadolibre.com/items/{item_id}", headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        logger.info(
                            f"[MercadoLibre API Step2] price={data.get('price')} "
                            f"base={data.get('base_price')} orig={data.get('original_price')}"
                        )
                        title = title or data.get("title")
                        price = price or (
                            data.get("price")
                            or data.get("base_price")
                            or data.get("original_price")
                        )
                        if not price and data.get("variations"):
                            for v in data.get("variations", []):
                                if v.get("price"):
                                    price = v.get("price")
                                    break
                        pics = data.get("pictures", [])
                        if pics and not image_url:
                            image_url = pics[0].get("secure_url") or pics[0].get("url")
            except Exception as e:
                logger.warning(f"[MercadoLibre API Error]: {e}")

    # --- 3. FALLBACK DINÁMICO A PLAYWRIGHT (GARANTÍA ABSOLUTA) ---
    if not title or not price:
        # Usar la URL canónica (articulo.mercadolibre.com.co/MCO-...) — funciona sin sesión
        playwright_url = url  # url es el cleaned_url (articulo.mercadolibre.com.co)
        logger.warning(f"[ML-STEP3] Lanzando Playwright en: {playwright_url[:100]}")
        try:
            dynamic_html = await fetch_dynamic_html(playwright_url)
            if dynamic_html:
                d_soup = BeautifulSoup(dynamic_html, "html.parser")

                # DIAGNÓSTICO: qué página cargó Playwright
                pw_title_el = d_soup.find("title")
                pw_page_title = pw_title_el.get_text(strip=True) if pw_title_el else "SIN TITULO"
                pw_body_text = d_soup.get_text()[:400].replace("\n", " ")
                logger.warning(f"[ML-STEP3] Página cargada: '{pw_page_title}'")
                logger.warning(f"[ML-STEP3] Texto (primeros 400 chars): {pw_body_text!r}")

                if not title:
                    t_el = d_soup.select_one(".ui-pdp-title") or d_soup.find("h1")
                    if t_el:
                        title = t_el.get_text(strip=True)
                    logger.warning(f"[ML-STEP3] title tras DOM: {title!r}")


                if not price:
                    # 3a. Selector Andes (entero + fracción)
                    p_whole = d_soup.select_one(".andes-money-amount__integer")
                    p_frac = d_soup.select_one(".andes-money-amount__fraction")
                    logger.warning(f"[ML-STEP3] andes integer={p_whole} fraction={p_frac}")
                    if p_whole:
                        parts_str = p_whole.get_text(strip=True)
                        if p_frac:
                            parts_str += "." + p_frac.get_text(strip=True)
                        price = clean_price(parts_str)

                    if not price:
                        # 3b. Texto visible con $ o COP
                        body_text = d_soup.get_text()
                        price_matches = re.findall(r'(?:\$\s*|COP\s*)([\d\.,]{3,12})', body_text)
                        logger.warning(f"[ML-STEP3] candidatos $texto: {price_matches[:5]}")
                        for p_cand in price_matches:
                            cleaned_p = clean_price(p_cand)
                            if cleaned_p and cleaned_p > 100:
                                price = cleaned_p
                                break

                    if not price:
                        # 3c. Regex sobre HTML dinámico (Nordic context renderizado)
                        for pattern in [
                            r'"localItemPrice"\s*:\s*(\d+)',
                            r'"actual_price"\s*:\s*(\d+)',
                            r'"price"\s*:\s*(\d+)',
                        ]:
                            p_matches = re.findall(pattern, dynamic_html)
                            for cand in p_matches:
                                val = float(cand)
                                if val > 100:
                                    price = val
                                    break
                            if price:
                                break

                    logger.warning(f"[ML-STEP3] price final tras Playwright: {price}")

                if not image_url:
                    img_el = d_soup.select_one("img.ui-pdp-image")
                    if img_el:
                        image_url = img_el.get("src")
        except Exception as e:
            logger.error(f"[ML-STEP3] Playwright Error: {e}")


    # --- 4. RETORNO Y LIMPIEZA ---
    if title and price:
        return {
            "title": clean_text(title),
            "price": clean_price(str(price)),
            "image_url": image_url or "",
            "platform": "mercadolibre",
            "url": url,
        }

    raise ParsingError(f"No se encontraron título ({bool(title)}) o precio ({bool(price)}) en MercadoLibre.")


async def _parse_amazon(soup: BeautifulSoup, url: str, response_text: str = "") -> Dict:
    title_tag_test = soup.select_one('title')
    title_test = title_tag_test.text if title_tag_test else ""
    logger.info(f"[_parse_amazon] Title extraido: {title_test}")
    
    blocked_keywords = ["captcha", "challenge-running", "pardon our interruption", "access denied", "robot check"]
    lower_text = response_text.lower()
    if any(kw in lower_text for kw in blocked_keywords):
        logger.warning(f"[_parse_amazon] Bloqueo Anti-Bot o CSR detectado en Amazon. Procediendo con fallback dinámico. URL: {url}")

    title = ""
    title_tag = soup.select_one('#productTitle') or soup.select_one('#title') or soup.find("meta", property="og:title")
    if title_tag:
        title = title_tag.text if hasattr(title_tag, 'text') else title_tag.get("content", "")

    price = 0.0
    price_whole = soup.select_one('.a-price-whole')
    if price_whole:
        fraction = soup.select_one('.a-price-fraction')
        price_str = price_whole.text.strip().strip('.')
        if fraction:
            price_str += f".{fraction.text.strip()}"
        price = clean_price(price_str)
    else:
        price_tag = soup.select_one('#priceblock_ourprice') or soup.select_one('#priceblock_dealprice') or soup.select_one('.a-offscreen')
        if price_tag:
            price = clean_price(price_tag.text)
        else:
            meta_price = soup.find("meta", property="og:price:amount")
            if meta_price:
                price = clean_price(meta_price.get("content", ""))

    img_url = ""
    img_tag = soup.select_one('#landingImage') or soup.select_one('#imgBlkFront') or soup.find("meta", property="og:image")
    if img_tag:
        img_url = img_tag.get("src") or img_tag.get("data-old-hires") or img_tag.get("content", "")

    # --- FALLBACK A PLAYWRIGHT PARA AMAZON ---
    if not title or not price:
        logger.info(f"[_parse_amazon] Faltan datos (Title: {bool(title)}, Price: {bool(price)}). Iniciando motor headless Playwright...")
        dynamic_html = await fetch_dynamic_html(url)
        dynamic_soup = BeautifulSoup(dynamic_html, "html.parser")
        
        if not title:
            title_tag_dyn = dynamic_soup.select_one('#productTitle') or dynamic_soup.select_one('#title') or dynamic_soup.find("meta", property="og:title")
            if title_tag_dyn:
                title = title_tag_dyn.text if hasattr(title_tag_dyn, 'text') else title_tag_dyn.get("content", "")
                
        if not price:
            price_tag_dyn = (
                dynamic_soup.select_one('#corePrice_feature_div .a-price-whole')
                or dynamic_soup.select_one('#priceblock_ourprice')
                or dynamic_soup.select_one('#priceblock_dealprice')
                or dynamic_soup.select_one('#price_inside_buybox')
                or dynamic_soup.select_one('.a-price .a-offscreen')
                or dynamic_soup.select_one('.a-price-whole')
            )
            if price_tag_dyn:
                price = clean_price(price_tag_dyn.text)

    if not title or not price:
        raise ParsingError("No se encontraron título o precio en Amazon incluso con Playwright.")

    return {
        "title": clean_text(title),
        "price": price,
        "image_url": img_url,
        "platform": "amazon",
        "url": url
    }

async def _parse_aliexpress(soup: BeautifulSoup, url: str, response_text: str = "") -> Dict:
    title = None
    price = None
    image_url = None
    dynamic_soup = None

    # Anti-bot check
    blocked_keywords = ["captcha", "challenge-running", "pardon our interruption", "access denied", "robot check"]
    lower_text = response_text.lower()
    if any(kw in lower_text for kw in blocked_keywords):
        logger.error(f"[_parse_aliexpress] Bloqueo Anti-Bot detectado en AliExpress. URL: {url}")
        raise ParsingError("Bloqueo Anti-Bot detectado en la plataforma")

    # --- 1. INTENTO VÍA JSON-LD SCHEMA.ORG ---
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            if script.string:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    title = data.get("name")
                    image_url = data.get("image")
                    offers = data.get("offers", {})
                    if isinstance(offers, dict):
                        price = offers.get("price") or offers.get("lowPrice")
                    elif isinstance(offers, list) and len(offers) > 0:
                        price = offers[0].get("price")
                    if title and price:
                        break
        except Exception:
            continue

    # --- 2. INTENTO VÍA REGEX EN SCRIPTS INLINE (AEP / RUNPARAMS) ---
    if not price or not title:
        # Buscar patrones comunes donde AliExpress guarda los datos en JS
        patterns = [
            r'window\.__AEP_DATA__\s*=\s*(\{.*?\});',
            r'window\.runParams\s*=\s*(\{.*?\});',
            r'_init_data_\s*=\s*(\{.*?\});',
            r'"priceModule":\s*(\{.*?\})\s*,\s*"',
        ]
        for pattern in patterns:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                js_text = match.group(0)
                # Extraer montos con formato numérico dentro del bloque JS
                price_match = re.search(
                    r'(?:formatedPrice|formattedAmount|actMinPrice|minPrice|maxPrice)"\s*:\s*"([^"]+)"',
                    js_text,
                )
                if price_match and not price:
                    price = price_match.group(1)

                title_match = re.search(
                    r'(?:subject|title|productTitle)"\s*:\s*"([^"]+)"', js_text
                )
                if title_match and not title:
                    title = title_match.group(1)

                if price and title:
                    break

    # --- 3. INTENTO VÍA META TAGS (OPEN GRAPH / TWITTER) ---
    if not title:
        og_title = (
            soup.find("meta", property="og:title")
            or soup.find("meta", attrs={"name": "twitter:title"})
            or soup.find("title")
        )
        if og_title:
            title = (
                og_title.get("content")
                or og_title.text
                or og_title.string
            )

    if not price:
        og_price = (
            soup.find("meta", property="og:price:amount")
            or soup.find("meta", property="product:price:amount")
            or soup.find("meta", attrs={"name": "twitter:data1"})
        )
        if og_price and og_price.get("content"):
            price = og_price["content"]

    if not image_url:
        og_image = soup.find("meta", property="og:image") or soup.find(
            "meta", attrs={"name": "twitter:image"}
        )
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

    # --- 4. FALLBACK A PLAYWRIGHT PARA ALIEXPRESS ---
    if not price:
        logger.info(f"[_parse_aliexpress] Faltan datos, posible CSR o bloqueo (Title: {bool(title)}, Price: {bool(price)}). Iniciando motor headless Playwright...")
        dynamic_html = await fetch_dynamic_html(url)
        dynamic_soup = BeautifulSoup(dynamic_html, "html.parser")
        
        # Buscar precio con selectores CSS en el DOM dinámico
        price_tag_dyn = (
            dynamic_soup.select_one('.product-price-current') 
            or dynamic_soup.select_one('.current-price')
            or dynamic_soup.select_one('.price--currentPriceText--V8_y_b5')
        )
        if price_tag_dyn:
            price = price_tag_dyn.text.strip()
            
        if not price:
            # Buscar en metadatos re-inyectados o regex de JS del DOM dinámico
            price_match = re.search(r'(?:formatedPrice|formattedAmount|actMinPrice|minPrice|maxPrice)"\s*:\s*"([^"]+)"', dynamic_html)
            if price_match:
                price = price_match.group(1)

            if not price:
                # Búsqueda por selectores que contengan "price" en sus clases
                price_elements = dynamic_soup.select(
                    '[class*="price"], [class*="Price"], .pdp-price-current'
                )
                for el in price_elements:
                    text = el.get_text(strip=True)
                    # Buscar patrones tipo "$ 12.345", "US $4.50", "12.34"
                    match = re.search(
                        r'(?:US\s*\$|\$|\bCOP\b)?\s*([\d\.,]{2,10})', text
                    )
                    if match and any(char.isdigit() for char in match.group(1)):
                        # Evitar tomar porcentajes de descuento como -50%
                        if "%" not in text and len(text) < 30:
                            price = match.group(0)
                            break

        if not title:
            title_tag_dyn = (
                dynamic_soup.select_one('[data-pl="product-title"]') 
                or dynamic_soup.select_one('.title--wrap--sUB0Hn6 h1')
                or dynamic_soup.select_one('.product-title-text')
            )
            if title_tag_dyn:
                title = title_tag_dyn.text.strip()
                
        if not image_url:
            img_tag_dyn = (
                dynamic_soup.select_one('.image-viewer--wrap--3zXw8J3 img')
                or dynamic_soup.select_one('.magnifier-image')
            )
            if img_tag_dyn:
                image_url = img_tag_dyn.get("src") or img_tag_dyn.get("data-src", "")

        if not price and 'dynamic_soup' in locals():
            # Extraer todo el texto renderizado
            body_text = dynamic_soup.get_text()
            # Buscar patrones de precios comunes
            price_matches = re.findall(
                r'(?:US\s*\$|\$|\bCOP\b)\s*([\d\.,]{2,10})', body_text
            )
            for p_candidate in price_matches:
                cleaned_p = clean_price(p_candidate)
                if cleaned_p and cleaned_p > 0:
                    price = cleaned_p
                    break

    # Limpieza final
    if title and price:
        return {
            "title": clean_text(title),
            "price": clean_price(str(price)),
            "image_url": image_url or "",
            "platform": "aliexpress",
            "url": url,
        }

    logger.error(
        f"[AliExpress Parser Error] Title: '{title}', Price: '{price}', URL: {url}"
    )
    raise ParsingError("No se encontraron título o precio en AliExpress.")

def _parse_generic(soup: BeautifulSoup, url: str) -> Dict:
    title = ""
    title_tag = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"}) or soup.find("title")
    if title_tag:
        title = title_tag.get("content", "") if title_tag.name == "meta" else title_tag.text

    price = 0.0
    price_tag = soup.find("meta", property="og:price:amount") or soup.find("meta", property="product:price:amount") or soup.find("meta", attrs={"name": "price"})
    if price_tag:
        price = clean_price(price_tag.get("content", ""))
    else:
        # Intento regex básico en el texto
        match = re.search(r'(?:precio|price)[\s:]*[\$€]?\s*([\d.,]+)', soup.text, re.IGNORECASE)
        if match:
            price = clean_price(match.group(1))

    img_url = ""
    img_tag = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
    if img_tag:
        img_url = img_tag.get("content", "")

    if not title:
        title = "Producto Genérico"
    if not price:
        raise ParsingError("No se pudo extraer precio de la página genérica.")

    return {
        "title": clean_text(title),
        "price": price,
        "image_url": img_url,
        "platform": "generic",
        "url": url
    }

async def scrape_product_url(url: str) -> dict:
    """Punto de entrada principal para scraping de cualquier tienda soportada."""
    cleaned_url = clean_product_url(url)
    logger.info(
        f"[Scraper] URL original: {url} -> URL sanitizada: {cleaned_url}"
    )

    try:
        if "aliexpress" in cleaned_url.lower():
            html, final_url, status_code = await fetch_html(cleaned_url)
            soup = BeautifulSoup(html, "html.parser")
            return await _parse_aliexpress(soup, cleaned_url, html)
        elif "amazon" in cleaned_url.lower():
            html, final_url, status_code = await fetch_html(cleaned_url)
            soup = BeautifulSoup(html, "html.parser")
            return await _parse_amazon(soup, cleaned_url, html)
        elif "mercadolibre" in cleaned_url.lower() or "mercadolibre" in url.lower():
            html, final_url, status_code = await fetch_html(cleaned_url)
            soup = BeautifulSoup(html, "html.parser")
            return await _parse_mercadolibre(soup, cleaned_url, html, original_url=url)
        else:
            html, final_url, status_code = await fetch_html(cleaned_url)
            soup = BeautifulSoup(html, "html.parser")
            return _parse_generic(soup, cleaned_url)

    except ScrapingError:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(
            f"[Scraper Fatal Error] Fallo en {cleaned_url}:\n{error_details}"
        )
        err_msg = str(e) if str(e) else type(e).__name__
        raise ParsingError(
            f"No se pudo extraer la información del producto ({err_msg})."
        )

# Alias para compatibilidad con código existente
scrape_product = scrape_product_url
