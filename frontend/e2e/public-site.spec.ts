import { mkdir } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";
import { expectCorporateBrand, expectSemanticContrast } from "./brand-assertions";
import { consultationSubject } from "../lib/consultation-areas";
import { publicServices, serviceIconName, serviceSlug } from "../lib/public-services";

const widths = [320, 390, 768, 820, 900, 901, 1024, 1440, 1920, 2560];
const captures = path.resolve(process.cwd(), "../.tmp/public-brand-review");

for (const width of widths) {
  test(`corporate identity and layout at ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const response = await page.goto("/", { waitUntil: "networkidle" });
    expect(response?.status()).toBe(200);
    await page.emulateMedia({ reducedMotion: "reduce" });

    const logo = page.locator("header .site-logo");
    await expect(logo).toBeVisible();
    await expect(logo).toHaveJSProperty("complete", true);
    expect(await logo.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(100);
    const resource = await request.get(await logo.evaluate((image: HTMLImageElement) => image.currentSrc));
    expect(resource.status()).toBe(200);
    expect(resource.headers()["content-type"]).toMatch(/^image\//);

    const identity = await page.evaluate(() => {
      const image = document.querySelector<HTMLImageElement>("header .site-logo")!;
      const box = image.getBoundingClientRect();
      const header = document.querySelector("header")!.getBoundingClientRect();
      const container = document.querySelector("#inicio")!.getBoundingClientRect();
      const css = getComputedStyle(document.querySelector(".public-site")!);
      return {
        ratio: box.width / box.height,
        naturalRatio: image.naturalWidth / image.naturalHeight,
        withinHeader: box.top >= header.top && box.bottom <= header.bottom,
        background: css.backgroundColor,
        accent: css.getPropertyValue("--color-institutional").trim(),
        gutter: container.left + parseFloat(getComputedStyle(document.querySelector("#inicio")!).paddingLeft),
        overflow: document.documentElement.scrollWidth - innerWidth,
      };
    });
    expect(identity.ratio).toBeCloseTo(identity.naturalRatio, 1);
    expect(identity.withinHeader).toBe(true);
    expect(identity.background).toBe("rgb(37, 43, 57)");
    expect(identity.accent).toBe("#ed1c24");
    await expect(page.locator("#inicio .site-btn").first()).toHaveCSS("background-color", "rgb(201, 22, 32)");
    await expect(page.locator("#inicio h1 em")).toHaveCSS("color", "rgb(255, 112, 119)");
    expect(identity.gutter).toBeLessThanOrEqual(80);
    expect(identity.overflow).toBeLessThanOrEqual(1);

    const copy = await page.locator(".home-hero-copy").boundingBox();
    const illustration = await page.locator(".home-hero-visual").boundingBox();
    expect(copy).not.toBeNull();
    expect(illustration).not.toBeNull();
    if (width < 768) {
      expect(illustration!.y).toBeGreaterThanOrEqual(copy!.y + copy!.height);
    } else {
      expect(illustration!.x).toBeGreaterThanOrEqual(copy!.x + copy!.width);
    }

    if (width === 390 || width === 1920) {
      await mkdir(captures, { recursive: true });
      await page.screenshot({ path: path.join(captures, `home-${width}.png`) });
    }

    await page.locator("#servicios").scrollIntoViewIfNeeded();
    await expect(page.locator("header")).toHaveAttribute("data-condensed", "true");
    expect(await logo.evaluate((image) => {
      const box = image.getBoundingClientRect();
      const header = document.querySelector("header")!.getBoundingClientRect();
      return box.top >= header.top && box.bottom <= header.bottom;
    })).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    // The live catalogue is editable: seven is only the offline fallback.
    const serviceTitles = await page.locator("#servicios article h3").allTextContents();
    expect(serviceTitles.length).toBeGreaterThan(0);
    expect(serviceTitles.every((title) => title.trim().length > 0)).toBe(true);
    expect(new Set(serviceTitles).size).toBe(serviceTitles.length);
    await expect(page.locator("#servicios .service-card").nth(1)).toHaveCSS("background-color", "rgb(48, 52, 64)");
    if (width === 1920) {
      await page.screenshot({ path: path.join(captures, "services-1920.png") });
    }
    await page.locator("footer").scrollIntoViewIfNeeded();
    await expect(page.locator("footer .site-logo")).toHaveJSProperty("complete", true);
    expect(await page.locator("footer .site-logo").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(100);
    const duplicates = await page.evaluate(() => {
      const seen = new Set<string>();
      return Array.from(document.querySelectorAll("[id]")).map((element) => {
        const duplicate = seen.has(element.id);
        seen.add(element.id);
        return duplicate ? element.id : null;
      }).filter(Boolean);
    });
    expect(duplicates).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("homepage consultation, practice areas and firm links reach their sections", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByRole("link", { name: /Hablemos de su caso/ })).toHaveAttribute("href", "tel:+573124699617");

  for (const [name, target] of [
    ["Solicitar consulta", "contacto"],
    ["Conozca nuestras áreas", "servicios"],
    ["Conozca la firma", "firma"],
  ]) {
    await page.locator("#inicio").getByRole("link", { name: new RegExp(name) }).click();
    await expect(page).toHaveURL(new RegExp(`#${target}$`));
    await expect(page.locator(`#${target}`)).toBeInViewport();
  }
});

test("mobile menu, keyboard, privacy dialog and private portal link", async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 1000 });
  await page.goto("/", { waitUntil: "networkidle" });
  const toggle = page.getByRole("button", { name: "Abrir menú", exact: true });
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#site-navigation")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await page.locator("#site-navigation").getByRole("link", { name: "Servicios", exact: true }).click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await page.getByRole("button", { name: "aviso de privacidad", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Abrir menú", exact: true }).click();
  await page.locator("#site-navigation").getByRole("link", { name: /Portal privado/ }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Entrar", exact: true })).toBeVisible();
  // Public and private entry now share the approved corporate identity.
  await expectCorporateBrand(page);
  await expectSemanticContrast(page);
  await expect(page.getByRole("button", { name: "Entrar", exact: true })).toHaveCSS("background-color", "rgb(201, 22, 32)");
});

test("login, service status and not-found use the shared identity", async ({ page }) => {
  for (const href of ["/login", "/estado", "/brand-check-missing-page"]) {
    await page.goto(href, { waitUntil: "networkidle" });
    await expectCorporateBrand(page);
    await expectSemanticContrast(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
});

test("every service card opens its own area with the consultation preselected", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  const services = await page.locator("#servicios article").evaluateAll((articles) =>
    articles.map((article) => ({
      title: article.querySelector("h3")!.textContent!.trim(),
      href: article.querySelector("a")!.getAttribute("href")!,
    })),
  );
  expect(services.length).toBeGreaterThan(0);
  expect(new Set(services.map((service) => service.href)).size).toBe(services.length);

  for (const service of services) {
    await page.getByRole("link", { name: `Consultar esta área: ${service.title}`, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${service.href}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(service.title);
    await expect(page.getByLabel("Área de consulta", { exact: true })).toHaveValue(service.title);
    await expect(page.locator("header").getByRole("link", { name: "Servicios", exact: true })).toHaveAttribute("href", "/#servicios");
    await expect(page.getByRole("link", { name: "Ver todas las áreas", exact: true })).toHaveAttribute("href", "/#servicios");
    await page.goBack({ waitUntil: "networkidle" });
  }
});

test("service detail works on mobile and retains the selected area after a refused submission", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator("#servicios article a").first().click();
  await page.waitForURL(/\/servicios\//);
  const title = await page.getByRole("heading", { level: 1 }).innerText();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);

  // Deliberate refusal stub: no consultation or personal data is stored.
  let submittedArea: string | undefined;
  await page.route("**/api/consultas", async (route) => {
    submittedArea = route.request().postDataJSON().area;
    await route.fulfill({
      status: 503, contentType: "application/json",
      body: JSON.stringify({ error: { message: "El despacho no está disponible. Inténtelo de nuevo." } }),
    });
  });
  await page.getByLabel("Nombre completo").fill("Persona de prueba");
  await page.getByLabel("Teléfono", { exact: true }).fill("3000000000");
  await page.getByLabel("Correo electrónico", { exact: true }).fill("prueba@example.com");
  await page.getByLabel("¿En qué podemos orientarle?").fill("Consulta de prueba que no se almacena.");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Enviar solicitud" }).click();
  await expect(page.getByRole("status")).toContainText("No pudimos registrar");
  expect(submittedArea).toBe(title);
  await expect(page.getByLabel("Área de consulta", { exact: true })).toHaveValue(title);
  await expect(page.getByLabel("¿En qué podemos orientarle?")).toHaveValue("Consulta de prueba que no se almacena.");
  await expect(page.getByText("Solicitud registrada.", { exact: true })).toHaveCount(0);
});

test("unknown service is not rendered as a valid area", async ({ page }) => {
  await page.goto("/servicios/area-que-no-existe", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Esta página no existe" })).toBeVisible();
  await expect(page.getByLabel("Área de consulta", { exact: true })).toHaveCount(0);
});

test("service URLs and intake compatibility preserve the chosen area", () => {
  expect(serviceSlug("Asesorías empresariales")).toBe("asesorias-empresariales");
  const fallback = publicServices([]);
  expect(fallback).toHaveLength(7);
  expect(new Set(fallback.map((service) => service.slug)).size).toBe(7);
  expect(consultationSubject("Derecho civil", "Revisión de contrato.")).toEqual({
    area: "Derecho civil", message: "Revisión de contrato.",
  });
  expect(consultationSubject("Penal", "Revisión de antecedentes.")).toEqual({
    area: "Derecho penal", message: "Área de consulta: Penal.\n\nRevisión de antecedentes.",
  });
  expect(consultationSubject("Administrativo", "Consulta sobre un procedimiento.")).toEqual({
    area: "Otra consulta", message: "Área de consulta: Administrativo.\n\nConsulta sobre un procedimiento.",
  });
});

test("practice icons follow the area name even when the catalogue is reordered", () => {
  const cases = [
    ["Administrativo", "landmark"], ["Ambiental", "leaf"], ["Bancario", "bank"],
    ["Civil", "contract"], ["Comercial", "store"], ["Familia", "family"],
    ["Inmobiliario", "house"], ["Internacional", "globe"], ["Laboral", "briefcase"],
    ["Penal", "shield"], ["Procesal", "file-check"], ["Tributario", "receipt"],
    ["Derecho constitucional", "book"], ["Asesorías empresariales", "building"],
    ["Ley familiar", "family"], ["Derecho de familia", "family"],
    ["  DERECHO LABORAL  ", "briefcase"], ["Área nueva", "scales"],
  ];
  for (const [name, icon] of cases) expect(serviceIconName(name)).toBe(icon);

  const areas = ["Laboral", "Penal", "Familia", "Inmobiliario"].map((name) => ({
    id: name, name, description: null, is_active: true,
  }));
  const original = new Map(publicServices(areas).map((service) => [service.title, service.icon]));
  for (const service of publicServices([...areas].reverse())) {
    expect(service.icon).toBe(original.get(service.title));
  }
  for (const service of publicServices([])) expect(service.icon).not.toBe("scales");
});

test("service cards render matching vector icons without replacing their text labels", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  const cards = page.locator("#servicios article");
  const expected: Record<string, string> = {
    Laboral: "briefcase", "Derecho laboral": "briefcase",
    Penal: "shield", "Derecho penal": "shield",
    Familia: "family", "Ley familiar": "family", Inmobiliario: "house",
    Administrativo: "landmark", Ambiental: "leaf", Bancario: "bank", Civil: "contract",
    Comercial: "store", Internacional: "globe", Procesal: "file-check", Tributario: "receipt",
    "Derecho constitucional": "book", "Derecho civil": "contract", "Derecho comercial": "store",
    "Asesorías empresariales": "building",
  };
  for (const card of await cards.all()) {
    const title = (await card.getByRole("heading").innerText()).trim();
    const icon = card.locator(".service-glyph svg");
    await expect(icon).toHaveAttribute("data-service-icon", expected[title] ?? "scales");
    await expect(icon).toHaveAttribute("aria-hidden", "true");
    await expect(icon.locator("path")).toHaveAttribute("d", /\S+/);
    await expect(card.getByRole("link", { name: `Consultar esta área: ${title}`, exact: true })).toBeAttached();
  }
});
