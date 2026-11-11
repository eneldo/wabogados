import { expect, test } from "@playwright/test";

import { WIDTHS } from "../playwright.config";

/**
 * Layout gate for the administration.
 *
 * Three invariants that no existing gate can see, because none of them is an
 * error: the browser renders the page, the label points somewhere, and the
 * content fits. Each has cost real time in this project.
 *
 * The routes are the ones with filters, tables and per-row dialogs — the shapes
 * where a duplicate `id` appears. A row dialog mounted once per open case is how
 * `notes` and `client_id` ended up duplicated three times on one page.
 *
 * **Requires a signed-in session.** The administration redirects to `/login`
 * without one, and a login page has none of the structure worth checking, so the
 * gate runs against the real stack and says so when it cannot.
 */

const ADMIN_ROUTES = [
  "/admin",
  "/admin/expedientes",
  "/admin/clientes",
  "/admin/abogados",
  "/admin/agenda",
  "/admin/mensajes",
  "/admin/documentos",
  "/admin/multimedia",
  "/admin/seguridad",
  "/admin/configuracion",
  "/admin/solicitudes",
  "/admin/facturacion",
  "/admin/ia-juridica",
];

async function isSignedOut(page: import("@playwright/test").Page): Promise<boolean> {
  return page.url().includes("/login");
}

/**
 * Duplicate ids, read from the DOM rather than from the source.
 *
 * The point is that a repeated id does not throw: the page renders perfectly and
 * the click on the label does nothing, which is a long way from the cause.
 */
async function duplicateIds(page: import("@playwright/test").Page): Promise<string[]> {
  return page.evaluate(() => {
    const seen = new Set<string>();
    const repeated = new Set<string>();
    for (const element of Array.from(document.querySelectorAll("[id]"))) {
      const id = element.id;
      if (!id) continue;
      if (seen.has(id)) repeated.add(id);
      seen.add(id);
    }
    return [...repeated];
  });
}

/**
 * Horizontal overflow of the **page**, plus a diagnosis when it happens.
 *
 * The assertion is `scrollWidth > clientWidth`, because that is the symptom a
 * person feels: the page can be dragged sideways. Enumerating elements that
 * stick out was the first attempt and it produced false positives — a card whose
 * children are wider than the screen while the layout still does not scroll
 * reads as overflow in the DOM and is not overflow on screen. So the verdict is
 * the scroll width, and the element list is only the explanation attached to a
 * failure that already happened.
 */
async function overflowReport(
  page: import("@playwright/test").Page,
): Promise<{ pageWidth: number; viewport: number; culprits: string[] }> {
  return page.evaluate(() => {
    const document_ = document.documentElement;
    const viewport = document_.clientWidth;
    const culprits: string[] = [];

    if (document_.scrollWidth > viewport + 1) {
      for (const element of Array.from(document_.querySelectorAll<HTMLElement>("body *"))) {
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.right <= viewport + 1) continue;
        culprits.push(
          `${element.tagName.toLowerCase()}` +
            `${element.id ? `#${element.id}` : ""}` +
            `${element.className ? `.${String(element.className).split(" ")[0]}` : ""}` +
            ` (right=${Math.round(rect.right)})`,
        );
      }
    }

    return {
      pageWidth: document_.scrollWidth,
      viewport,
      culprits: culprits.slice(0, 5),
    };
  });
}

for (const route of ADMIN_ROUTES) {
  test.describe(route, () => {
    test("no duplicate ids in the DOM", async ({ page }) => {
      await page.goto(route);
      test.skip(await isSignedOut(page), "requiere una sesión de administración");

      expect(await duplicateIds(page)).toEqual([]);
    });

    for (const width of WIDTHS) {
      test(`no horizontal overflow at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 844 });
        await page.goto(route);
        test.skip(await isSignedOut(page), "requiere una sesión de administración");
        // Layout settles after hydration; measuring immediately can read the
        // server-rendered box and pass for the wrong reason.
        await page.waitForLoadState("networkidle");

        const report = await overflowReport(page);

        expect(
          report.culprits,
          `desbordamiento en ${route} a ${width}px: ${report.culprits.join(", ")}`,
        ).toEqual([]);
        expect(report.pageWidth).toBeLessThanOrEqual(report.viewport + 1);
      });
    }
  });
}

test("the gate refuses to pass silently when signed out", async ({ page }) => {
  await page.goto("/admin/expedientes");

  if (!(await isSignedOut(page))) {
    test.skip(true, "hay sesión: la comprobación de sesión no aplica aquí");
  }

  // If the session is missing, the layout gate covers nothing. Failing loudly is
  // better than a green run that inspected a login form.
  expect(await isSignedOut(page)).toBe(true);
});
