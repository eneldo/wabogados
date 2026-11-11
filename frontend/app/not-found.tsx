import Link from "next/link";

import { Card, Label } from "@/components/primitives";
import { BrandLogo } from "@/components/brand-logo";

/**
 * Spanish 404.
 *
 * The wording is deliberate. This page is also what a client sees when they type
 * the address of somebody else's case, because the backend answers 404 rather
 * than 403 on purpose: confirming the file exists would leak the fact that it
 * exists. So the page must not say "you do not have access" — that would give
 * the game away. It says the page is not here, which is true either way.
 */
export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center px-6 py-20">
      <Card className="w-full max-w-lg p-8 text-center">
        <div className="flex justify-center">
          <BrandLogo size="sidebar" />
        </div>
        <Label className="mt-6">Error 404</Label>
        <h1 className="font-display mt-2 text-3xl leading-tight">
          Esta página no existe
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-ink-soft">
          La dirección no corresponde a ningún contenido del portal. Puede que
          el enlace haya cambiado o que contenga un error al escribirla.
        </p>
        <div className="mt-7 flex justify-center gap-3">
          <Link
            href="/portal"
            className="rounded-card bg-action px-4 py-2.5 text-sm font-semibold text-on-action transition-colors hover:bg-action-hover"
          >
            Ir a mi expediente
          </Link>
          <Link
            href="/"
            className="rounded-card border border-rule-strong px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-wax hover:text-wax"
          >
            Estado del sistema
          </Link>
        </div>
      </Card>
    </main>
  );
}
