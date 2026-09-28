import { test, expect } from '@playwright/test';

test('S2-088: Flujo E2E - Login, Catálogo, Mapa y Limpieza', async ({ page }) => {
  // 1. Login
  await page.goto('/login');
  await page.fill('input[type="email"]', 'admin@aquabloom.cl'); // Ajustar correo de prueba
  await page.fill('input[type="password"]', 'secreto123'); // Ajustar contraseña
  await page.click('button[type="submit"]');

  // 2. Abrir catálogo
  await page.waitForURL('**/catalog'); // Ajustar ruta del catálogo si es diferente
  await expect(page.locator('text=Catálogo')).toBeVisible();

  // 3. Crear lago
  const lakeName = `Lago E2E Test ${Date.now()}`;
  await page.click('button:has-text("Crear Lago")'); // Ajustar texto del botón
  await page.fill('input[name="name"]', lakeName);
  // Simular clics en el mapa para el polígono si es requerido, o llenar coordenadas
  await page.click('button:has-text("Guardar")');
  
  // Validar creación
  await expect(page.locator(`text=${lakeName}`)).toBeVisible();

  // 4. Editarlo y comprobar en el mapa
  await page.click(`text=${lakeName}`);
  await page.click('button:has-text("Editar")');
  await page.click('button:has-text("Actualizar")');
  
  // Comprobar que el mapa (Leaflet) se renderizó correctamente
  await expect(page.locator('.leaflet-container')).toBeVisible();

  // 5. Eliminar o desactivar el dato (Teardown automático)
  await page.click('button:has-text("Eliminar")');
  await page.click('button:has-text("Confirmar")'); // Ajustar confirmación de borrado

  // Validar limpieza exitosa
  await expect(page.locator(`text=${lakeName}`)).not.toBeVisible();
});
