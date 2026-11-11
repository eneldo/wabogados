import { mkdir } from "node:fs/promises";
import path from "node:path";
import { setTimeout as pace } from "node:timers/promises";

import { expect, test } from "@playwright/test";

import { isClientOnly, landingFor } from "../lib/landing";
import { ADMIN_MODULES } from "../lib/admin-nav";
import { expectCorporateBrand, expectSemanticContrast } from "./brand-assertions";

const modules = [
  ["/admin", "Dashboard"],
  ["/admin/expedientes", "Expedientes"],
  ["/admin/clientes", "Clientes"],
  ["/admin/abogados", "Abogados"],
  ["/admin/agenda", "Agenda y audiencias"],
  ["/admin/mensajes", "Mensajes"],
  ["/admin/solicitudes", "Solicitudes"],
  ["/admin/documentos", "Documentos"],
  ["/admin/multimedia", "Centro multimedia"],
  ["/admin/ia-juridica", "IA Jurídica"],
  ["/admin/facturacion", "Facturación"],
  ["/admin/seguridad", "Usuarios"],
  ["/admin/configuracion", "Configuración"],
  ["/admin/estadisticas-web", "Estadísticas web"],
] as const;

test("landing and client classification agree, including mixed roles", () => {
  for (const roles of [["administrador"], ["cliente", "administrador"], ["administrador", "cliente"]]) {
    expect(landingFor(roles, ["cases:read_all"]).href).toBe("/admin");
    expect(isClientOnly(roles)).toBe(false);
  }
  expect(landingFor(["cliente"], ["cases:read_published"]).href).toBe("/portal");
  expect(isClientOnly(["cliente"])).toBe(true);
  expect(landingFor(["abogado"], ["cases:read_assigned"]).href).toBe("/expedientes");
});

test("anonymous and invalid-cookie requests cannot enter administration", async ({ page, context }) => {
  for (const href of ["/admin", "/admin/seguridad", "/portal"]) {
    await page.goto(href, { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("button", { name: "Entrar", exact: true })).toBeVisible();
  }
  // A readable future expiry avoids renewal in the proxy. The backend must
  // still reject the signature; a cookie's presence alone grants no session.
  const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url");
  await context.addCookies([{ name: "wb_access", value: `e30.${payload}.invalid`, url: test.info().project.use.baseURL as string }]);
  await page.goto("/login", { waitUntil: "networkidle" });
  await expect(page.getByRole("button", { name: "Entrar", exact: true })).toBeVisible();
  await page.goto("/admin", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(/\/login$/);
});

test("autofilled fields are submitted even without React change events", async ({ page }) => {
  // Only the form submission is mocked; this does not count as a real login.
  let submitted: { email?: string; password?: string } | undefined;
  await page.route("**/api/session", async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 503, json: { error: { message: "Error de prueba controlado" } } });
  });
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.evaluate(() => {
    document.querySelector<HTMLInputElement>('input[name="email"]')!.value = "autofill@example.test";
    document.querySelector<HTMLInputElement>('input[name="password"]')!.value = "dummy-form-value";
  });
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.locator('form [role="alert"]')).toHaveText("Error de prueba controlado");
  expect(submitted).toEqual({ email: "autofill@example.test", password: "dummy-form-value" });
  await expect(page).toHaveURL(/\/login$/);
});

test("public entry, existing session, all admin modules, mobile and server logout", async ({ page, context, request }) => {
  test.setTimeout(240_000);
  page.setDefaultTimeout(15_000);
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  if (!email || !password) throw new Error("Se necesitan E2E_EMAIL y E2E_PASSWORD de una cuenta administradora real.");
  const captures = path.resolve(process.cwd(), "../.tmp/admin-portal-review");
  await mkdir(captures, { recursive: true });
  const errors: string[] = [];
  let cleanupSession: { access: string; refresh: string } | undefined;
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.locator("#site-navigation").getByRole("link", { name: /Portal privado/ }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="email"]').fill(email);
    await page.locator('input[type="password"]').fill(password);
    const login = page.waitForResponse((response) => response.url().endsWith("/api/session") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Entrar", exact: true }).click();
    const response = await login;
    expect(response.status()).toBe(200);
    expect((await response.json()).href).toBe("/admin");
    await expect(page).toHaveURL(/\/admin$/);
    await page.waitForLoadState("networkidle");
    const signedInCookies = await context.cookies();
    cleanupSession = {
      access: signedInCookies.find((cookie) => cookie.name === "wb_access")!.value,
      refresh: signedInCookies.find((cookie) => cookie.name === "wb_refresh")!.value,
    };
    await expect(page.locator("aside nav a")).toHaveCount(ADMIN_MODULES.filter((module) => module.state === "ready").length);
    await expect(page.locator("aside").getByRole("link", { name: "Mi panel", exact: true })).toHaveAttribute("href", "/admin");
    await expectCorporateBrand(page);
    await expectSemanticContrast(page);
    await page.screenshot({ path: path.join(captures, "dashboard.png"), animations: "disabled" });

    // Re-enter through the public site with the session still active.
    await page.goto("/", { waitUntil: "networkidle" });
    await page.locator("#site-navigation").getByRole("link", { name: /Portal privado/ }).click();
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();

    // Real read-only rendering of the shared client/staff templates using the
    // administrator session. This is not a login as a client or a lawyer.
    for (const href of ["/portal", "/portal/documentos", "/portal/mensajes", "/expedientes"]) {
      await pace(6500);
      const result = await page.goto(href, { waitUntil: "networkidle" });
      expect(result?.status()).toBe(200);
      await expectCorporateBrand(page);
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        await expectCorporateBrand(page);
        expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      }
      await page.screenshot({ path: path.join(captures, `${href.replaceAll("/", "-")}-theme.png`), animations: "disabled" });
    }
    const evidence = await page.locator('main a[href$="/evidencias"]').first().getAttribute("href");
    expect(evidence).toBeTruthy();
    await pace(6500);
    await page.goto(evidence!, { waitUntil: "networkidle" });
    await expectCorporateBrand(page);
    await page.screenshot({ path: path.join(captures, "evidence-theme.png"), animations: "disabled" });

    for (const [href, heading] of modules) {
      // Each SSR page issues several API requests. Respect the existing
      // 100/minute limit instead of disabling security to run a fast crawl.
      await pace(6500);
      const result = await page.goto(href, { waitUntil: "networkidle" });
      expect(result?.status(), href).toBe(200);
      expect(new URL(page.url()).pathname).toBe(href);
      await expect(page.getByRole("heading", { name: heading, exact: true }).first()).toBeVisible();
      await expect(page.locator("main")).not.toContainText(/Servicio no disponible|No fue posible cargar|No fue posible consultar el índice|Sin acceso a esta sección|Catálogo de permisos no disponible/);
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        await expectCorporateBrand(page);
        const layout = await page.evaluate(() => {
          const seen = new Set<string>();
          const duplicates: string[] = [];
          for (const element of document.querySelectorAll("[id]")) {
            if (seen.has(element.id)) duplicates.push(element.id);
            seen.add(element.id);
          }
          return { overflow: document.documentElement.scrollWidth - innerWidth, duplicates };
        });
        expect(layout.overflow, `${href} at ${width}`).toBeLessThanOrEqual(1);
        expect(layout.duplicates, href).toEqual([]);
      }
      if (href === "/admin/clientes") {
        await page.getByRole("button", { name: "Nuevo cliente", exact: true }).click();
        const dialog = page.getByRole("dialog", { name: "Registrar cliente", exact: true });
        await expect(dialog).toHaveCSS("background-color", "rgb(48, 52, 64)");
        await expect(dialog.locator('button[type="submit"]')).toHaveCSS("background-color", "rgb(201, 22, 32)");
        expect(await dialog.evaluate((element) => getComputedStyle(element, "::backdrop").backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
        await page.screenshot({ path: path.join(captures, "client-form-theme.png"), animations: "disabled" });
        await page.keyboard.press("Escape");
        await expect(dialog).not.toBeVisible();
      }
      console.log(`OK ${href}: HTTP 200, title, data and four viewport widths`);
    }

    await page.setViewportSize({ width: 390, height: 900 });
    await page.getByRole("button", { name: "Abrir el menú de administración", exact: true }).click();
    await expect(page.locator('nav[aria-label="Administración"] a:visible')).toHaveCount(13);
    await expectCorporateBrand(page);
    await expect(page.getByRole("link", { name: "Mi panel", exact: true }).filter({ visible: true })).toHaveAttribute("href", "/admin");
    await page.screenshot({ path: path.join(captures, "mobile-menu.png"), animations: "disabled" });
    await page.locator('nav[aria-label="Administración"] a[href="/admin"]:visible').click();
    await expect(page).toHaveURL(/\/admin$/);
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("button", { name: "Abrir el menú de administración", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Abrir el menú de administración", exact: true }).click();

    const refresh = (await context.cookies()).find((cookie) => cookie.name === "wb_refresh");
    expect(Boolean(refresh)).toBe(true);
    await page.getByRole("button", { name: "Salir", exact: true }).filter({ visible: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect((await context.cookies()).some((cookie) => ["wb_access", "wb_refresh"].includes(cookie.name))).toBe(false);
    const revoked = await request.post(`${process.env.E2E_API_URL ?? "http://localhost:8000"}/api/v1/auth/refresh`, {
      data: { refresh_token: refresh!.value },
    });
    expect(revoked.status()).toBe(401);
    await page.goto("/admin", { waitUntil: "networkidle" });
    await expect(page).toHaveURL(/\/login$/);
    expect(errors).toEqual([]);
  } finally {
    // No storageState is written, and failed checks also revoke their session.
    if (cleanupSession) {
      // Use Node fetch so cleanup still works if Playwright closes a timed-out
      // browser context. Credentials remain only in this process's memory.
      await fetch(`${process.env.E2E_API_URL ?? "http://localhost:8000"}/api/v1/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${cleanupSession.access}`, "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: cleanupSession.refresh }),
        signal: AbortSignal.timeout(10_000),
      });
    }
    await context.clearCookies().catch(() => undefined);
  }
});
