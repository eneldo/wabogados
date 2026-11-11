import "server-only";

import { cache } from "react";
import { unstable_cache } from "next/cache";

import { apiFetch } from "./api";
import { publicServices } from "./public-services";
import type { LegalAreaOption } from "./types";

// Public catalogue only, never identities or client records. Successful reads
// are shared briefly across pages; failures must not replace the cache with an
// offline fallback. This avoids one backend call per card/page navigation.
const loadCatalogue = unstable_cache(
  () => apiFetch<LegalAreaOption[]>("/api/v1/public/legal-areas", { anonymous: true }),
  ["public-service-catalogue"],
  { revalidate: 30 },
);

export const getPublicServices = cache(async () => {
  try {
    const areas = await loadCatalogue();
    return { services: publicServices(areas), available: true };
  } catch {
    return { services: publicServices([]), available: false };
  }
});
