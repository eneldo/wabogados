import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

test("administrative reset works with keyboard, validation, cancellation and session revocation", async ({ page, context, request }) => {
  const file = process.env.PASSWORD_RESET_TEST_AUTH;
  const api = process.env.PASSWORD_RESET_TEST_API;
  test.skip(!file || !api, "Solo se cambian contraseñas de cuentas sintéticas en instalación aislada.");
  const credentials = JSON.parse(await readFile(file!, "utf8"));
  await context.addCookies([{ name: "wb_access", value: credentials.access, url: test.info().project.use.baseURL as string }]);
  await page.goto("/admin/usuarios", { waitUntil: "networkidle" });
  const row = page.getByRole("row").filter({ hasText: credentials.target_email });
  const trigger = row.getByRole("button", { name: "Restablecer contraseña", exact: true });
  await expect(trigger).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "reset-super@example.com" }).getByRole("button", { name: "Restablecer contraseña" })).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: "reset-admin@example.com" }).getByRole("button", { name: "Restablecer contraseña" })).toHaveCount(0);
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: `Restablecer contraseña de ${credentials.target_email}` });
  const password = dialog.getByLabel("Nueva contraseña", { exact: false });
  const confirmation = dialog.getByLabel("Confirmar contraseña", { exact: false });
  await expect(password).toBeFocused();
  await password.fill("not-saved-password");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await expect(password).toHaveValue("");
  await password.fill("not-saved-password");
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  await trigger.click();
  await expect(password).toHaveValue("");

  // Field diagnostics and focus without echoing secrets in action state.
  await password.fill("synthetic-new-password");
  await confirmation.fill("different-password");
  await dialog.getByRole("button", { name: "Restablecer contraseña", exact: true }).click();
  await expect(dialog.getByText("Las contraseñas no coinciden.", { exact: true })).toBeVisible();
  await expect(confirmation).toBeFocused();
  await expect(password).toHaveValue("");
  await expect(confirmation).toHaveValue("");
  await dialog.getByRole("button", { name: "Mostrar contraseñas" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await dialog.getByRole("button", { name: "Ocultar contraseñas" }).click();
  await expect(password).toHaveAttribute("type", "password");

  const captures = path.resolve(process.cwd(), "../.tmp/password-reset-review");
  await mkdir(captures, { recursive: true });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    const box = await dialog.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    for (const control of await dialog.locator("h2, input:not([type=hidden]), button").all()) {
      const bounds = await control.boundingBox();
      expect(bounds!.x).toBeGreaterThanOrEqual(box!.x);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(box!.x + box!.width);
    }
    expect(await dialog.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
    if (width === 390 || width === 1440) await page.screenshot({ path: path.join(captures, `dialog-${width}.png`) });
  }
  const duplicates = await page.locator("[id]").evaluateAll((elements) => {
    const ids = elements.map((element) => element.id);
    return ids.filter((id, index) => ids.indexOf(id) !== index);
  });
  expect(duplicates).toEqual([]);

  const newPassword = "  synthetic-reset-password  ";
  await password.fill(newPassword);
  await confirmation.fill(newPassword);
  let writes = 0;
  let reflectedSecret = false;
  page.on("request", (req) => { if (req.headers()["next-action"]) writes++; });
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/admin/usuarios", async (route) => {
    if (!route.request().headers()["next-action"]) return route.continue();
    await waiting;
    const response = await route.fetch();
    reflectedSecret = (await response.text()).includes(newPassword);
    await route.fulfill({ response });
  });
  await dialog.locator("form").evaluate((form: HTMLFormElement) => {
    form.requestSubmit();
    form.requestSubmit();
  });
  await expect(dialog.getByRole("button", { name: "Guardando…" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  release();
  await expect(dialog).not.toBeVisible();
  await expect(row.getByRole("status")).toContainText("Contraseña restablecida");
  expect(writes).toBe(1);
  expect(reflectedSecret).toBe(false);
  await trigger.click();
  await expect(password).toHaveValue("");
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect((await request.get(`${api}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${credentials.old_access}` } })).status()).toBe(401);
  expect((await request.post(`${api}/api/v1/auth/refresh`, { data: { refresh_token: credentials.old_refresh } })).status()).toBe(401);
  const login = await request.post(`${api}/api/v1/auth/login`, { data: { email: credentials.target_email, password: newPassword } });
  expect(login.status()).toBe(200);
  const tokens = await login.json();
  expect((await request.post(`${api}/api/v1/auth/logout`, { data: { refresh_token: tokens.refresh_token }, headers: { Authorization: `Bearer ${tokens.access_token}` } })).status()).toBe(200);
});

test("role-less superuser can use the dedicated users action", async ({ page, context }) => {
  const file = process.env.PASSWORD_RESET_TEST_AUTH;
  test.skip(!file, "Requiere cuenta sintética aislada.");
  const credentials = JSON.parse(await readFile(file!, "utf8"));
  await context.addCookies([{ name: "wb_access", value: credentials.super_access, url: test.info().project.use.baseURL as string }]);
  await page.goto("/admin/usuarios", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Usuarios", exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: credentials.target_email }).getByRole("button", { name: "Restablecer contraseña" })).toBeVisible();
});
