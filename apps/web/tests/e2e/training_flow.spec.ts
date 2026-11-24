import { expect, test } from '@playwright/test';

const runtimeEnv =
  (
    globalThis as {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env ?? {};

const E2E_EMAIL = runtimeEnv.E2E_EMAIL ?? 'admin@aquabloom.cl';
const E2E_PASSWORD = runtimeEnv.E2E_PASSWORD ?? 'AquaBloom2026!';

test('S2-168: Flujo E2E - Entrenamiento completo en staging con resultado persistido', async ({
  page,
}) => {
  // 1. Inicio de sesión autenticado
  await page.goto('/login');

  const loginResponse = page.waitForResponse(
    (response) =>
      response.url().includes('token') && response.status() === 200,
  );

  await page.fill('#login-email', E2E_EMAIL);
  await page.fill('#login-password', E2E_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await loginResponse;

  await page.waitForURL('**/dashboard', { timeout: 15000 });

  // 2. Navegar a Revisión de datasets y localizar una versión publicada
  await page.goto('/datasets/review');
  await expect(
    page.getByRole('heading', { name: /Revisión de datasets/i }),
  ).toBeVisible({ timeout: 15000 });

  const startTrainingButton = page.getByRole('button', {
    name: /Entrenar Modelo Piloto/i,
  });

  if (!(await startTrainingButton.isVisible())) {
    const publishButton = page.getByRole('button', {
      name: /Publicar versión/i,
    });
    if ((await publishButton.isVisible()) && (await publishButton.isEnabled())) {
      await publishButton.click();
    }
  }

  await expect(startTrainingButton).toBeVisible({ timeout: 15000 });

  // 3. Disparar el worker científico vía API Gateway
  const submitJobPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/executions/jobs') &&
      response.request().method() === 'POST',
  );

  await startTrainingButton.click();
  const submitJobResponse = await submitJobPromise;
  expect(submitJobResponse.status()).toBe(202);

  const acceptedPayload = (await submitJobResponse.json()) as {
    job_id: string;
    status: string;
  };
  expect(acceptedPayload.job_id).toBeTruthy();

  // 4. Confirmar navegación al detalle y polling hasta resultado persistido
  await page.waitForURL(`**/scientific/jobs/${acceptedPayload.job_id}`, {
    timeout: 15000,
  });

  await expect(page.getByText('Completado')).toBeVisible({ timeout: 20000 });
  await expect(page.getByText(acceptedPayload.job_id)).toBeVisible();

  const resultHeading = page.getByRole('heading', { name: 'Resultado' });
  await expect(resultHeading).toBeVisible();
  await expect(page.getByText('prediction_value')).toBeVisible();
  await expect(page.getByText('metrics')).toBeVisible();
});

