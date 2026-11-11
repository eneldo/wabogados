import { expect, type Page } from "@playwright/test";

/** Checks downloaded artwork and computed colors, not only class names. */
export async function expectCorporateBrand(page: Page) {
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(37, 43, 57)");
  await expect(page.locator("body")).toHaveCSS("color", "rgb(245, 246, 248)");
  const logo = page.locator(".brand-logo__image:visible").first();
  await expect(logo).toBeVisible();
  await expect(logo).toHaveJSProperty("complete", true);
  const image = await logo.evaluate((element: HTMLImageElement) => {
    const box = element.getBoundingClientRect();
    return { natural: element.naturalWidth, ratio: box.width / box.height, original: element.naturalWidth / element.naturalHeight, withinViewport: box.left >= 0 && box.right <= innerWidth };
  });
  expect(image.natural).toBeGreaterThan(80);
  expect(image.ratio).toBeCloseTo(image.original, 1);
  expect(image.withinViewport).toBe(true);
}

export async function expectSemanticContrast(page: Page) {
  const ratios = await page.evaluate(() => {
    function rgb(token: string) {
      const sample = document.createElement("span");
      sample.style.color = `var(${token})`;
      document.body.append(sample);
      const value = getComputedStyle(sample).color;
      sample.remove();
      return value.match(/[\d.]+/g)!.slice(0, 3).map(Number);
    }
    function luminance(values: number[]) {
      const linear = values.map((value) => {
        const channel = value / 255;
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
    }
    return [
      ["--color-on-action", "--color-action"],
      ["--color-ink", "--color-surface"],
      ["--color-ink-muted", "--color-surface"],
      ["--color-ink-faint", "--color-surface"],
      ["--color-forest", "--color-forest-tint"],
      ["--color-brass", "--color-brass-tint"],
      ["--color-wax-deep", "--color-wax-tint"],
    ].map(([foreground, background]) => {
      const a = luminance(rgb(foreground));
      const b = luminance(rgb(background));
      return { foreground, background, contrast: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) };
    });
  });
  for (const pair of ratios) expect(pair.contrast, `${pair.foreground} on ${pair.background}`).toBeGreaterThanOrEqual(4.5);
}
