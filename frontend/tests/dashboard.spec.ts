import { test, expect } from '@playwright/test';

const fixture = { id: 1, url: 'https://amazon.com/dp/fixture', title: 'Fixture de prueba', platform: 'amazon', current_price: '12.30', target_price: '10.00', currency: 'USD', target_currency: 'USD', is_active: true, source: 'observed' };
const status = { writes_enabled: true, demo: false, notifications_enabled: false };

test('connection failure is an error, never an empty list', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.abort('connectionrefused'));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('No se pudo conectar');
  await expect(page.getByText('Todavía no hay productos.')).not.toBeVisible();
});

test('explicit loading and empty state', async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/**', async route => {
    await gate;
    await route.fulfill({ json: route.request().url().endsWith('/status') ? status : [] });
  });
  await page.goto('/');
  await expect(page.getByText('Cargando productos…')).toBeVisible();
  release();
  await expect(page.getByText(/Todavía no hay productos/)).toBeVisible();
  await expect(page.getByText(/Notificaciones de Telegram deshabilitadas/)).toBeVisible();
});

test('add, list, history, refresh and delete through UI with mocked store data', async ({ page }) => {
  let products: typeof fixture[] = [];
  let observations = 1;
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/status')) return route.fulfill({ json: status });
    if (request.method() !== 'GET') expect(request.headers()['x-api-key']).toBe('fixture-access-key');
    if (path.endsWith('/track')) {
      expect(request.postDataJSON().target_price).toBe('10.00');
      expect(request.postDataJSON().currency).toBe('USD');
      products = [fixture];
      return route.fulfill({ json: fixture });
    }
    if (path.endsWith('/refresh')) { observations++; return route.fulfill({ json: fixture }); }
    if (path.endsWith('/history')) return route.fulfill({ json: { history: Array.from({ length: observations }, (_, i) => ({ id: i + 1, price: '12.30', currency: 'USD', source: 'observed', timestamp: `2026-11-0${i + 1}T12:00:00Z` })), stats: { lowest_price: '12.30', highest_price: '12.30', average_price: '12.30', currency: 'USD' }, excluded_legacy_count: 0, source: 'observed' } });
    if (request.method() === 'DELETE') { products = []; return route.fulfill({ json: {} }); }
    return route.fulfill({ json: products });
  });
  await page.goto('/');
  await page.getByLabel('Clave de escritura').fill('fixture-access-key');
  await page.getByRole('button', { name: 'Agregar producto', exact: true }).click();
  await page.getByLabel('URL del producto').fill(fixture.url);
  await page.getByLabel('Precio objetivo').fill('10.00');
  await page.getByRole('button', { name: 'Guardar producto' }).click();
  await expect(page.getByRole('button', { name: fixture.title, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ver historial' }).click();
  await expect(page.getByText('1 observaciones reales')).toBeVisible();
  await page.getByRole('button', { name: 'Actualizar precio' }).click();
  await expect(page.getByText('2 observaciones reales')).toBeVisible();
  await page.getByRole('button', { name: 'Eliminar', exact: true }).click();
  await expect(page.getByText(/Todavía no hay productos/)).toBeVisible();
});

test('read-only demo and history errors are explicit', async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = route.request().url();
    if (path.endsWith('/status')) return route.fulfill({ json: { ...status, demo: true, writes_enabled: false } });
    if (path.endsWith('/history')) return route.fulfill({ status: 500, json: { detail: 'internal fixture exception not for users' } });
    return route.fulfill({ json: [{ ...fixture, source: 'demo' }] });
  });
  await page.goto('/');
  await expect(page.getByText(/Modo DEMO: datos sintéticos/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Agregar producto', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Ver historial' }).click();
  await expect(page.getByRole('alert')).toContainText('No se pudo cargar el historial');
  await expect(page.getByText('internal fixture exception not for users')).not.toBeVisible();
});
