import { expect, test } from '@playwright/test';

const runtimeEnv =
  (
    globalThis as {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env ?? {};

const E2E_EMAIL = runtimeEnv.E2E_EMAIL ?? 'admin@aquabloom.cl';
const E2E_PASSWORD = runtimeEnv.E2E_PASSWORD ?? 'AquaBloom2026!';

test('S3-24: El catálogo de staging muestra Panguipulli y su detalle', async ({ page }) => {
  await page.goto('/login');
  await page.fill('#login-email', E2E_EMAIL);
  await page.fill('#login-password', E2E_PASSWORD);

  await Promise.all([
    page.waitForURL('**/dashboard', { timeout: 15000 }),
    page.locator('button[type="submit"]').click(),
  ]);

  await page.goto('/lakes');
  await expect(page.getByRole('heading', { name: 'Listado de Lagos' })).toBeVisible({
    timeout: 15000,
  });

  const panguipulliRow = page.locator('.lake-row').filter({
    hasText: 'Panguipulli',
  });
  await expect(panguipulliRow).toBeVisible({ timeout: 15000 });

  await panguipulliRow.getByRole('button', { name: 'Ver detalle' }).click();
  await page.waitForURL(/\/lakes\/[^/]+$/);

  await expect(page.getByRole('heading', { name: 'Panguipulli' })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText('ID Catálogo')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Información' })).toBeVisible();
  await expect(page.getByText('Descripción')).toBeVisible();
  await expect(
    page
      .locator('section.card')
      .filter({ has: page.getByRole('heading', { name: 'Información' }) })
      .getByText(/Fuente disponible:/i),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Estaciones Asociadas' }),
  ).toBeVisible();

  const cartographicCanvas = page.locator('.maplibregl-canvas');
  if (await cartographicCanvas.count()) {
    await expect(cartographicCanvas).toBeVisible({ timeout: 20000 });
  } else {
    await expect(page.getByRole('status')).toContainText(
      'El mapa no está disponible',
    );
  }
});

