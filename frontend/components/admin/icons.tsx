import type { IconName } from "@/lib/admin-nav";

/**
 * The icon set.
 *
 * Drawn rather than imported, for the same reason the seal is drawn: an icon
 * font is a network request that can flash, and a library would bring thirty
 * glyphs to use twelve. Every path is 24x24, `stroke-width` 1.6, round joins and
 * caps, so they sit on the same optical weight as the type around them.
 *
 * They are deliberately plain. This interface is an instrument, and an
 * instrument does not decorate its labels.
 */
const PATHS: Record<IconName, string> = {
  // Four panes, the universal "overview".
  dashboard: "M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z",

  // A folder with a ruled spine.
  cases: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",

  // Two figures: the client is always a person, never a row in a table.
  clients:
    "M9 11a3.2 3.2 0 1 0 0-6.4A3.2 3.2 0 0 0 9 11M2.8 19.5c.6-3.1 3.2-5 6.2-5s5.6 1.9 6.2 5M16 11.4a2.6 2.6 0 1 0 0-5.2M17.6 14.4c2.1.5 3.5 2.1 3.9 4.4",

  // The balance, for the people who hold it.
  lawyers:
    "M12 4v16M7 20h10M12 6.5 5 9m7-2.5L19 9M5 9l-2.2 5.4h4.4zM19 9l-2.2 5.4h4.4zM8.4 6.4h7.2",

  // Agenda: a grid with two days marked.
  agenda:
    "M4 6.5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM4 9.5h16M8 3.5v3M16 3.5v3M7.6 13h3v3h-3z",

  // A speech tail.
  messages: "M4 5.5h16v11H9.5L5 20v-3.5H4zM8 9h8M8 12.5h5",

  consultations:
    "M5 4.5h14v15H5zM8.5 8h7M8.5 11.5h7M8.5 15h4M3 7.5h2M3 11.5h2M3 15.5h2",

  // A sheet with a folded corner and ruled lines.
  documents:
    "M6 3.5h7.5L19 9v11.5H6zM13.5 3.5V9H19M9 12.5h7M9 16h4.5",

  // Play inside a frame: audio and video.
  multimedia:
    "M3.5 6.5h17v11h-17zM10 9.8l4.4 2.2-4.4 2.2z",

  // A node with branches, for the assistant that is not built yet.
  ai: "M12 4.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4M6 16.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4M18 16.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4M11 8.5v3.2a2 2 0 0 0 1.1 1.8l4.8 3M13 8.5v3.2a2 2 0 0 1-1.1 1.8l-4.8 3",

  // A receipt with a perforated foot.
  billing:
    "M6 3.5h12v17l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4-2 1.4zM9.5 8.5h5M9.5 12.5h5",

  // A shield with a keyhole.
  security:
    "M12 3.5l7 2.6v5.2c0 4.3-2.9 7.7-7 9.2-4.1-1.5-7-4.9-7-9.2V6.1zM12 10.2a1.6 1.6 0 0 0-.8 3v2.3h1.6v-2.3a1.6 1.6 0 0 0-.8-3",

  // Sliders, for the settings of the system.
  config:
    "M4 7h9M17 7h3M4 17h3M11 17h9M15 4.6v4.8M9 14.6v4.8",
};

/**
 * One icon.
 *
 * `aria-hidden` unconditionally: every icon here sits next to a text label, and a
 * decorative glyph read aloud in Spanish is noise for a screen reader.
 */
export function Icon({
  name,
  className = "size-4",
}: {
  name: IconName;
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

export type ActionIconName = "add" | "edit" | "close" | "deactivate";

const ACTION_PATHS: Record<ActionIconName, string> = {
  add: "M12 5v14M5 12h14",
  edit:
    "M5 19h3.4L18.8 8.6a2.1 2.1 0 0 0-3-3L5.4 16zM13.9 7.5l3 3M5 19h14",
  close:
    "M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM9 13l2 2 4-4",
  deactivate:
    "M9 11a3.2 3.2 0 1 0 0-6.4A3.2 3.2 0 0 0 9 11M2.8 19.5c.6-3.1 3.2-5 6.2-5 1.1 0 2.1.2 3 .7M16 14l5 5M21 14l-5 5",
};

/** Decorative action glyph. The adjacent visible verb remains the accessible name. */
export function ActionIcon({
  name,
  className = "size-4",
}: {
  name: ActionIconName;
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      <path d={ACTION_PATHS[name]} />
    </svg>
  );
}
