import type { ReactNode } from "react";

import { Label } from "@/components/primitives";

/**
 * The header every administration screen opens with.
 *
 * The description line is not decoration. A screen that can create, edit and
 * deactivate records has to say in words what the buttons do, and the honest
 * place for that is under the title, where it is read before the first click
 * rather than after it.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-6 border-b border-rule-strong pb-7">
      <div className="min-w-0">
        {/*
          A short brass rule above the eyebrow. It is the only ornament on the
          screen, and it earns its place because it is the same brass as the
          stamp: the header says "this is a file", not "this is a page".
        */}
        <span aria-hidden="true" className="mb-3 block h-px w-9 bg-brass" />
        <Label>{eyebrow}</Label>
        <h1 className="font-display mt-2 text-[2.35rem] leading-[1.05] tracking-[-0.02em] text-ink">
          {title}
        </h1>
        {description ? (
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink-muted">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/**
 * Pagination.
 *
 * Rendered only when there is more than one page. `total` is rendered even when
 * `items` is empty, because "0 de 0" is an answer and a blank strip is not.
 */
export function Pager({
  total,
  skip,
  limit,
  pageHref,
}: {
  total: number;
  skip: number;
  limit: number;
  pageHref: (skip: number) => string;
}) {
  const shown = total === 0 ? 0 : Math.min(limit, total - skip);
  const from = total === 0 ? 0 : skip + 1;
  const to = skip + shown;

  return (
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-4 text-xs text-ink-muted">
      <p className="tnum">
        {from}–{to} de {total}
      </p>
      {total > limit ? (
        <nav aria-label="Paginación" className="flex items-center gap-1">
          <PagerLink
            href={pageHref(Math.max(0, skip - limit))}
            disabled={skip === 0}
          >
            Anterior
          </PagerLink>
          <PagerLink
            href={pageHref(skip + limit)}
            disabled={skip + limit >= total}
          >
            Siguiente
          </PagerLink>
        </nav>
      ) : null}
    </div>
  );
}

function PagerLink({
  href,
  disabled,
  children,
}: {
  href: string;
  disabled: boolean;
  children: ReactNode;
}) {
  const className =
    "rounded-card border px-3 py-1.5 font-semibold uppercase tracking-[0.1em] transition-colors";

  if (disabled) {
    return (
      <span className={`${className} cursor-not-allowed border-rule text-ink-faint`}>
        {children}
      </span>
    );
  }

  return (
    <a href={href} className={`${className} border-rule-strong hover:border-wax hover:text-wax`}>
      {children}
    </a>
  );
}

/**
 * A filter strip that is a plain GET form.
 *
 * No client component and no JavaScript: the filter states live in the URL, so a
 * filtered list is a link anybody can paste into a message and the browser's back
 * button behaves. The one thing it costs is a full page render per search, which
 * for a list of a few hundred records is the right trade.
 */
export function FilterBar({ children }: { children: ReactNode }) {
  return (
    <form
      method="get"
      className="mt-6 flex flex-wrap items-end gap-x-3 gap-y-3 rounded-card border border-rule bg-surface px-4 py-4 shadow-card"
    >
      {children}
    </form>
  );
}

export function FilterField({
  label,
  name,
  defaultValue,
  placeholder,
  type = "search",
  className = "",
}: {
  label: string;
  name: string;
  defaultValue?: string;
  placeholder?: string;
  type?: string;
  className?: string;
}) {
  // `filtro-` prefix: the listing also renders the "new record" drawer, and
  // both use names like `status` or `priority`. A repeated id would point the
  // filter label at the drawer's control instead of the filter's own.
  const id = `filtro-${name}`;
  const isSearch = type === "search";
  return (
    <div className={className}>
      <label htmlFor={id} className="label-rule block">
        {label}
      </label>
      <div className="relative mt-1.5">
        {isSearch ? (
          /*
            A magnifier drawn in CSS, not an icon font: it sits inside the field,
            so it has to inherit the field's own ink or it looks pasted on.
          */
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-faint"
          >
            <circle cx="9" cy="9" r="5.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="m13.2 13.2 3.4 3.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        ) : null}
        <input
          id={id}
          name={name}
          type={type}
          defaultValue={defaultValue ?? ""}
          placeholder={placeholder}
          className={`w-full rounded-card border border-rule-strong bg-surface-sunk py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-wax focus:bg-surface ${isSearch ? "pl-9 pr-3" : "px-3"}`}
        />
      </div>
    </div>
  );
}