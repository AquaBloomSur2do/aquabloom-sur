import { test, expect } from '@playwright/test';

test('S2-088: Flujo E2E - Login, Catálogo, Mapa y Limpieza', async ({ page }) => {
    await page.goto('http://localhost:5173/login');
    await page.fill('input[type="email"]', 'e2e@ejemplo.cl'); 
    await page.fill('input[type="password"]', 'AutomatedTest2026!');
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard');
    await expect(page.locator('text=Catálogo')).toBeVisible();

    const lakeName = `Lago E2E Test ${Date.now()}`;
    await page.click('button:has-text("Crear Lago")'); 
    await page.fill('input[name="name"]', lakeName);

    // FIX 1: Inyección automatizada de geometría GeoJSON válida
    const testGeoJSON = JSON.stringify({
        "type": "Polygon",
        "coordinates": [[[-72.3, -39.8], [-72.2, -39.8], [-72.2, -39.9], [-72.3, -39.9], [-72.3, -39.8]]]
    });
    await page.fill('textarea', testGeoJSON); 
    await page.click('button:has-text("Guardar")');

    await expect(page.locator(`text=${lakeName}`)).toBeVisible();
    await page.click(`text=${lakeName}`);
    await page.click('button:has-text("Editar")');

    // FIX 2: Mitigación de condición de carrera esperando el montaje de datos
    await page.waitForSelector(`input[value="${lakeName}"]`, { state: 'visible' });
    await page.click('button:has-text("Actualizar")');

    // FIX 3: Aserción actualizada a la arquitectura de MapLibre
    await expect(page.locator('.maplibregl-canvas')).toBeVisible();
});
