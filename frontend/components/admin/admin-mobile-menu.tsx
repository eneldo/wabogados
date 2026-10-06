"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { AdminRail } from "@/components/admin/admin-rail";
import { Seal } from "@/components/primitives";
import type { AdminModule } from "@/lib/admin-nav";
import { initialsOf } from "@/lib/format";

/**
 * The menu a phone gets.
 *
 * Until now a narrow screen got the twelve modules as a horizontal strip of
 * chips that scrolled sideways. It was honest — every module was one tap away —
 * and it was wrong: the person had to scroll a menu to find out what existed,
 * the three planned modules were filtered out of it because they have no `href`,
 * and the row of chips pushed the content of every screen down by a bar nobody
 * asked for.
 *
 * This is the ordinary answer: a bar with the mark on the left and a hamburger
 * on the right, and the twelve modules inside. It has the same information
 * architecture as the desktop rail, which is the point — including the footer
 * with the person and the two exits, and including the planned modules with the
 * reason they are inert.
 *
 * The rules it follows, all of which cost more than the button does:
 *
 * - The toggle is a real `<button>` with `aria-expanded` and `aria-controls`, not
 *   a div that happens to look like one.
 * - The panel is unmounted when closed, so its links are not in the tab order and
 *   a screen reader does not announce a menu that is not there.
 * - Escape closes it, and the focus returns to the button that opened it.
 * - It closes by itself on navigation. A menu that stays open over the page you
 *   just asked for is a menu that has become a second navigation.
 * - Opening moves focus inside. Without it, keyboard focus stays behind the
 *   overlay and the next Tab walks the page under a menu that is on top of it.
 */
export function AdminMobileMenu({
  modules,
  profile,
  signOut,
}: {
  modules: AdminModule[];
  profile: { name: string; roleLabel: string };
  /** The server action, passed down from the layout so the client never imports it. */
  signOut: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const panelId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);

  /*
    Navigating elsewhere means the menu has done its job, and it must not stay
    open over the page just requested — that turns a menu into a second
    navigation bar.

    Done during render and not in an effect: this is React's pattern for "reset
    state when an input changed", and it handles every route change, including
    the browser's back button, without waiting a frame. An effect would also be
    rejected here, because `setState` inside an effect body is the cascade that
    this rule exists to prevent.
  */
  const [openedFor, setOpenedFor] = useState(pathname);
  if (openedFor !== pathname) {
    setOpenedFor(pathname);
    if (open) setOpen(false);
  }

  /* Escape closes, and focus goes back where it came from. */
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      toggleRef.current?.focus();
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  /*
    Move focus inside on open, and stop the page behind from scrolling with it.
    A menu that leaves the background scrollable scrolls the content out from
    under the panel, and on a phone that is how the menu ends up floating over a
    different page than the one it belongs to.
  */
  useEffect(() => {
    if (!open) return;

    panelRef.current?.querySelector<HTMLElement>("a, button, [tabindex]")?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <div className="border-b border-rule-strong bg-ink lg:hidden">
      <div className="flex items-center gap-3 px-4 py-3">
        <Seal className="size-7 text-wax" />
        <span className="font-display text-paper">WABOGADOS</span>

        <button
          ref={toggleRef}
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls={panelId}
          className="ml-auto grid size-10 place-items-center rounded-card border border-paper/20 text-paper transition-colors hover:border-paper/45 hover:bg-white/8"
        >
          <span className="sr-only">
            {open ? "Cerrar el menú de administración" : "Abrir el menú de administración"}
          </span>
          {/*
            Three lines that become a cross. Drawn as spans rather than as a glyph
            so it never depends on a font that is not loaded, and so the shape can
            animate without a framework.
          */}
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.9"
            strokeLinecap="round"
          >
            <path
              d="M4 7h16"
              className={`origin-center transition-transform duration-200 ${open ? "translate-y-[5px] rotate-45" : ""}`}
            />
            <path
              d="M4 12h16"
              className={`transition-opacity duration-150 ${open ? "opacity-0" : "opacity-100"}`}
            />
            <path
              d="M4 17h16"
              className={`origin-center transition-transform duration-200 ${open ? "-translate-y-[5px] -rotate-45" : ""}`}
            />
          </svg>
        </button>
      </div>

      {open ? (
        <div
          id={panelId}
          ref={panelRef}
          className="rise max-h-[calc(100dvh-3.75rem)] overflow-y-auto border-t border-paper/12 px-3 pb-3 pt-2"
        >
          <nav aria-label="Administración">
            <AdminRail modules={modules} onNavigate={close} />
          </nav>

          {/*
            The same footer the desktop rail has. On a phone it was missing
            entirely: no role, no second exit, and signing out meant finding the
            one control that happened to be in the bar.
          */}
          <div className="mt-2 border-t border-paper/12 px-2 pt-3">
            <div className="flex items-center gap-2.5">
              <span
                aria-hidden="true"
                className="grid size-8 shrink-0 place-items-center rounded-full bg-wax text-[0.6875rem] font-bold text-paper"
              >
                {initialsOf(profile.name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-paper">
                  {profile.name}
                </span>
                <span className="block truncate text-[0.6875rem] text-paper/50">
                  {profile.roleLabel}
                </span>
              </span>
            </div>

            <div className="mt-3 flex items-center gap-4 text-[0.6875rem] text-paper/55">
              <Link href="/portal" className="transition-colors hover:text-paper">
                Mi panel
              </Link>
              <Link href="/" className="transition-colors hover:text-paper">
                Web pública
              </Link>
              <form action={signOut} className="ml-auto">
                <button type="submit" className="transition-colors hover:text-paper">
                  Salir
                </button>
              </form>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}