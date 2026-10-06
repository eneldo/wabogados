"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Parallax for the hero illustration.
 *
 * A `--site-parallax` custom property, set once per frame, consumed by CSS on
 * `.hero-art`. Deliberately *not* a `transform` written from React state: this
 * updates on every scroll frame, and a state update per frame would re-render the
 * hero's whole subtree sixty times a second to move one box fourteen pixels.
 * Writing a custom property touches one element's style and nothing else.
 *
 * The offset is a fraction of how far the element has travelled through the
 * viewport, clamped, so the illustration settles rather than sliding out of its
 * own frame at either end.
 *
 * Off entirely for reduced motion, and for coarse pointers: a touch device is
 * already moving the whole viewport under its finger, and a second layer moving
 * against it is noise.
 */

export function Parallax({
  children,
  className = "",
  strength = 26,
}: {
  children: ReactNode;
  className?: string;
  /** Maximum travel in pixels across the whole pass. */
  strength?: number;
}) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    if (reduced || coarse) return;

    let frame: number | null = null;

    function update() {
      frame = null;
      const box = element?.getBoundingClientRect();
      if (!box) return;
      const centre = box.top + box.height / 2 - window.innerHeight / 2;
      // -1 when the element is one full viewport above centre, +1 below.
      const offset = (centre / (window.innerHeight / 2)) * -strength;
      element?.style.setProperty(
        "--site-parallax",
        `${offset.toFixed(2)}px`,
      );
    }

    function schedule() {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(update);
    }

    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [strength]);

  return (
    <div ref={host} className={className}>
      {children}
    </div>
  );
}