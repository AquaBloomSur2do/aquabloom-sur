import { test, expect } from '@playwright/test';

test('S2-088: Flujo E2E - Login, Catálogo, Mapa y Limpieza', async ({ page }) => {
  page.on('dialog', dialog => dialog.accept());

  // ==========================================
  // 1. LOGIN SEGURO Y ESPERA DE RED
  // ==========================================
  await page.goto('/login');
  
  const loginResponse = page.waitForResponse(response => 
    response.url().includes('token') && response.status() === 200
  );
  
  // CORRECCIÓN: Usar locators de accesibilidad (getByLabel/getByRole) en lugar de IDs frágiles
  await page.getByLabel('Correo Electrónico').fill('admin@aquabloom.cl'); 
  await page.getByLabel('Contraseña').fill('AquaBloom2026!');
  await page.getByRole('button', { name: 'Ingresar' }).click();
  
  await loginResponse;

  // ==========================================
  // 2. DASHBOARD Y NAVEGACIÓN LATERAL
  // ==========================================
  await page.waitForURL('**/dashboard', { timeout: 15000 });
  await expect(page.locator('h1', { hasText: 'Dashboard General' })).toBeVisible({ timeout: 10000 });

  // NAVEGACIÓN SEGURA: Usamos el enlace del Sidebar
  await page.locator('nav a', { hasText: 'Catálogo de Lagos' }).click();
  
  // FIX: Ajustamos el texto esperado del H1 según el snapshot del DOM
  await expect(page.locator('h1', { hasText: 'Listado de Lagos' })).toBeVisible({ timeout: 15000 });

  // ==========================================
  // 3. CREACIÓN DEL LAGO
  // ==========================================
  const lakeName = `Lago E2E Test ${Date.now()}`;
  await page.locator('text="+ Registrar Lago"').click();
  
  await page.waitForSelector('#lake-name', { state: 'visible', timeout: 10000 });
  await page.fill('#lake-name', lakeName);
  await page.fill('#lake-region', 'Los Lagos (E2E)'); 
  
  const testGeoJSON = JSON.stringify({
    "type": "Polygon",
    "coordinates": [[[-72.3, -39.8], [-72.2, -39.8], [-72.2, -39.9], [-72.3, -39.9], [-72.3, -39.8]]]
  });
  await page.fill('#lake-geojson', testGeoJSON);
  
  const createResponse = page.waitForResponse(response => 
    response.url().includes('/lakes') && response.request().method() === 'POST' && (response.status() === 201 || response.status() === 200)
  );
  await page.locator('button[type="submit"]').click();
  await createResponse;

  // ==========================================
  // 4. VALIDACIÓN EN CATÁLOGO Y DETALLES
  // ==========================================
  await page.waitForURL('**/lakes', { timeout: 15000 });
  
  const lakeRow = page.locator('tr').filter({ hasText: lakeName });
  await expect(lakeRow).toBeVisible({ timeout: 15000 });
  
  await lakeRow.locator('a', { hasText: 'Ver Detalles' }).click();
  
  // ==========================================
  // 5. EDICIÓN DEL LAGO
  // ==========================================
  await page.locator('a', { hasText: /Editar/i }).first().click();
  
  await page.waitForSelector('#lake-name', { state: 'visible', timeout: 10000 });
  await page.fill('#lake-name', `${lakeName} Editado`);
  
  const updateResponse = page.waitForResponse(response => 
    response.url().includes('/lakes') && ['PUT', 'PATCH'].includes(response.request().method()) && (response.status() === 200 || response.status() === 204)
  );
  await page.locator('button[type="submit"]').click();
  await updateResponse;

  // ==========================================
  // 6. VALIDACIÓN CARTOGRÁFICA Y LIMPIEZA
  // ==========================================
  await expect(page.locator('.maplibregl-canvas')).toBeVisible({ timeout: 20000 });
  
  const deleteResponse = page.waitForResponse(response => 
    response.url().includes('/lakes') && ['DELETE', 'PATCH'].includes(response.request().method()) && (response.status() === 200 || response.status() === 204)
  );
  await page.locator('button', { hasText: /Desactivar|Eliminar/i }).first().click();
  await deleteResponse;

  // FIX: Ajustamos la validación final también
  await expect(page.locator('h1', { hasText: 'Listado de Lagos' })).toBeVisible({ timeout: 15000 });
});

