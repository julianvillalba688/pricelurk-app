import pytest
from unittest.mock import patch, AsyncMock
from app.services.scraper import (
    clean_price,
    scrape_product_url,
    ProductNotFoundError,
    ParsingError,
    ScrapingError
)

# --- Test para helpers (clean_price) ---

@pytest.mark.parametrize("price_str, expected", [
    ("$ 1.250.000", 1250000.0),
    ("1,250.00 USD", 1250.0),
    ("1250000.00", 1250000.0),
    ("$45.990,00", 45990.0),
    ("99,99", 99.99),
    ("1,250", 1250.0),
    ("1.250", 1250.0),
    ("1.250,99", 1250.99),
    ("1,250.99", 1250.99),
    ("12345", 12345.0),
    ("", 0.0),
    (None, 0.0)
])
def test_clean_price_formats(price_str, expected):
    assert clean_price(price_str) == expected

def test_clean_price_invalid():
    with pytest.raises(ParsingError):
        clean_price("invalid price")

# --- Fixtures HTML Mock ---

HTML_MERCADOLIBRE = """
<html>
  <head>
    <meta property="og:image" content="https://mlb-s2-p.mlstatic.com/mock_image.jpg">
  </head>
  <body>
    <h1 class="ui-pdp-title">iPhone 14 Pro Max 256 GB</h1>
    <div class="ui-pdp-price__second-line">
      <span class="andes-money-amount__fraction">4.599</span>
      <span class="andes-money-amount__cents">99</span>
    </div>
  </body>
</html>
"""

HTML_AMAZON = """
<html>
  <body>
    <span id="productTitle">Sony WH-1000XM5</span>
    <span class="a-price-whole">348.</span>
    <span class="a-price-fraction">00</span>
    <img id="landingImage" src="https://m.media-amazon.com/images/mock.jpg" />
  </body>
</html>
"""

HTML_GENERIC = """
<html>
  <head>
    <meta property="og:title" content="Monitor LG 24 Pulgadas">
    <meta property="og:price:amount" content="149.99">
    <meta property="og:image" content="https://example.com/monitor.jpg">
  </head>
</html>
"""

HTML_ALIEXPRESS = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Teclado Mecanico AliExpress",
        "image": "https://ae01.alicdn.com/kf/mock.jpg",
        "offers": {
          "@type": "Offer",
          "price": "45.99",
          "priceCurrency": "USD"
        }
      }
    </script>
  </head>
  <body></body>
</html>
"""

MOCK_ML_API_RESPONSE = """
{
  "id": "MCO1902404845",
  "title": "Producto ML de Catalogo",
  "price": 120000,
  "thumbnail": "https://http2.mlstatic.com/mock.jpg"
}
"""

HTML_INVALID = """
<html>
  <body>
    <h1>Solo un titulo, sin precio</h1>
  </body>
</html>
"""

class MockCurlResponse:
    def __init__(self, status_code, text, url=""):
        self.status_code = status_code
        self.text = text
        self.url = url
        
    def json(self):
        import json
        return json.loads(self.text)

# --- Test para Scraper Principal ---

@pytest.mark.asyncio
async def test_scrape_mercadolibre():
    url = "https://articulo.mercadolibre.com.co/MCO-mock"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockCurlResponse(200, HTML_MERCADOLIBRE, url)
        result = await scrape_product_url(url)
    
    assert result["platform"] == "mercadolibre"
    assert result["title"] == "iPhone 14 Pro Max 256 GB"
    assert result["price"] == 4599.99
    assert result["image_url"] == "https://mlb-s2-p.mlstatic.com/mock_image.jpg"
    assert result["url"] == url

@pytest.mark.asyncio
async def test_scrape_amazon():
    url = "https://www.amazon.com/dp/B09XS7JWHH"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockCurlResponse(200, HTML_AMAZON, url)
        result = await scrape_product_url(url)
    
    assert result["platform"] == "amazon"
    assert result["title"] == "Sony WH-1000XM5"
    assert result["price"] == 348.0
    assert result["image_url"] == "https://m.media-amazon.com/images/mock.jpg"

@pytest.mark.asyncio
async def test_scrape_generic():
    url = "https://www.tienda-desconocida.com/producto"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockCurlResponse(200, HTML_GENERIC, url)
        result = await scrape_product_url(url)
    
    assert result["platform"] == "generic"
    assert result["title"] == "Monitor LG 24 Pulgadas"
    assert result["price"] == 149.99
    assert result["image_url"] == "https://example.com/monitor.jpg"

@pytest.mark.asyncio
async def test_product_not_found():
    url = "https://www.amazon.com/dp/INVALID"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockCurlResponse(404, "Not found", url)
        with pytest.raises(ProductNotFoundError):
            await scrape_product_url(url)

@pytest.mark.asyncio
async def test_parsing_error():
    url = "https://www.amazon.com/dp/BROKEN"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockCurlResponse(200, HTML_INVALID, url)
        with pytest.raises(ParsingError):
            await scrape_product_url(url)

@pytest.mark.asyncio
async def test_http_network_error():
    url = "https://www.amazon.com/dp/TIMEOUT"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Timeout")
        with pytest.raises(ScrapingError):
            await scrape_product_url(url)

@pytest.mark.asyncio
async def test_scrape_mercadolibre_catalog():
    url = "https://www.mercadolibre.com.co/p/MCO65018896?pdp_filters=item_id%3AMCO1902404845"
    api_url = "https://api.mercadolibre.com/items/MCO1902404845"
    
    async def side_effect(target_url, *args, **kwargs):
        if target_url == api_url:
            return MockCurlResponse(200, MOCK_ML_API_RESPONSE, target_url)
        return MockCurlResponse(200, "<html></html>", target_url)

    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = side_effect
        result = await scrape_product_url(url)
    
    assert result["platform"] == "mercadolibre"
    assert result["title"] == "Producto ML de Catalogo"
    assert result["price"] == 120000.0
    assert result["image_url"] == "https://http2.mlstatic.com/mock.jpg"

@pytest.mark.asyncio
async def test_scrape_aliexpress():
    url = "https://es.aliexpress.com/item/1005001234.html"
    with patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockCurlResponse(200, HTML_ALIEXPRESS, url)
        result = await scrape_product_url(url)
    
    assert result["platform"] == "aliexpress"
    assert result["title"] == "Teclado Mecanico AliExpress"
    assert result["price"] == 45.99
    assert result["image_url"] == "https://ae01.alicdn.com/kf/mock.jpg"
