# Procedencia y dependencias

Se revisaron el historial original (cuatro commits de un mismo autor Git), los archivos fuente, manifests y archivos de licencia presentes. No había LICENSE ni avisos de código de aplicación de terceros. MIT se añade al código propio con la autorización del usuario; la revisión no certifica titularidad exclusiva ni despeja obligaciones contractuales desconocidas.

El proyecto usa dependencias instaladas mediante pip/npm, no código de tiendas copiado en los nuevos parsers. Cada dependencia conserva su licencia y avisos en su distribución. Entre las principales: FastAPI, SQLAlchemy, Pydantic y React (MIT), Celery (BSD), aiohttp (Apache-2.0), Playwright (Apache-2.0), psycopg2-binary (LGPL con excepciones, ver distribución), Vite y Recharts (MIT). Revisa también las transitivas de `requirements.txt` y `package-lock.json` antes de redistribuir binarios o imágenes; MIT del proyecto no reemplaza esos términos.

Los SVG de inicio React/Vite proceden del boilerplate de desarrollo y no se presentan como diseño propio. El PNG `frontend/src/assets/hero.png`, sin referencias en la interfaz ni atribución documentada, se retira de la distribución sin afirmar derechos sobre él. Los HTML de depuración de AliExpress y la base SQLite se retiran del árbol actual; continúan en el historial original. No se reasigna licencia a contenidos de tiendas, marcas ni datos históricos.

Las nuevas fixtures HTML/JSON y las muestras demo son ejemplos mínimos escritos para las pruebas; no son capturas de páginas de comercios ni evidencia de precios reales. Las capturas en `docs/screenshots` documentan una interfaz ejecutada con los datos explícitos que indica su leyenda.
