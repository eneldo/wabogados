"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { DrawRule } from "./reveal";
import { BrandLogo } from "@/components/brand-logo";

/**
 * Sticky header with the mobile menu, and three things that only make sense
 * while the page is being read.
 *
 * 1. **It condenses.** On desktop it drops from 112px to 88px, with the logo
 *    scaling proportionally. Mobile keeps a stable 96px header for its menu.
 * 2. **It says where you are.** The link for the section currently in view turns
 *    the accent colour and grows an underline. A page with no marker reads as
 *    an endless scroll; this is the cheapest cure.
 * 3. **It says how much is left.** Two pixels of gold across the top.
 *
 * All three are computed in one `requestAnimationFrame` callback on a passive
 * scroll listener. Separate listeners per feature would each run a layout read
 * on every scroll event; one rAF that reads once and writes three times does not.
 *
 * `a client component only for the open/close state` is no longer the whole
 * story: the scroll work needs the browser, and it is all passive reads.
 */

/*
  The order of this list follows the page, not the reference mock.

  The reference put "La firma" before "Servicios"; this page shows the practice
  areas first, because a visitor arrives asking what the firm does, not who it
  is. A menu whose order disagrees with the scroll is not a small thing once the
  active-section marker exists: the highlight would walk the menu backwards.
*/
const LINKS = [
  { href: "#inicio", label: "Inicio" },
  { href: "#servicios", label: "Servicios" },
  { href: "#firma", label: "La firma" },
  { href: "#equipo", label: "Equipo" },
  { href: "#actualidad", label: "Actualidad" },
  { href: "#contacto", label: "Contacto" },
];

/** As published by the firm on wabogados.co. */
const FOOTER_CONTACT = {
  address: "Cra. 9 # 16-20, oficina 206, edificio Berna, Bogotá D.C.",
  phone: "+57 312 469 9617",
  phoneHref: "+573124699617",
  schedule: "Lunes a viernes, 8:00 a. m. a 7:00 p. m.",
};

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

export function SiteHeader({ homePage = true }: { homePage?: boolean }) {
  const [open, setOpen] = useState(false);
  const [condensed, setCondensed] = useState(false);
  const [active, setActive] = useState<string>(homePage ? "#inicio" : "#servicios");
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia(REDUCED_MOTION).matches;

    function read() {
      frame.current = null;
      const scrollTop = window.scrollY;
      const limit = document.documentElement.scrollHeight - window.innerHeight;

      setCondensed(scrollTop > 120);

      const progressBar = document.querySelector<HTMLElement>(".site-progress");
      if (progressBar) {
        const ratio = limit > 0 ? Math.min(1, Math.max(0, scrollTop / limit)) : 0;
        progressBar.style.setProperty("--site-progress", ratio.toFixed(4));
      }

      /*
        Which section owns the reading position. Measured rather than observed:
        an IntersectionObserver fires when a section's edge crosses a threshold,
        but what the reader wants to know is "what am I in the middle of", and
        the line 120px below the top of the window answers that directly.
      */
      let current = homePage ? "#inicio" : "#servicios";
      for (const link of homePage ? LINKS : []) {
        const section = document.querySelector(link.href);
        if (!section) continue;
        const top = section.getBoundingClientRect().top;
        if (top <= 140) current = link.href;
      }
      // At the very bottom the last section may never reach the line.
      if (homePage && limit > 0 && scrollTop >= limit - 4) current = LINKS[LINKS.length - 1].href;
      setActive(current);
    }

    function schedule() {
      if (frame.current !== null) return;
      frame.current = window.requestAnimationFrame(read);
    }

    read();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });

    if (reduced) {
      // The bar still tells the truth; it simply does not animate.
      const bar = document.querySelector<HTMLElement>(".site-progress");
      if (bar) bar.style.transition = "none";
    }

    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
    };
  }, [homePage]);

  /*
    The scrim is a **sibling** of the header, not a child, and that is not a
    detail.

    `.site-header` carries `backdrop-filter`, and an element with a filter or
    backdrop-filter becomes the containing block for its `position: fixed`
    descendants. Nested inside it, the scrim's `inset: 0` resolves against the
    91px-tall header instead of the viewport: the scrim covered only the header
    band, sat behind it at z-index 39, and tapping the page did nothing at all.
    Outside the header it covers what it is supposed to cover.
  */
  return (
    <>
      <header className="site-header" data-condensed={condensed}>
        <div className="site-progress" aria-hidden="true" />
        <div className="wrap site-nav">
          <Link href={homePage ? "#inicio" : "/"} className="site-brand" aria-label="WABOGADOS, inicio">
            <BrandLogo priority imageClassName="site-logo" />
          </Link>

          <button
            type="button"
            className="site-menu-toggle"
            aria-label={open ? "Cerrar menú" : "Abrir menú"}
            aria-expanded={open}
            aria-controls="site-navigation"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "×" : "☰"}
          </button>

          <nav
            id="site-navigation"
            className="site-nav-links"
            data-open={open}
            aria-label="Principal"
          >
            {LINKS.map((link) => (
              <a
                key={link.href}
                href={homePage ? link.href : `/${link.href}`}
                data-active={active === link.href}
                aria-current={active === link.href ? "true" : undefined}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </a>
            ))}

            {/*
              The reference HTML opened a mock-up dialog here. This links to the
              real thing: the login the platform actually has. A public site that
              fakes the door to its own product is a worse first impression than
              one that opens it.
            */}
            <Link href="/login" className="site-btn" onClick={() => setOpen(false)}>
              Portal privado <span aria-hidden="true">↗</span>
            </Link>
          </nav>
        </div>
      </header>

      {/*
        Dimming the page says "you are in the menu", and the full-bleed target
        gives the usual way out — tap anywhere that is not a link. Without it the
        hero's own buttons appear directly under the panel and the page behind
        stays fully active, which reads as a broken dropdown.

        A `<button>` so it is reachable and announced as a control, with
        `aria-hidden` because it carries no information: the button that opened
        the menu already reports `aria-expanded`, and a second control doing the
        same job would be announced twice.
      */}
      <button
        type="button"
        className="site-menu-scrim"
        data-open={open}
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => setOpen(false)}
      />
    </>
  );
}

export function SiteFooter({ homePage = true }: { homePage?: boolean }) {
  return (
    <footer className="site-band">
      <div className="wrap">
        <DrawRule />
        <div className="flex flex-col items-start gap-8 py-12 lg:flex-row lg:items-center lg:justify-between">
          <Link href={homePage ? "#inicio" : "/"} className="site-brand site-brand--footer" aria-label="WABOGADOS, inicio">
            <BrandLogo size="footer" imageClassName="site-logo" />
          </Link>

          <address className="text-xs not-italic leading-relaxed text-ivory/60">
            <span className="block">{FOOTER_CONTACT.address}</span>
            <a
              className="mt-1 block transition-colors hover:text-gold"
              href={`tel:${FOOTER_CONTACT.phoneHref}`}
            >
              {FOOTER_CONTACT.phone}
            </a>
            <span className="mt-1 block">{FOOTER_CONTACT.schedule}</span>
          </address>

          <div className="flex flex-col items-start gap-4 lg:items-end">
            <small className="text-xs text-ivory/55">
              © 2026 WABOGADOS · Propuesta de diseño
            </small>
            <p className="max-w-[46ch] text-xs leading-relaxed text-ivory/70">
              Estadísticas agregadas sin cookies: no guardamos IP ni datos del
              formulario en los contadores. Respetamos Do Not Track y Global Privacy Control.
            </p>
            <div className="flex flex-wrap gap-6 text-xs">
              <a href={homePage ? "#contacto" : "/#contacto"} className="text-ivory/70 transition-colors hover:text-gold">
                Contacto <span aria-hidden="true">↗</span>
              </a>
              <Link
                href="/login"
                className="text-ivory/70 transition-colors hover:text-gold"
              >
                Portal privado
              </Link>
              <Link
                href="/estado"
                className="text-ivory/70 transition-colors hover:text-gold"
              >
                Estado del sistema
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
