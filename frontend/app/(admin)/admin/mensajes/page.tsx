import Link from "next/link";
import { redirect } from "next/navigation";

import { NewConversationDialog } from "@/components/admin/mensajes/new-conversation-dialog";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader } from "@/components/admin/page-furniture";
import { ConversationList } from "@/components/mensajes/conversation-list";
import { Card, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { closeConversation, createConversation } from "@/features/mensajes/actions";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import { requireSession } from "@/lib/session-guard";
import type {
  ConversationSummary,
  PaginatedCases,
  PaginatedClients,
  ParticipantOption,
} from "@/lib/types";

export default async function AdminMessagesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const permissions = session.profile.permissions;
  if (!permissions.includes("messages:read")) redirect("/admin");
  const params = await searchParams;
  const search = first(params.search)?.trim().toLocaleLowerCase("es") ?? "";
  const type = first(params.type);
  const status = first(params.status);
  const caseId = first(params.case_id);
  const onlyUnread = first(params.only_unread) === "1";
  const canCreate = permissions.includes("messages:create_conversation");

  const [conversationResult, casesResult, clientsResult, participantsResult] = await Promise.all([
    safely<ConversationSummary[]>("/api/v1/conversations", { limit: 200 }),
    canCreate
      ? safely<PaginatedCases>("/api/v1/cases", { skip: 0, limit: 200, open_only: true })
      : Promise.resolve({ value: null, failed: false }),
    canCreate && permissions.includes("clients:read")
      ? safely<PaginatedClients>("/api/v1/clients", { skip: 0, limit: 200 })
      : Promise.resolve({ value: null, failed: false }),
    canCreate
      ? safely<ParticipantOption[]>("/api/v1/conversations/participant-options", {
          conversation_type: "interna",
        })
      : Promise.resolve({ value: null, failed: false }),
  ]);

  if (conversationResult.failed) return <ServiceUnavailable backHref="/admin" />;
  const all = conversationResult.value ?? [];
  const filtered = all.filter((item) => {
    if (type && item.conversation_type !== type) return false;
    if (status && item.status !== status) return false;
    if (caseId && item.case_id !== caseId) return false;
    if (onlyUnread && item.unread === 0) return false;
    if (search && !`${item.subject} ${item.last_message_preview ?? ""}`.toLocaleLowerCase("es").includes(search)) return false;
    return true;
  });
  const cases = (casesResult.value?.items ?? []).map((record) => ({
    id: record.id,
    label: `${record.case_number} · ${record.title}`,
  }));
  const clients = (clientsResult.value?.items ?? [])
    .filter((record) => Boolean(record.user_id))
    .map((record) => ({ id: record.id, label: record.display_name }));
  const participants = (participantsResult.value ?? []).filter(
    (participant) => participant.account_type === "personal" && participant.id !== session.profile.id,
  );
  const optionsFailed = casesResult.failed || clientsResult.failed || participantsResult.failed;

  return (
    <div>
      <PageHeader
        eyebrow="Correspondencia"
        title="Mensajes"
        description="Su bandeja personal del despacho. Participar da acceso al contenido; administrar la plataforma no permite leer conversaciones ajenas."
        actions={canCreate ? (
          <NewConversationDialog
            action={createConversation}
            cases={cases}
            clients={clients}
            participants={participants}
          />
        ) : undefined}
      />

      {optionsFailed ? (
        <p className="mt-5 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          La bandeja está disponible, pero no se pudieron cargar todas las opciones para abrir un hilo nuevo.
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="Mis conversaciones" value={all.length} note="Solo hilos en los que participa" />
        <Metric label="Sin leer" value={all.filter((item) => item.unread > 0).length} note={`${all.reduce((sum, item) => sum + item.unread, 0)} mensajes pendientes`} urgent={all.some((item) => item.unread > 0)} />
        <Metric label="Canales de cliente" value={all.filter((item) => item.conversation_type === "cliente").length} note="Visibles en el portal" />
      </div>

      <FilterBar>
        <FilterField label="Buscar" name="search" defaultValue={first(params.search)} placeholder="Asunto o último mensaje" className="min-w-[14rem] flex-1" />
        <div>
          <label htmlFor="filtro-type" className="label-rule block">Canal</label>
          <select id="filtro-type" name="type" defaultValue={type ?? ""} className={SELECT}>
            <option value="">Todos</option>
            <option value="interna">Interna</option>
            <option value="cliente">Cliente</option>
          </select>
        </div>
        <div>
          <label htmlFor="filtro-status" className="label-rule block">Estado</label>
          <select id="filtro-status" name="status" defaultValue={status ?? ""} className={SELECT}>
            <option value="">Todos</option>
            <option value="abierto">Abiertos</option>
            <option value="cerrado">Cerrados</option>
          </select>
        </div>
        <div className="min-w-[12rem]">
          <label htmlFor="filtro-case_id" className="label-rule block">Expediente</label>
          <select id="filtro-case_id" name="case_id" defaultValue={caseId ?? ""} className={`${SELECT} max-w-[18rem]`}>
            <option value="">Todos</option>
            {cases.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
          <input type="checkbox" name="only_unread" value="1" defaultChecked={onlyUnread} className="size-4 accent-wax" />
          Solo sin leer
        </label>
        <Button type="submit" variant="secondary">Filtrar</Button>
        {search || type || status || caseId || onlyUnread ? (
          <Link href="/admin/mensajes" className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-wax">Limpiar</Link>
        ) : null}
      </FilterBar>

      <div className="mt-7">
        <ConversationList
          initial={filtered}
          profileId={session.profile.id}
          canAttach={permissions.includes("messages:attach")}
          canArchive={permissions.includes("messages:archive")}
          canClose={permissions.includes("messages:manage_participants")}
          closeAction={closeConversation}
          emptyMessage="No hay conversaciones que coincidan con estos filtros."
        />
      </div>

      <RuleNote>
        Cerrar conserva mensajes y adjuntos, pero impide nuevas respuestas. No existe borrado físico de correspondencia jurídica.
      </RuleNote>
    </div>
  );
}

function Metric({ label, value, note, urgent = false }: { label: string; value: number; note: string; urgent?: boolean }) {
  return (
    <Card className={`px-5 py-4 ${urgent ? "border-wax/35 bg-wax-tint" : ""}`}>
      <p className="label-rule">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-4">
        <p className={`font-display text-4xl ${urgent ? "text-wax-deep" : "text-ink"}`}>{value}</p>
        <p className="max-w-[11rem] text-right text-xs leading-relaxed text-ink-muted">{note}</p>
      </div>
    </Card>
  );
}

const SELECT = "mt-1.5 w-full rounded-card border border-rule-strong bg-surface-sunk px-3 py-2 text-sm text-ink outline-none focus:border-wax focus:bg-surface";

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

async function safely<T>(
  path: string,
  query: Record<string, string | number | boolean | undefined>,
): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path, { query }), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}
