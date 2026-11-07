# Frontend de PriceLurk

Requiere Node 24. Consulta la [guía principal](../README.md) para arquitectura, API, configuración, límites de acceso y resultados de validación.

```sh
cp .env.example .env
npm ci
npm run dev
npm run lint
npm run build
npx playwright install chromium
npm test
```

`VITE_API_BASE_URL` es pública, incluye `/api/v1` y se fija durante el build. Nunca guardes claves de escritura ni Telegram en variables `VITE_*`. La clave de escritura se introduce en la interfaz y solo permanece en memoria. Las pruebas del navegador simulan la API sin tiendas ni mensajes reales.
