import { notFound } from "next/navigation";

import { PageHeader } from "@/components/admin/page-furniture";
import { Card, Label } from "@/components/primitives";
import { findModule } from "@/lib/admin-nav";

/**
 * The honest page for a module whose API is ready and whose screens are not.
 *
 * A menu item that leads to a 404 is a broken menu. A menu item that leads here
 * says, in the firm's own terms, that the module exists, that the service behind
 * it is finished, and exactly what is missing.
 *
 * The reason is not decoration. This project has been bitten by three of these
 * already: an endpoint that existed and was never surfaced, a form that claimed to
 * send and did not, and a statistics block full of zeroes. A screen that admits
 * what it is not yet is the cheapest of the three to build.
 */

export default async function PendingModulePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const entry = findModule(slug);

  if (!entry || entry.state === "ready") notFound();

  return (
    <div>
      <PageHeader
        eyebrow={entry.state === "planned" ? "Fase futura" : "En construcción"}
        title={entry.label}
        description={entry.note}
      />

      <div className="mt-8 max-w-2xl">
        <Card className="p-6">
          {entry.state === "planned" ? (
            <>
              <p className="text-sm leading-relaxed text-ink-soft">
                Este módulo está en la hoja de ruta y <strong>fuera</strong> del
                alcance actual. Aparece aquí para que la dirección vea la
                secuencia del proyecto, y está inactivo a propósito: no hay nada
                detrás de este enlace.
              </p>
              <p className="mt-4 text-sm leading-relaxed text-ink-muted">
                El <code className="tnum text-xs">MASTER_PROMPT.md</code> del
                proyecto lo enumera bajo «Fases futuras, NO implementar aún». La
                arquitectura queda preparada para integrarlo: los permisos, el
                almacenamiento y la auditoría ya son comunes a todos los módulos.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm leading-relaxed text-ink-soft">
                El servicio de este módulo <strong>ya está construido</strong>:
                sus endpoints, sus permisos y su auditoría existen y funcionan.
                Lo que falta es la pantalla.
              </p>
              <p className="mt-4 text-sm leading-relaxed text-ink-muted">
                No se muestra una tabla vacía ni un botón inactivo como si el
                módulo no existiera. Se dice lo que hay y lo que no.
              </p>
            </>
          )}
        </Card>

        <div className="mt-6 space-y-5">
          <div>
            <Label>Estado</Label>
            <p className="mt-1.5 text-sm text-ink-muted">
              {entry.state === "planned"
                ? "Planificado, no implementado."
                : "API lista, interfaz pendiente."}
            </p>
          </div>

          {/*
            The scope, when the roadmap has one. Without it this page says only
            that the module is absent, which is true and useless to the person
            deciding what comes next: they cannot tell an idea from a decision.
          */}
          {entry.future ? (
            <div>
              <Label>Fase {entry.future.phase}</Label>
              <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-muted">
                {entry.future.scope}
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}