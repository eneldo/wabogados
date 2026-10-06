import type { ReactNode } from "react";

import type { Tone } from "@/lib/format";

/**
 * The small vocabulary the whole interface is built from.
 *
 * Each piece is a server component with no state. Anything interactive is a
 * separate client component, which keeps the client bundle to the parts that
 * genuinely need it.
 */

const TONE_CLASS: Record<Tone, string> = {
  neutral: "bg-paper-deep text-ink-soft ring-rule-strong",
  forest: "bg-forest-tint text-forest ring-forest/30",
  brass: "bg-brass-tint text-brass ring-brass/30",
  wax: "bg-wax-tint text-wax-deep ring-wax/30",
  ink: "bg-ink text-paper ring-ink",
};

/** The dot that carries the colour, so the word beside it can stay quiet. */
const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-ink-faint",
  forest: "bg-forest",
  brass: "bg-brass",
  wax: "bg-wax",
  ink: "bg-ink",
};

/** Text colour alone, for the dot variant that paints no background. */
const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-ink-muted",
  forest: "text-forest",
  brass: "text-brass",
  wax: "text-wax-deep",
  ink: "text-ink",
};

export function Chip({
  tone = "neutral",
  dot = false,
  children,
  className = "",
}: {
  tone?: Tone;
  /**
   * Leads with a dot instead of a filled pill.
   *
   * Two pills side by side in the same row read as two shouts. On a row that
   * already carries a name, a number and three other values, the colour is what
   * needs to be seen from across the desk and the word is only confirmation.
   */
  dot?: boolean;
  children: ReactNode;
  className?: string;
}) {
  if (dot) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-[0.6875rem] font-semibold uppercase tracking-[0.1em] ${TONE_TEXT[tone]} ${className}`}
      >
        <span
          aria-hidden="true"
          className={`size-[5px] shrink-0 rounded-full ${TONE_DOT[tone]}`}
        />
        {children}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[0.6875rem] font-semibold uppercase tracking-[0.1em] ring-1 ring-inset ${TONE_CLASS[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Label({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <p className={`label-rule ${className}`}>{children}</p>;
}

/** A value under a label, the way a field appears on a form. */
export function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <Label>{label}</Label>
      <div className="mt-1 text-ink">{children}</div>
    </div>
  );
}

/**
 * A SHA-256 shown as a fingerprint.
 *
 * The full digest is present in the DOM, not truncated away: someone checking a
 * chain of custody needs to copy the whole value, and a chip that hides it
 * invites a screenshot instead.
 */
export function HashChip({
  value,
  short,
  tone = "neutral",
}: {
  value: string | null | undefined;
  short?: string;
  tone?: Tone;
}) {
  if (!value) {
    return (
      <span className="tnum text-xs text-ink-faint">
        Sin hash registrado
      </span>
    );
  }
  return (
    <span
      title={value}
      className={`tnum inline-flex items-center rounded-sm px-1.5 py-0.5 text-[0.6875rem] ring-1 ring-inset ${TONE_CLASS[tone]}`}
    >
      {short ?? value.slice(0, 16)}
    </span>
  );
}

export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "div" | "aside";
}) {
  return (
    <Tag
      className={`rounded-card border border-rule bg-surface shadow-card ${className}`}
    >
      {children}
    </Tag>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow ? <Label>{eyebrow}</Label> : null}
        <h2 className="font-display mt-1 text-2xl leading-tight sm:text-[1.75rem]">
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

/**
 * A standing rule of the system, said out loud under the thing it governs.
 *
 * It looks like a note but it is not decoration: it is the reason there is no
 * delete button, written where the absence of that button would otherwise look
 * like an oversight. The brass rule is the same colour as the stamp, so it reads
 * as part of the instrument rather than as a tooltip someone added.
 */
export function RuleNote({ children }: { children: ReactNode }) {
  return (
    <p className="mt-6 flex gap-3 border-l-2 border-brass/50 pl-3.5 text-xs leading-relaxed text-ink-muted">
      {children}
    </p>
  );
}

/**
 * The mark.
 *
 * A seal over ruled paper: the two marks of a legal file. Drawn in CSS and
 * inline SVG rather than shipped as an asset, so it never flickers and never
 * needs a network round trip.
 */
export function Seal({ className = "size-9" }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-grid place-items-center rounded-full border-2 border-wax/70 text-wax ${className}`}
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-[58%]">
        <path
          d="M6 3h9l4 4v14H6z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M15 3v4h4" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M9 12h7M9 16h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-card border border-dashed border-rule-strong bg-surface-sunk px-6 py-12 text-center">
      <p className="font-display text-xl text-ink-soft">{title}</p>
      {hint ? <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{hint}</p> : null}
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
    </div>
  );
}
