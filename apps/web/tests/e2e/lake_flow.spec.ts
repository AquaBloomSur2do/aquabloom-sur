import { test, expect } from '@playwright/test';

test('S2-088: Flujo E2E - Login, Catálogo, Mapa y Limpieza', async ({ page }) => {
  // Manejo automático de diálogos nativos (alerts de confirmación al eliminar/desactivar)
  page.on('dialog', dialog => dialog.accept());

  // 1. Login Seguro (Usando IDs indestructibles de la S2-080)
  await page.goto('http://localhost:5173/login');
  await page.fill('#login-email', 'secret@ejem.cl'); 
  await page.fill('#login-password', 'ClabeSecreta123!');
  await page.locator('button[type="submit"]').click();

  // 2. Transición y Persistencia de Sesión (La Magia Negra)
  await page.waitForURL('**/dashboard');
  
  // Garantizamos que Supabase guardó el token en el navegador ANTES de navegar
  // Esto evita el fallo de "deslogueo fantasma" al usar page.goto
  await page.waitForFunction(() => {
    return Object.keys(window.localStorage).some(key => key.includes('auth-token'));
  });

  // 3. Navegación directa y segura al catálogo
  await page.goto('http://localhost:5173/lakes');
  await expect(page.locator('h1', { hasText: 'Catálogo de Lagos' })).toBeVisible();

  // 4. Crear Lago
  const lakeName = `Lago E2E Test ${Date.now()}`;
  // Usamos el href exacto que configuramos, ignorando textos que pueden cambiar
  await page.locator('a[href="/lakes/new"]').click(); 
  
  await page.waitForSelector('#lake-name', { state: 'visible' });
  await page.fill('#lake-name', lakeName);
  await page.fill('#lake-region', 'Los Lagos (E2E)'); // Campo obligatorio
  
  const testGeoJSON = JSON.stringify({
    "type": "Polygon",
    "coordinates": [[[-72.3, -39.8], [-72.2, -39.8], [-72.2, -39.9], [-72.3, -39.9], [-72.3, -39.8]]]
  });
  await page.fill('#lake-geojson', testGeoJSON);
  
  // Clic universal a cualquier botón de envío del formulario
  await page.locator('button[type="submit"]').click();

  // 5. Validar creación en el catálogo
  await page.waitForURL('**/lakes');
  const lakeRow = page.locator('tr', { hasText: lakeName });
  await expect(lakeRow).toBeVisible({ timeout: 10000 });

  // Entrar al detalle del lago creado
  await lakeRow.locator('text="Ver Detalles"').click();

  // 6. Editar Lago
  // Usamos Regex (/Editar/i) para que funcione diga "Editar", "editar" o "EDITAR"
  await page.locator('text=/Editar/i').first().click();
  
  await page.waitForSelector('#lake-name', { state: 'visible' });
  await page.fill('#lake-name', `${lakeName} Editado`);
  await page.locator('button[type="submit"]').click();

  // 7. Visor Cartográfico (Aserción robusta de MapLibre)
  await expect(page.locator('.maplibregl-canvas')).toBeVisible({ timeout: 15000 });

  // 8. Criterio de Aceptación: Limpieza y Eliminación
  // Usamos Regex por si el botón de la vista de detalle dice Desactivar o Eliminar
  await page.locator('text=/Desactivar|Eliminar/i').first().click();
  
  // Aserción final: verificar que el sistema nos devolvió al catálogo tras borrar
  await page.waitForURL('**/lakes');
});
