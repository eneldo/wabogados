"use client";

import { useEffect, useRef } from "react";

// Memory only: no cookies, storage, fingerprint, account or cross-tab identity.
let navigationId: string | undefined;

function optedOut(): boolean {
  return navigator.doNotTrack === "1" ||
    (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl === true;
}

export function PublicAnalytics({ path, enabled = true }: { path: string; enabled?: boolean }) {
  const tracked = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || optedOut() || typeof crypto.randomUUID !== "function") return;
    navigationId ??= crypto.randomUUID();
    const visitor = navigationId;
    function send(kind: "page_view" | "phone_click") {
      if (optedOut()) return;
      void fetch("/api/estadisticas", {
        method: "POST", credentials: "omit", referrerPolicy: "no-referrer",
        headers: { "Content-Type": "application/json" }, cache: "no-store", keepalive: true,
        body: JSON.stringify({ event_id: crypto.randomUUID(), visitor_id: visitor, kind, path }),
      }).catch(() => { /* Metrics must never interrupt navigation or a consultation. */ });
    }
    if (tracked.current !== path) {
      tracked.current = path;
      send("page_view");
    }
    function onClick(event: MouseEvent) {
      if (event.target instanceof Element && event.target.closest('a[href^="tel:"]')) {
        send("phone_click");
      }
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [path, enabled]);

  return null;
}
