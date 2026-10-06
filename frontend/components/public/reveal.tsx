"use client";

import { useEffect, useRef, type ElementType, type ReactNode } from "react";

/**
 * Reveal on scroll.
 *
 * The hidden state lives in CSS, keyed on `html.js`, and this component only
 * ever **adds** a class. That is deliberate, and it fixes two real traps:
 *
 * 1. **Hydration.** A `useState` initialiser that reads `IntersectionObserver`
 *    evaluates differently on the server and on the client, and React adopts
 *    the server's value on hydration. The effect then silently becomes a no-op
 *    and every element is visible from the first paint.
 * 2. **No JavaScript.** Starting from `opacity-0` in the markup would leave a
 *    page full of invisible content for anyone whose scripts are blocked, and
 *    for anyone whose observer never fires.
 *
 * So: the class name is constant across renders, `html.js` says "scripts are
 * available", and `is-in` says "this element has arrived". Without scripts the
 * `js` class is never added and the whole page is simply there.
 */
export function Reveal({
  children,
  as: Tag = "div",
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  as?: ElementType;
  /** Milliseconds. Use 60–90px between siblings. */
  delay?: number;
  className?: string;
}) {
  const host = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = host.current;
    if (!element || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        element.classList.add("is-in");
        // Once, then gone: a section that re-animates every time it is scrolled
        // back into makes the page feel unreliable rather than alive.
        observer.disconnect();
      },
      // A tenth of a viewport early, so the motion is finished by the time the
      // element is comfortably in view instead of starting late.
      { rootMargin: "0px 0px -10% 0px", threshold: 0.05 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <Tag
      ref={host}
      className={`site-reveal ${className}`}
      style={{ "--site-delay": `${delay}ms` } as React.CSSProperties}
    >
      {children}
    </Tag>
  );
}

/**
 * The hairline that opens a section. It is drawn once on first sighting, with
 * the same observer contract as `Reveal` and for the same reasons.
 */
export function DrawRule({ delay = 0, className = "" }: { delay?: number; className?: string }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = host.current;
    if (!element || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        element.classList.add("is-in");
        observer.disconnect();
      },
      { threshold: 0.1 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={host}
      className={`site-draw ${className}`}
      style={{ "--site-delay": `${delay}ms` } as React.CSSProperties}
    />
  );
}