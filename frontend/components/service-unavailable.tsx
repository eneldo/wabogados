import Link from "next/link";

import { Card, Label, Seal } from "@/components/primitives";
/**
 * Shown when the API is reachable but the call failed.
 *
 * This exists so a backend problem reads as a backend problem. Redirecting to
 * the login form would tell the user their session expired, which is a
 * different and false story, and would loop if the cookie is still valid.
 */
export function ServiceUnavailable({
  message,
  backHref = "/portal",
  backLabel = "Volver al panel",
}: {
  message?: string;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <main className="grid min-h-screen place-items-center px-6 py-20">
      <Card className="w-full max-w-lg p-8 text-center">
        <div className="flex justify-center">
          <Seal className="size-11" />
        </div>
        <Label className="mt-6">Servicio no disponible</Label>
        <h1 className="font-display mt-2 text-3xl leading-tight">
          No pudimos cargar su información
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-ink-soft">
          {message ??
            "El servicio no responde en este momento. Sus datos no se han perdido: vuelva a intentarlo en unos segundos."}
        </p>
        <div className="mt-7 flex justify-center gap-3">
          <Link
            href={backHref}
            className="rounded-card bg-ink px-4 py-2.5 text-sm font-semibold text-paper transition-colors hover:bg-ink-soft"
          >
            {backLabel}
          </Link>
        </div>
      </Card>
    </main>
  );
}
