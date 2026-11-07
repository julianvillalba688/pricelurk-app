# Validación de la preparación BYOP

Revisión local: 7 de noviembre de 2026. No se envió ningún formulario BYOP, no se desplegó a producción y no se hizo merge.

## Resultados ejecutados

| Comprobación | Resultado observado |
| --- | --- |
| Instalación nativa | Entorno virtual Python 3.14.7, instalación pip y `pip check` sin dependencias rotas; Node 24 y `npm ci`. |
| Backend Windows | `python -m pytest --cov=app --cov-fail-under=80 -q`: **76 aprobadas**, **90,89 %** de cobertura; incluye Chromium real con sandbox y documentos simulados. |
| Backend Linux en contenedor limpio | Mismos archivos de aplicación/pruebas montados sobre la imagen construida desde requirements: **75 aprobadas, 1 omitida**. Se omite únicamente el arranque del navegador cuando el host rechaza su sandbox; no se desactiva el sandbox para pasar la prueba. |
| Lint Python | `ruff check app tests ../scripts`: aprobado. |
| Frontend | `npm run lint` y `npm run build`: aprobados; bundle dividido para cargar la gráfica bajo demanda. |
| Navegador frontend | `npm test`: **5 aprobadas** en Chromium, con API simulada; carga/vacío, conexión fallida, demo/errores de historial, flujo completo y preservación de centavos en importes grandes. |
| Dependencias frontend | `npm audit` tras actualizar lock: sin vulnerabilidades informadas en esa consulta; no es garantía futura. |
| Docker Compose | Construcción desde las dependencias fijadas y arranque de API, frontend, Redis, worker y Beat. API/Redis saludables; frontend HTTP 200; API informa escritura y Telegram deshabilitados por defecto. `pip check` dentro del worker aprobado. |
| Cola real y Beat | Configuración temporal `CELERY_QUEUE=readiness-queue`, intervalo 60 s. Se comprobaron registro de tarea, cola consumida y dos publicaciones/recepciones/ejecuciones satisfactorias consecutivas. Base vacía: `updated=0, failed=0`, sin tiendas ni mensajes. Después se restauró `main-queue` e intervalo de una hora. |
| SQLite anterior | `scripts/check_legacy_copy.py`: copia privada de la base original migrada dos veces, 0 usuarios, 5 productos, 5 snapshots y 0 alertas conservados; monedas NULL y procedencia no verificada. Hash del archivo original sin cambios. |
| PostgreSQL real | PostgreSQL 17 del overlay local; `scripts/check_postgres.py` en un esquema aleatorio desechable. Migración de floats heredados, segunda ejecución idempotente, moneda desconocida y persistencia decimal exacta aprobadas. El esquema de fixtures se eliminó al terminar. |
| Secretos | `detect-secrets 1.5.0`, sin verificación por red, árbol actual y las cuatro revisiones originales; repetido al preparar commits. Solo candidatos conocidos de ejemplo/fixture. No se imprimieron valores ni se agregaron reportes con candidatos al repositorio. |
| Git | Copia inicialmente limpia, identidad Git preexistente conservada; rama `feat/byop-readiness`, historial original mantenido. Push verificado contra el SHA remoto y [PR #4 abierto hacia main](https://github.com/julianvillalba688/pricelurk-app/pull/4), sin merge. |
| GitHub Actions remoto | En `85d5eb4`, [backend](https://github.com/julianvillalba688/pricelurk-app/actions/runs/42420107286) y [frontend](https://github.com/julianvillalba688/pricelurk-app/actions/runs/42420107289) terminaron antes de ejecutar pasos: las anotaciones indican una restricción administrativa de la cuenta. No son pruebas ejecutadas ni aprobadas remotamente. El titular debe resolver esa restricción y volver a lanzarlas. |
| Preview automática | La integración Vercel existente recibió el push de `85d5eb4` y marcó su [check](https://vercel.com/julianvillalba688s-projects/pricelurk-app/7RxSLLiJA7t6u4ijsmVoJ55HfJsW) como completado. La API de deployments de GitHub la registra como `Preview`, `production_environment=false`. No se validó su flujo funcional ni se ordenó un despliegue manual. |

La suite backend comprueba precios/monedas, almacenamiento exacto, migración, UTC en historial, exclusión de datos antiguos, atomicidad del alta, errores sin detalles internos, escrituras cerradas, demo separada, registro/cola/Beat, fallo por producto, rollback tras un flush, deduplicación y rearme de alertas, Telegram deshabilitado, reintentos limitados y entrega ambigua. Las pruebas de red comprueban esquemas, hosts, puertos, credenciales en URL, IP públicas/privadas/mixtas, redirecciones, tamaño y compresión de respuesta y peticiones secundarias del navegador. No intentan verificar una tienda real.

El flujo agregar → listar → actualizar → historial → eliminar se ejecutó tanto contra FastAPI/SQLite temporal con scraper simulado como desde la interfaz con una API simulada. La eliminación deja el historial y las observaciones conservadas. Estos resultados no equivalen a una prueba de comercios en vivo o de una instalación hospedada.

## Línea base y correcciones de instalación

Al clonar no estaban instaladas las dependencias: pytest, tsc y oxlint no podían arrancar. Tras instalarlas, el frontend original pasaba lint/build; el backend original obtuvo 18 aprobadas y 3 fallidas al bloquear navegador y salidas no simuladas. Había pruebas que asumían moneda por símbolos o aceptaban tiendas genéricas; se actualizaron al contrato que exige moneda explícita, destinos permitidos y fixtures sin red real. La auditoría inicial frontend informó siete vulnerabilidades altas; el lock actualizado no las informó en la consulta final.

La verificación real de PostgreSQL detectó que SQLAlchemy 2.1 selecciona psycopg3 para una URL genérica, mientras el proyecto instala psycopg2. Se corrigió con URLs explícitas `postgresql+psycopg2://` en Compose y normalización de URLs heredadas, con una prueba de regresión. No se dio por aprobado PostgreSQL antes de repetir el ensayo.

La revisión final también detectó pérdida de centavos al convertir importes grandes a `Number` para etiquetarlos. Una prueba de navegador reprodujo el fallo antes del arreglo; ahora las etiquetas usan `BigInt` y la fracción decimal de la API. Las coordenadas de la gráfica siguen siendo una aproximación visual sin intervenir en estadísticas o alertas. Una reinstalación inicial de npm en Windows encontró una DLL bloqueada por el Vite de la demo; tras detener ese proceso, `npm ci`, lint, build y las cinco pruebas pasaron.

## Capturas reales

Las imágenes se obtuvieron con `scripts/capture_demo.py`, desde una API y un frontend ejecutándose localmente, sin interceptar sus respuestas. La base `pricelurk-demo.db` se creó mediante el comando explícito de demo. Sus dos productos y seis registros son **fixtures sintéticos**, no precios ni observaciones de tiendas. La interfaz los rotula, muestra solo lectura y deshabilita Telegram.

- [Escritorio, 1440 px](screenshots/demo-desktop.png).
- [Móvil, 390 px](screenshots/demo-mobile.png).

Ambas capturas fueron inspeccionadas visualmente. No son imágenes generadas ni evidencia de uso por clientes.

## Límites y comprobaciones pendientes

- **Sandbox Chromium en Docker Desktop:** un ensayo explícito con `chromium_sandbox=True` falló por falta de sandbox utilizable en ese kernel/política. El código lo exige y falla cerrado. El fallback está apagado por defecto; su habilitación en Linux exige un entorno compatible, pendiente de la issue de alojamiento. La prueba con sandbox sí pasó en Windows; los controles de rutas/recursos se probaron también en Linux.
- **Tiendas en vivo:** no consultadas. No se certifican selectores, anti-bot, disponibilidad ni precios actuales de Amazon, Mercado Libre o AliExpress. Solo metadatos inequívocos de fixtures y límites de red comprobados.
- **Telegram real:** no se configuró un bot real ni se enviaron mensajes. Se simularon éxito, rechazo, 429, fallo de conexión y timeout ambiguo. No se promete entrega exactamente una vez ante caída entre reclamación y envío.
- **Vercel:** revisión estática con documentación oficial de [configuración](https://vercel.com/docs/services/config-reference), [routing](https://vercel.com/docs/services/routing) y [servicios/procesos continuos](https://vercel.com/docs/services). La Preview automática descrita arriba no equivale a una validación funcional: no se aprovisionaron manualmente servicios hospedados ni se afirma que el proyecto completo funcione allí. Redis, base durable y worker/Beat requieren decisión y ensayo de alojamiento. No se desplegó a producción.
- **Multiusuario:** no existe. Lecturas compartidas, clave única para escrituras y modo público de solo lectura; no hay cuentas nuevas. Los datos privados no deben publicarse en esa lista.
- **Secretos y titularidad:** el escaneo señaló Basic Auth en `backend/.env.example:1` en las revisiones originales y en una URL de rechazo de `backend/tests/test_readiness.py:22`; son placeholders/fixtures conocidos. No se detectaron credenciales potencialmente reales en ese análisis, pero el detector puede omitir secretos. No hubo revocaciones ni reescrituras de historial. La revisión de autoría/licencias tampoco certifica derechos contractuales desconocidos.
- **Avisos:** Starlette emite una advertencia de deprecación sobre su adaptador TestClient con httpx; no fue un fallo de ejecución. No se migró a otra API de pruebas como parte de esta entrega.
- **BYOP:** no se verificó elegibilidad ni aceptación y no se acredita una estimación validada de al menos 20 horas futuras. Los tres pendientes reales tienen problema, alcance y aceptación en [ROADMAP.md](../ROADMAP.md).

La construcción Docker siguió la ruta Compose del README con ejemplos de configuración, sin depender de la SQLite antigua versionada. La instalación nativa también se ejercitó con demo aislada y migración de una copia. No se comprobó transferencia de datos entre SQLite y PostgreSQL ni restauración de backups en alojamiento remoto.
