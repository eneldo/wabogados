import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

const authFile = process.env.RECOVERY_TEST_AUTH;
const api = process.env.RECOVERY_TEST_API;
const mailbox = process.env.RECOVERY_TEST_MAILBOX;

test.beforeEach(() => {
  test.skip(!authFile || !api || !mailbox, "Solo con cuentas y buzón SMTP sintéticos en instalación aislada.");
});

test("real email link recovers access, clears sessions and never travels in a URL to the server", async ({ page, context, request }) => {
  const credentials = JSON.parse(await readFile(authFile!, "utf8"));
  // A fresh synthetic account makes repeated runs independent of prior resets.
  const initialPassword = randomBytes(24).toString("base64url");
  const email = `recovery-e2e-${randomUUID()}@example.com`;
  const created = await request.post(`${api}/api/v1/admin/users`, {
    headers: { Authorization: `Bearer ${credentials.access}` },
    data: { email, password: initialPassword, full_name: "Cuenta sintética E2E", role_names: ["cliente"] },
  });
  expect(created.status()).toBe(201);
  const beforeLogin = await request.post(`${api}/api/v1/auth/login`, { data: { email, password: initialPassword } });
  expect(beforeLogin.status()).toBe(200);
  const before = await beforeLogin.json();
  credentials.target_email = email;
  credentials.old_access = before.access_token;
  credentials.old_refresh = before.refresh_token;
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.getByRole("link", { name: "Olvidé mi contraseña", exact: true }).click();
  await expect(page).toHaveURL(/\/olvide-contrasena$/);
  await page.getByRole("button", { name: "Enviar instrucciones" }).click();
  await expect(page.getByText("Introduzca un correo válido.")).toBeVisible();
  await expect(page.getByLabel("Correo electrónico")).toBeFocused();
  await page.getByLabel("Correo electrónico").fill(credentials.target_email);
  await page.getByRole("button", { name: "Enviar instrucciones" }).click();
  await expect(page.getByRole("status")).toContainText("Si existe una cuenta habilitada");
  await expect(page.getByLabel("Correo electrónico")).toHaveValue("");

  let link = "";
  await expect.poll(async () => {
    const messages = await (await request.get(`${mailbox}/messages`)).json();
    const message = messages.find((item: { to: string[] }) => item.to.includes(credentials.target_email));
    link = message?.text.match(/http:\/\/[^\s]+\/restablecer-contrasena#token=[A-Za-z0-9_-]{43}/)?.[0] ?? "";
    return Boolean(link);
  }, { timeout: 15000 }).toBe(true);
  const token = new URL(link).hash.slice("#token=".length);
  expect((await request.get(link)).status()).toBe(200); // A mail scanner's GET must not consume it.
  expect((await request.get(`${api}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${credentials.old_access}` } })).status()).toBe(200);
  await context.addCookies([
    { name: "wb_access", value: credentials.old_access, url: test.info().project.use.baseURL as string },
    { name: "wb_refresh", value: credentials.old_refresh, url: test.info().project.use.baseURL as string },
  ]);
  const urls: string[] = [];
  page.on("request", (req) => { urls.push(req.url()); });
  const response = await page.goto(link, { waitUntil: "networkidle" });
  expect(response?.headers()["cache-control"]).toContain("no-store");
  expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
  await expect(page).toHaveURL(/\/restablecer-contrasena$/);
  await expect(page.getByLabel("Nueva contraseña", { exact: false })).toBeVisible();
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
  const captures = path.resolve(process.cwd(), "../.tmp/recovery-review");
  await mkdir(captures, { recursive: true });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    for (const input of await page.locator("input").all()) {
      const bounds = await input.boundingBox();
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    }
    if (width === 390 || width === 1440) await page.screenshot({ path: path.join(captures, `reset-${width}.png`) });
  }
  expect(await page.locator("[id]").evaluateAll((elements) => {
    const ids = elements.map((entry) => entry.id);
    return ids.filter((id, index) => ids.indexOf(id) !== index);
  })).toEqual([]);
  const password = page.getByLabel("Nueva contraseña", { exact: false });
  const confirmation = page.getByLabel("Confirmar contraseña", { exact: false });
  await password.fill("synthetic-new-password");
  await confirmation.fill("different-password");
  await page.getByRole("button", { name: "Guardar nueva contraseña" }).click();
  await expect(page.getByText("Las contraseñas no coinciden.")).toBeVisible();
  await expect(confirmation).toBeFocused();
  await page.getByRole("button", { name: "Mostrar contraseñas" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Ocultar contraseñas" }).click();
  const newPassword = "  synthetic-mail-recovery-password  ";
  await password.fill(newPassword);
  await confirmation.fill(newPassword);
  let release!: () => void;
  let writes = 0;
  const wait = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/recuperacion/restablecer", async (route) => {
    writes++;
    await wait;
    const upstream = await route.fetch();
    const body = await upstream.text();
    expect(body.includes(token)).toBe(false);
    expect(body.includes(newPassword)).toBe(false);
    await route.fulfill({ response: upstream });
  });
  await page.locator("form").evaluate((form: HTMLFormElement) => { form.requestSubmit(); form.requestSubmit(); });
  await expect(page.getByRole("button", { name: "Guardando…" })).toBeDisabled();
  release();
  await expect(page.getByRole("status")).toContainText("Contraseña actualizada");
  expect(writes).toBe(1);
  expect(urls.every((url) => !url.includes(token))).toBe(true);
  expect(urls.some((url) => url.includes("/api/estadisticas"))).toBe(false);
  expect((await context.cookies()).some((cookie) => ["wb_access", "wb_refresh"].includes(cookie.name))).toBe(false);
  expect((await request.get(`${api}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${credentials.old_access}` } })).status()).toBe(401);
  expect((await request.post(`${api}/api/v1/auth/refresh`, { data: { refresh_token: credentials.old_refresh } })).status()).toBe(401);
  expect((await request.get(`${api}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${credentials.access}` } })).status()).toBe(200);
  const login = await request.post(`${api}/api/v1/auth/login`, { data: { email: credentials.target_email, password: newPassword } });
  expect(login.status()).toBe(200);
  expect((await request.post(`${api}/api/v1/auth/reset-password`, { data: { token, new_password: newPassword, confirm_password: newPassword } })).status()).toBe(400);
});

test("unknown and unverified recipients get the same generic response without mail", async ({ page, request }) => {
  await page.goto("/olvide-contrasena", { waitUntil: "networkidle" });
  for (const email of ["recovery-unknown@example.com", "recovery-unverified@example.com"]) {
    await page.getByLabel("Correo electrónico").fill(email);
    await page.getByRole("button", { name: "Enviar instrucciones" }).click();
    await expect(page.getByRole("status")).toContainText("Si existe una cuenta habilitada");
  }
  // The isolated worker is sequential/FIFO. A subsequent eligible delivery is
  // a processing barrier, rather than checking absence before the worker ran.
  await page.getByLabel("Correo electrónico").fill("recovery-admin@example.com");
  await page.getByRole("button", { name: "Enviar instrucciones" }).click();
  await expect.poll(async () => {
    const inbox = await (await request.get(`${mailbox}/messages`)).json();
    return inbox.some((entry: { to: string[] }) => entry.to.includes("recovery-admin@example.com"));
  }, { timeout: 15000 }).toBe(true);
  const messages = await (await request.get(`${mailbox}/messages`)).json();
  expect(messages.some((message: { to: string[] }) => message.to.includes("recovery-unverified@example.com") || message.to.includes("recovery-unknown@example.com"))).toBe(false);
});

test("missing fragment and cross-origin submission are rejected safely", async ({ page, request }) => {
  await page.goto("/restablecer-contrasena#token=malformed", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(/\/restablecer-contrasena$/);
  await expect(page.locator("main").getByRole("alert")).toContainText("El enlace no es válido");
  await expect(page.getByRole("link", { name: "Solicitar un nuevo enlace" })).toBeVisible();
  const response = await request.post("/api/recuperacion/solicitar", { headers: { Origin: "https://malicious.example" }, data: { email: "recovery-target@example.com" } });
  expect(response.status()).toBe(403);
});
