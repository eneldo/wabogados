import Link from "next/link";
import { redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import {
  Card,
  Chip,
  EmptyState,
  SectionHeading,
} from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { caseStatusTone, formatDate } from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { DashboardPayload } from "@/lib/types";

/**
 * The staff case list.
 *
 * The dashboard is capped at a handful of rows, so this is the way to reach the
 * rest of the book and, from there, the evidence manager of a case. It reads
 * the same scoped endpoint the panel does rather than building its own query:
 * one place decides what a lawyer may see.
 */
export default async function CasesPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return (
      <ServiceUnavailable message={session.message} backHref="/portal" />
    );
  }
  const profile = session.profile;

  const { value: dashboard } = await loadForSession<DashboardPayload>(
    "/api/v1/dashboard",
    { query: { limit: 50 } },
  );

  const cases = dashboard?.cases ?? [];

  return (
    <Masthead
      eyebrow="WABOGADOS"
      title="Expedientes"
      profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
      nav={[
        { href: "/portal", label: "Panel" },
        { href: "/expedientes", label: "Expedientes", active: true },
        { href: "/portal/mensajes", label: "Mensajes" },
      ]}
    >
      <SectionHeading eyebrow="Cartera" title="Mis expedientes" />

      {cases.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No tiene expedientes asignados"
            hint="Un expediente aparece aquí en cuanto se le asigne como responsable o colaborador."
          />
        </div>
      ) : (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2">
          {cases.map((item) => (
            <li key={item.id}>
              <Card className="flex h-full flex-col p-5 transition-all duration-200 hover:border-rule-strong hover:shadow-[0_8px_22px_-16px_rgba(25,27,24,0.5)]">
                <div className="flex items-start justify-between gap-3">
                  <p className="tnum text-xs text-ink-muted">{item.case_number}</p>
                  <Chip tone={caseStatusTone(item.status)}>{item.status}</Chip>
                </div>

                <h2 className="font-display mt-2 text-xl leading-snug">{item.title}</h2>
                <p className="mt-1 text-xs text-ink-muted">{item.client_name}</p>
                <p className="mt-3 text-xs text-ink-faint">
                  Abierto el {formatDate(item.opened_at)}
                </p>

                <div className="mt-5 flex flex-wrap gap-x-4 gap-y-2 border-t border-rule pt-4">
                  <Link
                    href={`/expedientes/${item.id}`}
                    className="text-xs font-semibold uppercase tracking-[0.1em] text-wax underline-offset-4 transition-colors hover:underline"
                  >
                    Ver expediente →
                  </Link>
                  <Link
                    href={`/expedientes/${item.id}/evidencias`}
                    className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted underline-offset-4 transition-colors hover:text-ink hover:underline"
                  >
                    Evidencias →
                  </Link>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-10 text-xs text-ink-faint">
        El gestor de evidencias existe dentro de cada expediente: una evidencia
        pertenece siempre a un archivo, nunca flota por separado.
      </p>
    </Masthead>
  );
}
