import type { ServiceIconName } from "@/lib/public-services";

/** Consistent outline illustrations; no icon fonts or external dependencies. */
const PATHS: Record<ServiceIconName, string> = {
  landmark: "M3 9 12 4l9 5H3ZM5 10v8m5-8v8m4-8v8m5-8v8M3 21h18M4 18h16",
  leaf: "M20 4C10 2 3 7 4 14c1 6 9 8 13 2 2-3 2-7 3-12ZM4 21 15 10M9 16v-5m0 5h5",
  bank: "M3 8 12 3l9 5H3Zm3 3v5m12-5v5M3 21h18M5 18h14M12 10v5m-1-1h2m-2-3h2",
  contract: "M5 3h9l5 5v13H5V3Zm9 0v5h5M8 11h7m-7 4h4m1 3 2-2 2 2",
  store: "M4 10v11h16V10M3 4h18l1 6a3 3 0 0 1-5 2 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-5-2l1-6ZM9 21v-6h6v6",
  family: "M7 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm10 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 20v-5a4 4 0 0 1 6-3m14 8v-5a4 4 0 0 0-6-3M12 16a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm-4 5v-1a4 4 0 0 1 8 0v1",
  house: "M3 11 12 3l9 8M5 10v11h14V10M9 21v-8h6v8M16 4h3v5",
  globe: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM2 12h20M12 2c-6 5-6 15 0 20 6-5 6-15 0-20ZM4 6h16M4 18h16",
  briefcase: "M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M3 6h18v14H3V6Zm0 6a22 22 0 0 0 18 0M10 11h4v4h-4v-4Z",
  shield: "M12 3 21 7v5c0 5-5 8-9 10-4-2-9-5-9-10V7l9-4Zm-4 9 3 3 5-6",
  "file-check": "M5 3h9l5 5v13H5V3Zm9 0v5h5M8 11h4m-4 5 2 2 5-5",
  receipt: "M5 3h14v19l-3-2-4 2-4-2-3 2V3Zm3 4h8M8 11h3m-3 4h3m3-4h2m-2 4h2",
  book: "M12 5C9 3 5 3 2 4v16c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Zm0 0v16M5 8h3m-3 4h3m8-4h3m-3 4h3",
  building: "M5 22V3h14v19M2 22h20M9 22v-5h6v5M9 7h1m4 0h1m-6 4h1m4 0h1",
  scales: "M12 3v18M7 21h10M4 7h16M5 7l-3 7h6L5 7Zm14 0-3 7h6l-3-7ZM2 14a3 3 0 0 0 6 0m8 0a3 3 0 0 0 6 0",
};

export function ServiceIcon({ name }: { name: ServiceIconName }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      data-service-icon={name}
      viewBox="0 0 24 24"
      width={26}
      height={26}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
