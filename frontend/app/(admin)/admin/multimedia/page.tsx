import Link from "next/link";
import { redirect } from "next/navigation";

import {
  DeactivateMediaButton,
  ReactivateMediaButton,
  UploadMediaButton,
} from "@/components/admin/multimedia/media-actions";
import { EditMediaButton, MediaForm } from "@/components/admin/multimedia/media-form";
import { MediaDetail } from "@/components/admin/multimedia/media-detail";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader, Pager } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  formatBytes,
  formatDate,
  mediaConfidentialityLabel,
  mediaConfidentialityTone,
  mediaKindLabel,
  mediaKindTone,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { MediaHistoryEntry, MediaRecord, PaginatedMedia } from "@/lib/types";

/**
 * Centro multimedia (MASTER_PROMPT V4): the firm's own material in one place.
 *
 * Two states a listing must be able to tell apart, because both are normal and
 * neither is an error: a resource **registered without a file** (a librarian
 * files the recording and it arrives later) and a resource whose file **was
 * deactivated** (it left the day-to-day view but kept its bytes and its history).
 * Collapsing them would make the screen lie about what the firm actually holds.
 *
 * This is an internal library. Nothing here is published to the portal and the
 * client role holds no permission on it, so the only gate is `media:read`.
 */

const PAGE_SIZE = 24;

export default async function MultimediaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const { profile } = session;
  const can = (permission: string) => profile.permissions.includes(permission);

  if (!can("media:read")) {
    return (
      <div>
        <PageHeader
          eyebrow="Biblioteca"
          title="Centro multimedia"
          description="Su perfil no tiene el permiso para consultar la biblioteca."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso a esta sección"
            hint="La biblioteca es material interno de la firma; consulte con un administrador si necesita verla."
          />
        </div>
      </div>
    );
  }

  const params = await searchParams;
  const search = first(params.q);
  const kind = first(params.tipo);
  const confidentiality = first(params.confidencialidad);
  const status = first(params.estado);
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);
  const includeInactive = first(params.inactivos) === "1";
  const open = first(params.recurso);

  const { value, failed } = await load<PaginatedMedia>("/api/v1/media", {
    skip,
    limit: PAGE_SIZE,
    search,
    kind,
    confidentiality,
    status,
    include_inactive: includeInactive || undefined,
  });

  const items = value?.items ?? [];
  const total = value?.total ?? 0;

  // Cases are authorised by scope, not by `cases:read`, which does not exist: the
  // API accepts `cases:read_all`, `cases:read_assigned` and `cases:read_published`.
  // Gating on a name the catalogue does not have leaves the select empty for
  // everyone, which looks like "there are no cases" rather than "the check is wrong".
  const canReadCases = ["cases:read_all", "cases:read_assigned", "cases:read_published"].some(
    (permission) => can(permission),
  );

  const { value: cases } = canReadCases
    ? await load<{ items: { id: string; case_number: string; title: string }[] }>(
        "/api/v1/cases",
        { skip: 0, limit: 200 },
      )
    : { value: null };
  const caseOptions = cases?.items ?? [];

  // The drawer is a URL, not component state, so a resource can be linked to.
  const { value: detail } = open
    ? await load<MediaRecord>(`/api/v1/media/${open}`)
    : { value: null };
  const { value: history } =
    open && detail && can("media:read")
      ? await load<MediaHistoryEntry[]>(`/api/v1/media/${open}/history`, { limit: 40 })
      : { value: null };

  const hrefFor = (next: {
    q?: string;
    tipo?: string;
    confidencialidad?: string;
    estado?: string;
    inactivos?: string;
    recurso?: string;
    skip?: number;
  }) => {
    const query = new URLSearchParams();
    // An empty value is the same as no value: the filter bar submits "" for
    // "Todos" on every select, and writing `?tipo=` would make a link to this
    // screen look filtered when it is not.
    const put = (key: string, value: string | number | undefined) => {
      if (value === undefined || value === "") return;
      query.set(key, String(value));
    };

    put("q", next.q ?? search);
    put("tipo", next.tipo ?? kind);
    put("confidencialidad", next.confidencialidad ?? confidentiality);
    put("estado", next.estado ?? status);
    put("inactivos", next.inactivos ?? (includeInactive ? "1" : ""));
    put("recurso", next.recurso ?? open);
    put("skip", next.skip);

    return query.size > 0 ? `/admin/multimedia?${query.toString()}` : "/admin/multimedia";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Biblioteca"
        title="Centro multimedia"
        description="Grabaciones, fotografías, audio y documentos de la firma, en un solo lugar. No es el archivo de evidencias: allí cada original es inmutable y tiene cadena de custodia, y aquí el material se puede corregir. Un recurso se puede registrar antes de que su archivo llegue."
        actions={<MediaForm canAct={can("media:create")} cases={caseOptions} />}
      />

      <FilterBar>
        <FilterField
          label="Buscar"
          name="q"
          defaultValue={search}
          placeholder="Título, descripción o etiqueta"
          className="min-w-[14rem] flex-1"
        />
        <SelectField
          id="filtro-tipo"
          label="Tipo"
          name="tipo"
          defaultValue={kind ?? ""}
          options={[
            ["", "Todos"],
            ["video", "Grabación"],
            ["image", "Fotografía"],
            ["audio", "Audio"],
            ["document", "Documento"],
          ]}
        />
        <SelectField
          id="filtro-confidencialidad"
          label="Confidencialidad"
          name="confidencialidad"
          defaultValue={confidentiality ?? ""}
          options={[
            ["", "Todas"],
            ["interno", "Interno"],
            ["restringido", "Restringido"],
            ["confidencial", "Confidencial"],
          ]}
        />
        <SelectField
          id="filtro-estado"
          label="Estado"
          name="estado"
          defaultValue={status ?? ""}
          options={[
            ["", "Todos"],
            ["activo", "Activo"],
            ["archivado", "Archivado"],
          ]}
        />
        <input type="hidden" name="inactivos" value={includeInactive ? "1" : ""} />
        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {search || kind || confidentiality || status || includeInactive ? (
          <Link
            href="/admin/multimedia"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar la biblioteca. Una lista vacía y una lista que no se
          pudo leer no son lo mismo, y esta pantalla no las confunde.
        </p>
      ) : null}

      <div className="mt-6">
        {items.length === 0 ? (
          <EmptyState
            title={
              search || kind || confidentiality || status || includeInactive
                ? "Ningún recurso coincide"
                : "La biblioteca está vacía"
            }
            hint={
              search || kind || confidentiality || status || includeInactive
                ? "Pruebe con otro texto o quite los filtros."
                : "Es lo normal en una instalación recién estrenada. Registre el primer recurso con «Nuevo recurso»; el archivo puede cargarse después."
            }
          />
        ) : (
          <>
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="ledger min-w-[58rem]">
                  <caption className="sr-only">
                    Biblioteca multimedia, {total} recursos en total
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className="label-rule">
                        Recurso
                      </th>
                      <th scope="col" className="label-rule">
                        Tipo
                      </th>
                      <th scope="col" className="label-rule">
                        Confidencialidad
                      </th>
                      <th scope="col" className="label-rule">
                        Tamaño
                      </th>
                      <th scope="col" className="label-rule">
                        Expediente
                      </th>
                      <th scope="col" className="label-rule text-right">
                        Acciones
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <MediaRow
                        key={item.id}
                        item={item}
                        canAct={can("media:update")}
                        canUpload={can("media:upload")}
                        canDeactivate={can("media:delete")}
                        caseOptions={caseOptions}
                        href={hrefFor({ recurso: item.id })}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Pager
              total={total}
              skip={skip}
              limit={PAGE_SIZE}
              pageHref={(next) => hrefFor({ skip: next })}
            />
          </>
        )}

        <RuleNote>
          Nada se borra en esta biblioteca: un recurso se desactiva, y conserva su
          archivo y su historial para poder volver a activarlo. Y no es el archivo de
          evidencias —allí el original es inmutable y tiene cadena de custodia—: lo
          que pertenece a un expediente se registra como evidencia, y lo que se
          archiva aquí es material de trabajo.
        </RuleNote>
      </div>

      {detail ? (
        <MediaDetail
          item={detail}
          history={history ?? []}
          canDownload={can("media:download")}
          closeHref={hrefFor({ recurso: "", skip: 0 })}
        />
      ) : null}
    </div>
  );
}

function MediaRow({
  item,
  canAct,
  canUpload,
  canDeactivate,
  caseOptions,
  href,
}: {
  item: MediaRecord;
  canAct: boolean;
  canUpload: boolean;
  canDeactivate: boolean;
  caseOptions: { id: string; case_number: string; title: string }[];
  href: string;
}) {
  const accent = !item.is_active
    ? "closed"
    : item.confidentiality === "confidencial"
      ? "urgent"
      : "live";

  return (
    <tr data-accent={accent} className="row-enter">
      <th scope="row" className="py-4 pr-4 font-normal">
        <Link
          href={href}
          className="row-title block break-words hover:text-wax hover:underline"
        >
          {item.title}
        </Link>
        <span className="mt-1 block max-w-[24rem] text-xs text-ink-muted">
          {item.has_file ? (
            <>
              {item.original_filename ?? "archivo"} ·{" "}
              <span className="text-ink-faint">{formatBytes(item.size_bytes ?? 0)}</span>
            </>
          ) : (
            <span className="text-brass">Registrado, sin archivo</span>
          )}
        </span>
        {item.tags ? (
          <span className="mt-1 block max-w-[24rem] text-xs text-ink-faint">
            {item.tags}
          </span>
        ) : null}
        {item.is_active ? null : (
          <span className="mt-1 block text-xs text-ink-faint">
            Desactivado el {formatDate(item.deleted_at)}
          </span>
        )}
      </th>
      <td className="py-4 pr-4 align-top">
        <Chip tone={mediaKindTone(item.kind)}>{mediaKindLabel(item.kind)}</Chip>
      </td>
      <td className="py-4 pr-4 align-top">
        <Chip tone={mediaConfidentialityTone(item.confidentiality)}>
          {mediaConfidentialityLabel(item.confidentiality)}
        </Chip>
      </td>
      <td className="row-meta py-4 pr-4 align-top">
        {item.has_file ? formatBytes(item.size_bytes ?? 0) : "—"}
      </td>
      <td className="row-meta py-4 pr-4 align-top">
        {item.case_number ?? <span className="text-ink-faint">Sin expediente</span>}
      </td>
      <td className="py-4 align-top">
        <div className="flex flex-wrap justify-end gap-1">
          <UploadMediaButton item={item} canAct={canUpload} />
          <EditMediaButton item={item} canAct={canAct} cases={caseOptions} />
          {canDeactivate ? (
            item.is_active ? (
              <DeactivateMediaButton item={item} />
            ) : (
              <ReactivateMediaButton item={item} />
            )
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function SelectField({
  id,
  label,
  name,
  defaultValue,
  options,
}: {
  id: string;
  label: string;
  name: string;
  defaultValue: string;
  options: [string, string][];
}) {
  return (
    <div>
      <label htmlFor={id} className="label-rule block">
        {label}
      </label>
      <select
        id={id}
        name={name}
        defaultValue={defaultValue}
        className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
      >
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Load a resource for a signed-in caller.
 *
 * Redirects only when the session is genuinely gone; any other failure returns
 * null with `failed`, because an empty list and a failed request must not look
 * alike.
 */
async function load<T>(
  path: string,
  query: Record<string, string | number | boolean | undefined> = {},
): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path, { query }), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}
