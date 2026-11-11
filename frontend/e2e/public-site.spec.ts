import { mkdir } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";
import { expectCorporateBrand, expectSemanticContrast } from "./brand-assertions";

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
    await expect(page.locator("#servicios article")).toHaveCount(7);
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
