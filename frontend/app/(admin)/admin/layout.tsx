import Link from "next/link";
import { redirect } from "next/navigation";

import { AdminMobileMenu } from "@/components/admin/admin-mobile-menu";
import { AdminRail } from "@/components/admin/admin-rail";
import { Seal } from "@/components/primitives";
import { signOut } from "@/features/admin/sign-out";
import { visibleModules } from "@/lib/admin-nav";
import { initialsOf } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";

/**
 * The administration shell.
 *
 * Two things happen here that did not happen anywhere before, because there was
 * no subroute layout until now:
 *
 * 1. **The session check.** It lived in each page, which meant every new page
 *    had to remember to do it. A forgotten check is an open door, so the guard
 *    belongs to the layout that owns the whole surface.
 * 2. **The rail.** The modules are filtered by the caller's permissions here,
 *    once, from a server component. The rail client component below only decides
 *    which item is highlighted.
 *
 * A client is not redirected away from this layout with a redirect loop; the
 * check below sends them to their own portal, because a client who types an
 * admin URL deserves to be told where they belong rather than shown a menu
 * half of which they cannot open.
 */

/*
  `overflow-x: clip`, and the reason is a data table.

  A six-column identity table does not fit on a phone. It scrolls inside its own
  box — that is the point of `min-w` on the table and `overflow-x: auto` on its
  wrapper — but the row box itself still contributes to the *scrollable overflow*
  of the shell, and the whole administration area ends up panning sideways: the
  reader swipes and the entire page, header included, slides out of view.

  `clip` and not `hidden`: `hidden` would make this a scroll container, which is
  exactly the behaviour being removed, and it would break any `sticky` child. The
  shell is not allowed to scroll sideways; the table is.
*/
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");

  if (session.kind === "unavailable") {
    /*
      Rendered here rather than thrown. The alternative is an error boundary that
      a clerk meets every time the database blinks, and the only honest thing on
      screen in that moment is the sentence the backend actually sent.
    */
    return (
      <main className="mx-auto max-w-2xl px-6 py-24 text-center">
        <h1 className="font-display text-2xl text-ink">Servicio no disponible</h1>
        <p className="mt-3 text-sm text-ink-muted">{session.message}</p>
        <Link
          href="/"
          className="mt-8 inline-block text-xs font-semibold uppercase tracking-[0.14em] text-wax underline-offset-4 hover:underline"
        >
          Volver al inicio
        </Link>
      </main>
    );
  }

  const { profile } = session;
  if (profile.isClient) redirect("/portal");

  const modules = visibleModules(profile.permissions);

  return (
    <div className="min-h-screen overflow-x-clip">
      {/*
        `fixed` rather than a grid column: the rail must stay put while a long
        client list scrolls. `w-[16.5rem]` matches the grid track exactly, so the
        content column does not shift when the rail is in view.
      */}
      <aside className="hidden bg-ink lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-[16.5rem] lg:flex-col">
        <div className="flex items-center gap-2.5 px-5 pt-6 pb-5">
          <Seal className="size-9 text-wax" />
          <span>
            <span className="font-display block text-lg leading-none text-paper">
              WABOGADOS
            </span>
            <span className="mt-1 block text-[0.5625rem] font-semibold uppercase tracking-[0.24em] text-paper/45">
              Administración
            </span>
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pb-4">
          <AdminRail modules={modules} />
        </div>

        <div className="border-t border-paper/12 px-4 py-4">
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

          <div className="mt-3 flex gap-3 text-[0.6875rem] text-paper/55">
            <Link href="/portal" className="transition-colors hover:text-paper">
              Mi panel
            </Link>
            <Link href="/" className="transition-colors hover:text-paper">
              Web pública
            </Link>
            <form action={signOut} className="ml-auto">
              <button
                type="submit"
                className="transition-colors hover:text-paper"
              >
                Salir
              </button>
            </form>
          </div>
        </div>
      </aside>

      {/*
        Without the rail — a phone, or a tablet in portrait — the same twelve
        modules are needed, so they go behind a hamburger. They used to be a
        horizontal strip of chips that scrolled sideways, which put a menu in the
        way of every screen, hid the three planned modules because they have no
        `href`, and left a phone without the role or the second exit. The panel
        inside the button has the same contents as the desktop rail.
      */}
      <AdminMobileMenu
        modules={modules}
        profile={{ name: profile.name, roleLabel: profile.roleLabel }}
        signOut={signOut}
      />

      {/*
        The rail is `position: fixed`, so it takes no part in the flow and
        reserves no grid track. A two-column grid would therefore place `main` in
        column one — the 16.5rem rail — and slide the whole page underneath it.
        The clearance is this padding, and it has to match the rail's width
        exactly.
      */}
      <main className="min-w-0 px-5 py-8 sm:px-8 lg:pl-[calc(16.5rem+2.5rem)] lg:pr-10 lg:py-10">
        {children}
      </main>
    </div>
  );
}