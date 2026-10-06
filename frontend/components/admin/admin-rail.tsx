"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon } from "@/components/admin/icons";
import type { AdminModule } from "@/lib/admin-nav";

/**
 * The administration rail.
 *
 * A client component for one reason: `usePathname`. The module list itself is
 * rendered by the server layout, which knows the caller's permissions, so the
 * list never has to round-trip to decide what this person may see.
 *
 * The active item is decided by **prefix**, not equality, with one exception for
 * the dashboard itself. `/admin/clientes` is the active item while the user is
 * editing `/admin/clientes/8f3c…`, and an equality test would drop the highlight
 * the moment a record is opened — the one moment the person most needs to know
 * where they are. `/admin` is the exception, because every screen here starts
 * with it and it would otherwise be lit on every page.
 */

export function AdminRail({
  modules,
  onNavigate,
}: {
  modules: AdminModule[];
  /**
   * Called after a module is chosen.
   *
   * The desktop rail never passes it; the mobile panel does, so the menu is
   * gone before the new page paints instead of on the render that follows it.
   */
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav aria-label="Administración" className="flex flex-col gap-0.5">
      {modules.map((module) => {
        const usable = module.state !== "planned" && Boolean(module.href);
        const target = module.href ?? `/admin/modulo/${module.slug}`;

        /*
          Active by **prefix**, with one exception.

          `/admin/clientes` must stay lit while the user is editing
          `/admin/clientes/8f3c…`: an equality test drops the highlight at exactly
          the moment the person most needs to know where they are.

          The exception is the dashboard. Its href is `/admin`, and every screen in
          this surface starts with `/admin/`, so the prefix rule matched it
          everywhere and the menu showed two lit items at once — the dashboard and
          the module actually being viewed. The index of the surface is lit only
          when it is the surface.
        */
        const isIndex = module.href === "/admin";
        const active =
          module.href !== undefined &&
          (pathname === module.href ||
            (!isIndex && pathname.startsWith(`${module.href}/`)));

        const base =
          "flex items-center gap-2.5 rounded-card px-2.5 py-2 text-sm transition-colors";
        const tone = active
          ? "bg-white/12 text-paper"
          : usable
            ? "text-paper/70 hover:bg-white/8 hover:text-paper"
            : "cursor-not-allowed text-paper/35";

        const content = (
          <>
            <Icon name={module.icon} className="size-[1.05rem]" />
            <span className="flex-1 truncate">{module.label}</span>
            {module.state === "planned" ? (
              <span className="rounded-full border border-paper/25 px-1.5 text-[0.5625rem] font-semibold uppercase tracking-[0.1em]">
                Pronto
              </span>
            ) : null}
            {module.state === "building" ? (
              <span
                className="size-1.5 rounded-full bg-paper/40"
                title={module.note}
              />
            ) : null}
          </>
        );

        if (!usable) {
          return (
            <span
              key={module.slug}
              className={`${base} ${tone}`}
              title={module.note}
              aria-disabled="true"
            >
              {content}
            </span>
          );
        }

        return (
          <Link
            key={module.slug}
            href={target}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`${base} ${tone}`}
          >
            {content}
          </Link>
        );
      })}
    </nav>
  );
}