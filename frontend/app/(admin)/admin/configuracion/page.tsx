import Link from "next/link";
import { redirect } from "next/navigation";

import { DeleteSettingButton } from "@/components/admin/configuracion/setting-actions";
import { EditSettingButton, SettingForm } from "@/components/admin/configuracion/setting-form";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  formatDateTime,
  humanise,
  settingValueLabel,
  settingValueType,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { SettingRecord } from "@/lib/types";

/**
 * Configuración: the values the system reads while it runs.
 *
 * `system_settings` is not a list of preferences. It is the small set of values
 * that a deployment needs to change without being reinstalled — a retention
 * window, a default timezone, a limit — and the screen is built around that
 * difference: there is no search over a hundred rows, because there are never a
 * hundred rows, and every one of them changes how the product behaves rather than
 * how it looks.
 *
 * **It is also the only place in the administration with a delete button**, and
 * the copy says why instead of hiding it: everywhere else a row is a legal record
 * and is deactivated or archived, while a setting holds nothing of the sort and
 * the backend already keeps its previous value in `change_logs`.
 */

const PAGE = "/admin/configuracion";

export default async function SettingsPage({
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
  const canWrite = profile.permissions.includes("settings:write");

  if (!profile.permissions.includes("settings:read")) {
    return (
      <div>
        <PageHeader
          eyebrow="Ajustes del sistema"
          title="Configuración"
          description="Su perfil no tiene el permiso para leer los ajustes del sistema."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso a esta sección"
            hint="Consulte con un administrador si necesita leer o modificar los ajustes del sistema."
          />
        </div>
      </div>
    );
  }

  const params = await searchParams;
  const search = first(params.q);
  const category = first(params.categoria);

  const { value, failed } = await load<SettingRecord[]>("/api/v1/admin/settings", {
    category: category || undefined,
  });

  const all = value ?? [];
  // The API filters by category but not by text, so the search runs here. It is
  // a handful of rows; sending it to the API would be a page of parameters for
  // nothing. The category is part of the searched text because it is on screen
  // as the heading of each block: someone who reads «Retencion» and types it
  // expects the block, not an empty page.
  const needle = search?.toLowerCase() ?? "";
  const settings = needle
    ? all.filter((setting) =>
        [
          setting.key,
          setting.category,
          setting.description ?? "",
          setting.raw_value,
        ]
          .join(" ")
          .toLowerCase()
          .includes(needle),
      )
    : all;

  const categories = [...new Set(all.map((setting) => setting.category))].sort();
  const groups = groupBy(settings, (setting) => setting.category);

  const hrefFor = (next: { q?: string; categoria?: string } = {}) => {
    const query = new URLSearchParams();
    if (next.q) query.set("q", next.q);
    if (next.categoria) query.set("categoria", next.categoria);
    return query.size > 0 ? `${PAGE}?${query.toString()}` : PAGE;
  };

  return (
    <div>
      <PageHeader
        eyebrow="Ajustes del sistema"
        title="Configuración"
        description="Los valores que el sistema lee mientras funciona, sin reinstalarlo. Un ajuste no es un expediente: no guarda datos del estudio, y por eso es el único sitio de la administración donde una fila se puede eliminar en lugar de desactivarse."
        actions={<SettingForm canAct={canWrite} />}
      />

      {/*
        No filter strip over nothing. A search box and a "Filtrar" button above an
        empty table is noise that implies there is something to narrow down, and
        the empty state below already says what to do instead.
      */}
      {all.length > 0 ? (
        <FilterBar>
          <FilterField
            label="Buscar"
            name="q"
            defaultValue={search}
            placeholder="Clave, categoría, descripción o valor"
            className="min-w-[14rem] flex-1"
          />
          {categories.length > 1 ? (
            <div>
              <label htmlFor="filtro-categoria" className="label-rule block">
                Categoría
              </label>
              <select
                id="filtro-categoria"
                name="categoria"
                defaultValue={category ?? ""}
                className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
              >
                <option value="">Todas</option>
                {categories.map((entry) => (
                  <option key={entry} value={entry}>
                    {humanise(entry)}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <Button type="submit" variant="secondary">
            Filtrar
          </Button>
          {search || category ? (
            <Link
              href={hrefFor()}
              className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
            >
              Limpiar
            </Link>
          ) : null}
        </FilterBar>
      ) : null}

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar los ajustes. Lo que se ve abajo puede estar
          incompleto, y una lista de ajustes a medias es peor que ninguna: cambia
          lo que el sistema cree que es verdad.
        </p>
      ) : null}

      <div className="mt-6 space-y-8">
        {all.length === 0 && !failed ? (
          <EmptyState
            title="Todavía no hay ningún ajuste"
            hint={
              canWrite
                ? "Es lo normal en una instalación recién estrenada: los ajustes se crean cuando hay algo que cambiar sin reinstalar. Use «Nuevo ajuste» para el primero."
                : "Es lo normal en una instalación recién estrenada: los ajustes se crean cuando hay algo que cambiar sin reinstalar."
            }
          />
        ) : settings.length === 0 ? (
          <EmptyState
            title="Ningún ajuste coincide"
            hint="Pruebe con otro texto o quite los filtros."
          />
        ) : (
          Object.entries(groups).map(([name, entries]) => (
            <section key={name}>
              <SectionHeading
                eyebrow="Categoría"
                title={humanise(name)}
                action={
                  <span className="text-sm text-ink-faint">
                    {entries.length} ajuste{entries.length === 1 ? "" : "s"}
                  </span>
                }
              />

              <Card className="mt-3 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="ledger min-w-[52rem]">
                    <caption className="sr-only">
                      Ajustes de la categoría {name}, {entries.length} en total
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col" className="label-rule">
                          Clave
                        </th>
                        <th scope="col" className="label-rule">
                          Valor
                        </th>
                        <th scope="col" className="label-rule">
                          Tipo
                        </th>
                        <th scope="col" className="label-rule">
                          Último cambio
                        </th>
                        <th scope="col" className="label-rule text-right">
                          Acciones
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((setting) => (
                        <SettingRow
                          key={setting.key}
                          setting={setting}
                          canWrite={canWrite}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>
          ))
        )}

        <RuleNote>
          Un ajuste se elimina de verdad, y es la única excepción de la
          administración: el resto de las filas son registros jurídicos que se
          desactivan o se archivan porque borrarlos rompe la cadena de custodia.
          Aquí el valor anterior queda anotado en el historial de cambios, y lo que
          no se puede guardar aquí es una contraseña ni un token: el backend
          rechaza esas claves y los secretos viven en el entorno.
        </RuleNote>
      </div>
    </div>
  );
}

function SettingRow({
  setting,
  canWrite,
}: {
  setting: SettingRecord;
  canWrite: boolean;
}) {
  return (
    <tr data-accent="live" className="row-enter">
      <th scope="row" className="py-4 pr-4 font-normal align-top">
        <span className="row-title break-all font-mono text-[0.8125rem]">{setting.key}</span>
        {setting.description ? (
          <span className="mt-1 block max-w-[26rem] text-xs text-ink-muted">
            {setting.description}
          </span>
        ) : (
          <span className="mt-1 block text-xs text-ink-faint">Sin descripción</span>
        )}
      </th>
      <td className="py-4 pr-4 align-top">
        <span className="block max-w-[22rem] break-words font-mono text-[0.8125rem] text-ink">
          {settingValueLabel(setting.value, setting.raw_value)}
        </span>
      </td>
      <td className="py-4 pr-4 align-top">
        <Chip tone="neutral">{settingValueType(setting.value)}</Chip>
      </td>
      <td className="row-meta py-4 pr-4 align-top">{formatDateTime(setting.updated_at)}</td>
      <td className="py-4 align-top">
        <div className="flex justify-end gap-1">
          <EditSettingButton setting={setting} canAct={canWrite} />
          <DeleteSettingButton setting={setting} />
        </div>
      </td>
    </tr>
  );
}

/**
 * Load the settings for a signed-in caller.
 *
 * Redirects only when the session is genuinely gone; any other failure returns
 * null with `failed`, because an empty list of settings and a failed request must
 * not look alike.
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

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  const groups: Record<string, T[]> = {};
  for (const item of items) {
    const group = key(item);
    (groups[group] ??= []).push(item);
  }
  return groups;
}
