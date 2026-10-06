import { notFound, redirect } from "next/navigation";

import { EvidenceManager } from "@/components/evidencias/manager";
import { Masthead } from "@/components/masthead";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { requireSession, loadForSession } from "@/lib/session-guard";
import type { Evidence } from "@/lib/types";

/**
 * The evidence manager, inside its case.
 *
 * Evidence is not a free-floating document: it belongs to a file, and the
 * backend only exposes it through a case. That is why there is no global
 * evidence list, and why this page takes a case identifier.
 *
 * The list is fetched here, on the server, already scoped. The client component
 * below only handles the view switch, the filter and the drawer.
 */
export default async function EvidenceManagerPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;

  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} />;
  }
  const profile = session.profile;

  let evidence: Evidence[];
  try {
    evidence = await apiFetch<Evidence[]>(`/api/v1/cases/${caseId}/evidences`);
  } catch (error) {
    if (error instanceof ApiRequestError && (error.isNotFound || error.isForbidden)) {
      // The backend answers 404 rather than 403 for a case outside the caller's
      // scope, on purpose: confirming it exists would leak the fact. Forwarding
      // that as a 404 here keeps the same answer.
      notFound();
    }
    // Anything else is the service failing, not the case being absent. Saying
    // "not found" here would hide an outage behind a misleading empty page.
    return (
      <ServiceUnavailable
        message={
          error instanceof Error
            ? error.message
            : "No fue posible cargar las evidencias."
        }
      />
    );
  }

  const canUpload = profile.permissions.includes("evidences:upload");

  // The case number for the heading. Taken from the case itself rather than
  // from the first row, so the heading is correct when the list is empty — and
  // so no number is ever invented from a list that happens to be missing.
  const { value: caseSummary } = await loadForSession<{
    case_number: string;
    title: string;
  }>(`/api/v1/cases/${caseId}`);

  return (
    <Masthead
      eyebrow="WABOGADOS"
      title="Gestor de evidencias"
      profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
      nav={[
        { href: "/portal", label: "Panel" },
        { href: "/expedientes", label: "Expedientes" },
        {
          href: `/expedientes/${caseId}/evidencias`,
          label: "Evidencias",
          active: true,
        },
      ]}
    >
      <EvidenceManager
        caseId={caseId}
        caseNumber={caseSummary?.case_number}
        caseTitle={caseSummary?.title}
        initial={evidence}
        canUpload={canUpload}
      />
    </Masthead>
  );
}
