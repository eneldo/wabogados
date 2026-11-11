import { expect, test as setup } from "@playwright/test";

/**
 * Signs in once and saves the session for the layout gate.
 *
 * Credentials come from the environment and are never written to the repository.
 * When they are missing the setup **fails loudly** instead of skipping: a gate
 * that quietly inspects the login form is worse than no gate, because it reports
 * green having checked nothing.
 *
 * Usage:
 *   E2E_EMAIL=... E2E_PASSWORD=... npm run test:e2e
 */

const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const STORAGE = "e2e/.auth.json";

setup("authenticate", async ({ page }) => {
  if (!EMAIL || !PASSWORD) {
    // Failing rather than skipping: a gate that quietly inspects the login form
    // reports green having checked nothing at all.
    throw new Error(
      "Faltan E2E_EMAIL o E2E_PASSWORD: la puerta necesita una sesión real. " +
        "Sin ella solo se comprobaría el formulario de acceso.",
    );
  }

  await page.goto("/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', EMAIL as string);
  await page.fill('input[type="password"]', PASSWORD as string);
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await page.context().storageState({ path: STORAGE });
});
