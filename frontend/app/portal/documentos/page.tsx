import { redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import { Card, Chip, EmptyState, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { formatDate } from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { DashboardDocument } from "@/lib/types";

/**
 * Everything the firm has published to this client.
 *
 * The dashboard endpoint already restricts documents to the caller's own cases
 * and to `publicada` visibility, so this page is a view over that set rather
 * than a second query that might disagree with it.
 */
export default async function DocumentsPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} />;
  }
  const profile = session.profile;

  const { value, failed } = await loadForSession<{
    documents: DashboardDocument[];
    cases: Array<{ id: string; case_number: string; title: string }>;
  }>("/api/v1/dashboard", { query: { limit: 50 } });

  if (failed) return <ServiceUnavailable />;

  const documents = value?.documents ?? [];
  const numbers = new Map((value?.cases ?? []).map((item) => [item.id, item.case_number]));

  const grouped = documents.reduce<Map<string, DashboardDocument[]>>((accumulator, document) => {
    const key = document.case_id;
    const list = accumulator.get(key) ?? [];
    list.push(document);
    accumulator.set(key, list);
    return accumulator;
  }, new Map());

  return (
    <Masthead
      eyebrow="WABOGADOS"
      title="Portal del cliente"
      profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
      nav={[
        { href: "/portal", label: "Mi expediente" },
        { href: "/portal/mensajes", label: "Mensajes" },
        { href: "/portal/documentos", label: "Documentos", active: true },
      ]}
    >
      <SectionHeading eyebrow="A su disposición" title="Documentos publicados" />

      {documents.length === 0 ? (
        <div className="mt-7">
          <EmptyState
            title="Todavía no hay documentos"
            hint="Cuando el despacho publique un documento en alguno de sus expedientes aparecerá aquí."
          />
        </div>
      ) : (
        <div className="mt-7 space-y-9">
          {[...grouped.entries()].map(([caseId, list]) => (
            <section key={caseId}>
              <p className="tnum label-rule">
                {numbers.get(caseId) ?? "Expediente"}
              </p>
              <Card className="mt-3 overflow-hidden">
                <ul className="divide-y divide-rule">
                  {list.map((document) => (
                    <li
                      key={document.id}
                      className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 py-3.5"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{document.title}</p>
                        <p className="text-xs text-ink-muted">
                          {document.document_type} · {formatDate(document.created_at)}
                        </p>
                      </div>
                      <Chip tone="forest">Publicado</Chip>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
        </div>
      )}

      <p className="mt-10 text-xs leading-relaxed text-ink-faint">
        Los originales de los documentos los conserva el despacho. Esta vista
        muestra los documentos que ha puesto a su disposición.
      </p>
    </Masthead>
  );
}
