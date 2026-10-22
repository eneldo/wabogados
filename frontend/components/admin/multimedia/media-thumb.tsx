"use client";

import { useState } from "react";

/**
 * The poster of a media asset, with a two-step fallback.
 *
 * First choice is the derived JPEG the server generates on upload for images.
 * When it does not exist — assets uploaded before the generator behind them, a
 * kind that has no poster until `ffmpeg` arrives, a fetch that failed — the
 * component steps down instead of showing a broken image:
 *
 * - with `fallbackSrc`, it serves that address (the ficha hands the streaming
 *   route of the original, so an old image keeps having a preview);
 * - without it, it disappears (the listing cell simply has no poster, which is
 *   the honest current state of the resource and neither an error nor a spinner
 *   that will never resolve).
 *
 * Like everything else in this module, the tag is a plain `<img>` despite the
 * lint rule: the image lives behind an authenticated route, so the Next.js
 * optimizer has no public URL to fetch and no width it could know in advance.
 */

export function MediaThumb({
  id,
  alt,
  fallbackSrc,
  className,
}: {
  id: string;
  alt: string;
  /** Second choice; typically the streaming route of the original itself. */
  fallbackSrc?: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const [exhausted, setExhausted] = useState(false);

  if (exhausted) return null;
  if (failed && !fallbackSrc) return null;

  const source = failed ? fallbackSrc : `/api/media/${id}/thumbnail`;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={source}
      alt={alt}
      loading="lazy"
      className={className}
      onError={() => {
        if (failed && fallbackSrc) setExhausted(true);
        else setFailed(true);
      }}
    />
  );
}
