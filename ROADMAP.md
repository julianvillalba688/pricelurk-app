# Roadmap de PriceLurk

Estado de la rama de preparación BYOP. Implementación y validación se detallan por separado en [docs/VALIDATION.md](docs/VALIDATION.md).

## Implementado

- [x] API de seguimiento con escritura protegida por clave y modo solo lectura por defecto; sin nuevas cuentas ni datos personales.
- [x] Celery Beat, registro explícito de tareas, cola configurable y comandos para consumirla.
- [x] Transacciones/sesiones por producto y rollback ante fallos; los productos siguientes continúan.
- [x] Telegram opcional, timeouts, intentos limitados y reclamación atómica por episodio; estados ambiguos documentados.
- [x] Política de destinos por parser de URL y dominios; resolución DNS validada en el conector, redirecciones manuales y límites de descarga/tiempo.
- [x] Fallback Chromium opcional con transporte común, bloqueo de recursos secundarios no permitidos, WebSockets y service workers; límites de recursos.
- [x] Precios decimales con moneda explícita; rechazo de monedas ambiguas y de comparaciones entre divisas.
- [x] Migración no destructiva que conserva columnas originales, moneda desconocida y procedencia antigua no verificada.
- [x] Historial de observaciones sin puntos inventados; datos antiguos no verificables excluidos y conservados.
- [x] Demo explícita, fixtures fijos en base separada, sin escrituras públicas y rechazada en entorno production.
- [x] UI con carga, vacío, errores seguros, moneda y mensajes de Telegram/solo lectura/demo.
- [x] Instalación documentada con SQLite, PostgreSQL opcional, Redis, worker, Beat y frontend; dependencias fijadas y runtimes de CI actualizados.
- [x] README, MIT para código propio, revisión de procedencia y detección redactada de secretos en árbol e historial.
- [x] Pruebas de API, dinero, migración, redirecciones/DNS, aislamiento, alertas y navegador sin tiendas ni mensajes reales.

## Trabajo futuro justificado

- [ ] [Fixtures autorizadas y compatibilidad por tienda](https://github.com/julianvillalba688/pricelurk-app/issues/1): el extractor común no acredita compatibilidad con páginas actuales ni variantes de cada comercio. Ampliar solo sobre evidencia saneada, con pruebas de ambigüedad y moneda.
- [ ] [Estado y antigüedad del monitoreo](https://github.com/julianvillalba688/pricelurk-app/issues/2): la interfaz necesita distinguir un precio antiguo de un intento reciente fallido; el operador necesita consultar entregas fallidas/ambiguas sin exponer secretos.
- [ ] [Alojamiento y recuperación en staging](https://github.com/julianvillalba688/pricelurk-app/issues/3): hace falta una decisión de infraestructura persistente, pruebas de restauración, supervisión y validación del entorno hospedado antes de autorizar producción. Incluye habilitar el sandbox de Chromium si se quiere usar el fallback en Linux; Docker Desktop local lo rechazó y el código falla cerrado.

No se crea un sistema de cuentas ni se plantea un producto multiusuario como requisito de esta entrega. No se afirman despliegues, adopción, ingresos, propiedad exclusiva ni aprobación BYOP.

## Criterio de horas de BYOP

Hay mejoras concretas, pero **no se acredita una estimación validada de al menos 20 horas pendientes**. El alcance y esfuerzo deben acordarse con evidencia antes de presentarlo como requisito cumplido. No se inflan estimaciones ni se añade trabajo ficticio para alcanzar ese umbral. El titular debe revisar los criterios vigentes de BYOP y confirmar que el proyecto y el trabajo pendiente encajan antes de enviar su presentación.
