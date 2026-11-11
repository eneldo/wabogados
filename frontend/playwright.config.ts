import { defineConfig, devices } from "@playwright/test";

/**
 * Frontend layout gate.
 *
 * These checks exist because the three failures they look for produce **no
 * visible error**: a duplicated `id` leaves every `<label for>` pointing at
 * whichever control the browser finds first, and a horizontal overflow just makes
 * a page feel wrong on a phone. Neither shows up in `next build`, `tsc` or ESLint,
 * and both were found by hand more than once — the memory lists three separate
 * occasions.
 *
 * They run against the **built** application, not `next dev`, because the same
 * memory records a session where the container kept serving the previous image
 * and the verification passed against code that was not running.
 */

const PORT = Number(process.env.FRONTEND_PORT ?? 3000);
const BASE_URL = process.env.FRONTEND_BASE_URL ?? `http://127.0.0.1:${PORT}`;

/**
 * Widths the administration is actually read at.
 *
 * 320 is the narrowest phone still in use, 390 the one the recent work verified
 * by hand, 768 a tablet in portrait and 1440 a laptop. A page that survives only
 * the widest of them is not responsive.
 */
const WIDTHS = [320, 390, 768, 1440] as const;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: BASE_URL,
    trace: "off",
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "public",
      testMatch: /public-site\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "private",
      testMatch: /admin-portal\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "layout",
      testIgnore: [/public-site\.spec\.ts/, /admin-portal\.spec\.ts/],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth.json",
      },
      dependencies: ["setup"],
    },
  ],
});

export { WIDTHS };
