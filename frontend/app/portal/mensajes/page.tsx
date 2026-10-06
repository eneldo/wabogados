import { redirect } from "next/navigation";

import { ConversationList } from "@/components/mensajes/conversation-list";
import { Masthead } from "@/components/masthead";
import { SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { ConversationSummary } from "@/lib/types";

/**
 * The client's conversations.
 *
 * The list arrives from `GET /api/v1/conversations`, which the backend already
 * restricts: a client receives their own threads and nothing else. An internal
 * conversation is not filtered here, because it is never sent.
 */
export default async function MessagesPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} />;
  }
  const profile = session.profile;

  const { value, failed } = await loadForSession<ConversationSummary[]>(
    "/api/v1/conversations",
  );
  if (failed) return <ServiceUnavailable />;

  return (
    <Masthead
      eyebrow="WABOGADOS"
      title="Portal del cliente"
      profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
      nav={[
        { href: "/portal", label: "Mi expediente" },
        { href: "/portal/mensajes", label: "Mensajes", active: true },
        { href: "/portal/documentos", label: "Documentos" },
      ]}
    >
      <SectionHeading eyebrow="Con el despacho" title="Mensajes" />
      <div className="mt-7">
        <ConversationList
          initial={value ?? []}
          profileId={profile.id}
          canAttach={profile.permissions.includes("messages:attach")}
        />
      </div>
    </Masthead>
  );
}
