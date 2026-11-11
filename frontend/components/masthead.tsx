import Link from "next/link";
import type { ReactNode } from "react";

import { BrandLogo } from "./brand-logo";

/**
 * The shell both audiences share.
 *
 * A masthead rather than a sidebar: a Spanish law firm reads as a document
 * with a header, not as an application with a rail. The full-bleed rule under
 * the title is the one gesture that ties the whole thing together.
 */
export function Masthead({
  eyebrow,
  title,
  nav,
  profile,
  children,
}: {
  eyebrow: string;
  title: string;
  nav: Array<{ href: string; label: string; active?: boolean }>;
  profile?: { name: string; role: string; unread?: number };
  children?: ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-rule-strong bg-surface">
        <div className="workspace-container pt-6 pb-0">
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="flex min-w-0 flex-wrap items-center gap-4">
              <Link href="/" aria-label="WABOGADOS, web pública">
                <BrandLogo size="compact" priority />
              </Link>
              <span className="min-w-0">
                <span className="block text-[0.625rem] font-semibold uppercase tracking-[0.28em] text-ink-muted">
                  {eyebrow}
                </span>
                <span className="font-display block text-2xl leading-none text-ink">
                  {title}
                </span>
              </span>
            </div>

            {profile ? <ProfileBadge profile={profile} /> : null}
          </div>

          {nav.length > 0 ? (
            /*
              `overflow-y-hidden` is not optional here. With only `overflow-x`
              set, CSS computes the other axis to `auto`, and the active tab's
              rule — which sits on the bottom edge — then overflows by a pixel
              and draws a vertical scrollbar down the side of the navigation.
            */
            <nav
              aria-label="Principal"
              className="mt-7 -mb-px flex gap-1 overflow-x-auto overflow-y-hidden"
            >
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={item.active ? "page" : undefined}
                  className={`relative shrink-0 px-3.5 pt-2.5 pb-3 text-sm font-medium transition-colors ${
                    item.active
                      ? "text-ink"
                      : "text-ink-muted hover:text-ink"
                  }`}
                >
                  {item.label}
                  {item.active ? (
                    <span className="draw-rule absolute inset-x-2 bottom-0 h-0.5 bg-wax" />
                  ) : null}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
      </header>

      <main className="workspace-container py-10">{children}</main>

      <footer className="workspace-container pb-12">
        <div className="border-t border-rule pt-5 text-xs text-ink-faint">
          <p>
            WABOGADOS V1 · La información de este portal es confidencial y está
            cubierta por secreto profesional.
          </p>
        </div>
      </footer>
    </div>
  );
}

function ProfileBadge({
  profile,
}: {
  profile: { name: string; role: string; unread?: number };
}) {
  return (
    <div className="flex items-center gap-3">
      {profile.unread && profile.unread > 0 ? (
        <span className="live-dot inline-flex size-6 items-center justify-center rounded-full bg-action text-[0.6875rem] font-bold text-on-action">
          {profile.unread > 9 ? "9+" : profile.unread}
        </span>
      ) : null}
      <div className="text-right">
        <p className="text-sm font-semibold leading-tight text-ink">{profile.name}</p>
        <p className="text-xs text-ink-muted">{profile.role}</p>
      </div>
    </div>
  );
}
