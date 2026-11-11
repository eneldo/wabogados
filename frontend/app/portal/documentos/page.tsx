import Link from "next/link";
import { redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import { Card, Chip, EmptyState, RuleNote, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { documentStatusLabel, documentStatusTone, documentTypeLabel, formatDate } from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { DashboardDocument } from "@/lib/types";

/**
 * Everything the firm has published to this client.
 *
 * The dashboard endpoint already restricts documents to the caller's own cases
 * and to published/visible material according to backend rules. Publication does
 * not automatically grant file download (ADR-025); this view makes that policy
 * explicit instead of implying access.
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
  const titles = new Map((value?.cases ?? []).map((item) => [item.id, item.title]));
  const canDownload = profile.permissions.includes("documents:download");

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
      <SectionHeading
        eyebrow="A su disposición"
        title="Documentos publicados"
        action={
          <span className="text-xs text-ink-muted">
            {documents.length} {documents.length === 1 ? "documento" : "documentos"}
          </span>
        }
      />

      <Card className="mt-6 p-5">
        <p className="text-sm leading-6 text-ink-soft">
          Esta sección muestra documentos que el despacho ha publicado para consulta en sus expedientes.
          La publicación permite conocer el documento; <span className="font-medium text-ink">no implica automáticamente autorización de descarga</span> del archivo original.
        </p>
        <ul className="mt-4 space-y-1.5 text-xs text-ink-muted">
          <li>• Estado: indica la situación administrativa del documento.</li>
          <li>• Tipo y fecha: ayudan a identificar versión/contexto.</li>
          <li>• Expediente: puede abrir el caso para ver actividad, audiencias y plazos relacionados.</li>
          {canDownload ? (
            <li>• Su cuenta tiene permiso de descarga; si necesita el archivo, solicítelo al despacho indicando el documento y expediente.</li>
          ) : (
            <li>• Si necesita una copia o descarga, solicítela al despacho indicando el documento y expediente.</li>
          )}
        </ul>
      </Card>

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
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="tnum label-rule">{numbers.get(caseId) ?? "Expediente"}</p>
                  {titles.get(caseId) ? (
                    <p className="mt-1 text-sm text-ink-muted">{titles.get(caseId)}</p>
                  ) : null}
                </div>
                <Link
                  href={`/portal/casos/${caseId}`}
                  className="text-xs text-forest underline-offset-4 hover:underline"
                >
                  Ver expediente
                </Link>
              </div>
              <Card className="mt-3 overflow-hidden">
                <ul className="divide-y divide-rule">
                  {list.map((document) => (
                    <li key={document.id} className="px-5 py-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-ink">{document.title}</p>
                          <p className="mt-1 text-xs text-ink-muted">
                            {documentTypeLabel(document.document_type)} · {formatDate(document.created_at)}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Chip tone={documentStatusTone(document.status)} dot>
                            {documentStatusLabel(document.status)}
                          </Chip>
                          <Chip tone="neutral" dot>
                            {canDownload ? "Acceso controlado" : "Consulta"}
                          </Chip>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
        </div>
      )}

      <RuleNote>
        Los originales de los documentos los conserva el despacho. Esta vista informa qué material ha sido publicado; cualquier copia o descarga debe gestionarse con autorización y trazabilidad.
      </RuleNote>
    </Masthead>
  );
}
