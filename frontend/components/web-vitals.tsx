"use client";

import { useReportWebVitals } from "next/web-vitals";

/**
 * Reports Core Web Vitals to the console in development and to the backend
 * in production (placeholder endpoint). Keeps the page dynamic cost low.
 */
export function WebVitals() {
  useReportWebVitals((metric) => {
    if (process.env.NODE_ENV !== "production") {
      console.debug("[web-vitals]", metric.name, Math.round(metric.value));
      return;
    }
    const body = JSON.stringify(metric);
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/vitals", body);
    }
  });
  return null;
}