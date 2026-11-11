import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";
import { visibleModules } from "../lib/admin-nav";

test("analytics navigation is restricted to its explicit permission", () => {
  expect(visibleModules([]).some((item) => item.slug === "estadisticas-web")).toBe(false);
  expect(visibleModules(["website_analytics:read"]).some((item) => item.slug === "estadisticas-web")).toBe(true);
});

test("anonymous visitors cannot open the private statistics panel", async ({ page }) => {
  await page.goto("/admin/estadisticas-web", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Estadísticas web", exact: true })).toHaveCount(0);
});

test("DNT keeps normal public browsing out of analytics", async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, "doNotTrack", { get: () => "1" }));
  const events: string[] = [];
  page.on("request", (request) => { if (request.url().endsWith("/api/estadisticas")) events.push(request.url()); });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator("#servicios article a").first().click();
  await page.waitForURL(/\/servicios\//);
  await page.waitForLoadState("networkidle");
  expect(events).toEqual([]);
});

test.describe("memory-only collector", () => {
  test.use({ extraHTTPHeaders: { DNT: "0" } });

  test("counts public navigation and phone intent without form data or browser storage", async ({ page }) => {
    const events: { kind: string; path: string; visitor_id: string; event_id: string }[] = [];
    await page.route("**/api/estadisticas", async (route) => {
      const payload = route.request().postDataJSON();
      expect(Object.keys(payload).sort()).toEqual(["event_id", "kind", "path", "visitor_id"]);
      events.push(payload);
      await route.fulfill({ status: 204 });
    });
    await page.goto("/?consulta=texto-que-no-se-registra", { waitUntil: "networkidle" });
    await expect.poll(() => events.length).toBe(1);
    expect(events[0].path).toBe("/");
    await page.locator("#servicios article a").first().click();
    await page.waitForURL(/\/servicios\//);
    await page.waitForLoadState("networkidle");
    await expect.poll(() => events.length).toBe(2);
    await page.locator('a[href^="tel:"]').first().click();
    await expect.poll(() => events.some((event) => event.kind === "phone_click")).toBe(true);
    expect(new Set(events.map((event) => event.visitor_id)).size).toBe(1);
    expect(new Set(events.map((event) => event.event_id)).size).toBe(events.length);
    expect(JSON.stringify(events)).not.toContain("texto-que-no-se-registra");
    expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
    expect(await page.context().cookies()).toEqual([]);
  });
});

test.describe("isolated real intake", () => {
  test.use({
    extraHTTPHeaders: { DNT: "0" },
    userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
  });

  test("public views and phone clicks reach the private real totals", async ({ page, request }) => {
    const file = process.env.WEBSITE_ANALYTICS_TEST_AUTH;
    const api = process.env.WEBSITE_ANALYTICS_TEST_API;
    test.skip(!file || !api, "Solo se envían métricas reales al entorno efímero de pruebas.");
    const { access } = JSON.parse(await readFile(file!, "utf8"));
    const headers = { Authorization: `Bearer ${access}` };
    const before = await (await request.get(`${api}/api/v1/admin/metrics/website`, { headers })).json();
    const home = page.waitForResponse((response) => response.url().endsWith("/api/estadisticas"));
    await page.goto("/", { waitUntil: "networkidle" });
    expect((await home).status()).toBe(204);
    const area = page.waitForResponse((response) => response.url().endsWith("/api/estadisticas"));
    await page.locator("#servicios article a").first().click();
    await page.waitForURL(/\/servicios\//);
    expect((await area).status()).toBe(204);
    const phone = page.waitForResponse((response) => response.url().endsWith("/api/estadisticas"));
    await page.locator('a[href^="tel:"]').first().click();
    expect((await phone).status()).toBe(204);
    const after = await (await request.get(`${api}/api/v1/admin/metrics/website`, { headers })).json();
    expect(after.totals.page_views).toBe(before.totals.page_views + 2);
    expect(after.totals.estimated_visitors).toBe(before.totals.estimated_visitors + 1);
    expect(after.totals.phone_clicks).toBe(before.totals.phone_clicks + 1);
    expect(await page.context().cookies()).toEqual([]);
  });
});

test("administrator sees real totals, filters, empty state and mobile layout", async ({ page, context }) => {
  const file = process.env.WEBSITE_ANALYTICS_TEST_AUTH;
  test.skip(!file, "Requiere sesión temporal del entorno aislado de pruebas, no credenciales de producción.");
  const { access } = JSON.parse(await readFile(file!, "utf8"));
  await context.addCookies([{ name: "wb_access", value: access, url: test.info().project.use.baseURL as string }]);
  await page.goto("/admin/estadisticas-web", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Estadísticas web", exact: true })).toBeVisible();
  await expect(page.getByText("Solicitudes registradas", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Áreas jurídicas más consultadas" })).toBeVisible();
  await expect(page.getByText("Laboral", { exact: true }).first()).toBeVisible();
  await expect(page.locator("aside").getByRole("link", { name: "Estadísticas web", exact: true })).toBeVisible();
  const captures = path.resolve(process.cwd(), "../.tmp/website-analytics-review");
  await mkdir(captures, { recursive: true });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    if (width === 1440) await page.screenshot({ path: path.join(captures, "dashboard-1440.png"), fullPage: true });
  }
  await page.goto("/admin/estadisticas-web?start=2026-01-01&end=2026-01-02", { waitUntil: "networkidle" });
  await expect(page.getByText("Aún no hay visitas registradas en este periodo", { exact: true })).toBeVisible();
  await page.goto("/admin/estadisticas-web?start=2099-01-01&end=2099-01-02", { waitUntil: "networkidle" });
  await expect(page.getByText("Rango de fechas no válido", { exact: true })).toBeVisible();
});
