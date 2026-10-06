import Link from "next/link";
import { redirect } from "next/navigation";

import {
  DeactivateUserButton,
  ReactivateUserButton,
  UserRolesButton,
} from "@/components/admin/seguridad/user-actions";
import { EditUserButton, UserForm } from "@/components/admin/seguridad/user-form";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader, Pager } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  auditActionParts,
  auditResultLabel,
  auditResultTone,
  formatDate,
  formatDateTime,
  humanise,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type {
  AuditLogRecord,
  PaginatedAuditLogs,
  PaginatedUsers,
  PermissionRecord,
  RoleRecord,
} from "@/lib/types";

/**
 * Seguridad: who can enter, what they may do once inside, and what the record
 * says they did.
 *
 * Three views in one URL, because they are three answers to one question and an
 * administrator moves between them while thinking. The selected view is `?vista`,
 * so a link to the audit trail filtered to one actor can be pasted into a
 * message like any other list.
 *
 * Each view is gated on its own permission rather than on one module-wide
 * string: a profile allowed to read the audit trail but not the user directory
 * still gets the first, and being refused the second should look like a missing
 * permission rather than a broken screen.
 */

const PAGE_SIZE = 25;

type ViewKey = "usuarios" | "roles" | "auditoria";

type HrefFor = (
  target: ViewKey,
  filters?: Record<string, string | undefined>,
  next?: Record<string, string | number>,
) => string;

const VIEWS: ReadonlyArray<{ key: ViewKey; label: string; permission: string }> = [
  { key: "usuarios", label: "Usuarios", permission: "users:read" },
  { key: "roles", label: "Roles y permisos", permission: "roles:read" },
  { key: "auditoria", label: "Auditoría", permission: "audit_logs:read" },
];

const VIEW_COPY: Record<ViewKey, { eyebrow: string; title: string; description: string }> = {
  usuarios: {
    eyebrow: "Control de acceso",
    title: "Usuarios",
    description:
      "Las cuentas que pueden entrar, los roles que les dan permisos y su estado. Una cuenta no se borra: se desactiva, porque la auditoría deja de ser legible en cuanto desaparece quien aparece en ella.",
  },
  roles: {
    eyebrow: "Control de acceso",
    title: "Roles y permisos",
    description:
      "Un permiso es la unidad: una acción concreta sobre un recurso concreto. Un rol es la manera de concederlos a grupo. Esta pantalla es de solo lectura: aquí se ve qué concede qué, no se reescribe.",
  },
  auditoria: {
    eyebrow: "Trazabilidad",
    title: "Auditoría",
    description:
      "Cada operación de escritura queda registrada con quién, cuándo, desde qué dirección y con qué resultado. Las lecturas no se registran: un listado de consultas no guarda nada que sirva y sí lo bastante como para no guardarlo.",
  },
};

export default async function SecurityPage({
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

  const params = await searchParams;
  const available = VIEWS.filter((entry) => can(entry.permission));
  const requested = first(params.vista);
  const view: ViewKey =
    requested && available.some((entry) => entry.key === requested)
      ? (requested as ViewKey)
      : (available[0]?.key ?? "usuarios");

  const hrefFor: HrefFor = (target, filters = {}, next = {}) => {
    const query = new URLSearchParams();
    query.set("vista", target);
    for (const [key, value] of Object.entries(filters)) {
      if (value) query.set(key, value);
    }
    for (const [key, value] of Object.entries(next)) query.set(key, String(value));
    return `/admin/seguridad?${query.toString()}`;
  };

  if (available.length === 0) {
    return (
      <div>
        <PageHeader
          eyebrow="Control de acceso"
          title="Seguridad"
          description="Su perfil no tiene ninguna de las permisiones que abren esta sección."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso a esta sección"
            hint="Consulte con un administrador si necesita leer usuarios, roles o la auditoría."
          />
        </div>
      </div>
    );
  }

  const copy = VIEW_COPY[view];
  const roles = can("roles:read")
    ? ((await load<RoleRecord[]>("/api/v1/admin/roles")).value ?? [])
    : [];

  const tabs = (
    <nav
      aria-label="Secciones de seguridad"
      className="mt-6 flex flex-wrap gap-1 border-b border-rule-strong"
    >
      {available.map((entry) => {
        const current = entry.key === view;
        return (
          <Link
            key={entry.key}
            href={hrefFor(entry.key)}
            aria-current={current ? "page" : undefined}
            className={`-mb-px border-b-2 px-3.5 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition-colors ${
              current ? "border-wax text-wax" : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {entry.label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div>
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        actions={
          view === "usuarios" ? <UserForm roles={roles} canAct={can("users:create")} /> : null
        }
      />

      {tabs}

      {view === "usuarios" ? (
        <UsersView
          params={params}
          hrefFor={hrefFor}
          roles={roles}
          meId={profile.id}
          can={can}
        />
      ) : null}
      {view === "roles" ? <RolesView roles={roles} can={can} /> : null}
      {view === "auditoria" ? (
        <AuditView params={params} hrefFor={hrefFor} usersAvailable={can("users:read")} />
      ) : null}
    </div>
  );
}

async function UsersView({
  params,
  hrefFor,
  roles,
  meId,
  can,
}: {
  params: Record<string, string | string[] | undefined>;
  hrefFor: HrefFor;
  roles: RoleRecord[];
  meId: string;
  can: (permission: string) => boolean;
}) {
  const search = first(params.search);
  const role = first(params.role);
  const estado = first(params.estado);
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);
  const filters = { search, role, estado };

  /*
    `failed` is kept apart from `value`: a directory that silently renders empty
    would tell the administrator the firm has no users at all.
  */
  const { value, failed } = await load<PaginatedUsers>("/api/v1/admin/users", {
    skip,
    limit: PAGE_SIZE,
    search,
    role,
    is_active: estado === "activo" ? true : estado === "inactivo" ? false : undefined,
  });

  const users = value?.items ?? [];
  const total = value?.total ?? 0;

  return (
    <div className="mt-6">
      <FilterBar>
        <input type="hidden" name="vista" value="usuarios" />
        <FilterField
          label="Buscar"
          name="search"
          defaultValue={search}
          placeholder="Correo o nombre"
          className="min-w-[14rem] flex-1"
        />
        {roles.length > 0 ? (
          <div>
            <label htmlFor="filtro-role" className="label-rule block">
              Rol
            </label>
            <select
              id="filtro-role"
              name="role"
              defaultValue={role ?? ""}
              className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
            >
              <option value="">Todos</option>
              {roles.map((entry) => (
                <option key={entry.id} value={entry.name}>
                  {humanise(entry.name)}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        <div>
          <label htmlFor="filtro-estado" className="label-rule block">
            Estado
          </label>
          <select
            id="filtro-estado"
            name="estado"
            defaultValue={estado ?? ""}
            className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
          >
            <option value="">Todos</option>
            <option value="activo">Activos</option>
            <option value="inactivo">Inactivos</option>
          </select>
        </div>
        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {search || role || estado ? (
          <Link
            href={hrefFor("usuarios")}
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar el directorio de usuarios. Los datos mostrados abajo
          pueden estar incompletos.
        </p>
      ) : null}

      <div className="mt-6">
        {users.length === 0 ? (
          <EmptyState
            title="No hay usuarios que coincidan"
            hint={
              search || role || estado
                ? "Pruebe con otro texto o quite los filtros."
                : "El directorio está vacío; dé de alta la primera cuenta con «Nuevo usuario»."
            }
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="ledger min-w-[52rem]">
                <caption className="sr-only">
                  Directorio de usuarios, {total} en total
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="label-rule">
                      Usuario
                    </th>
                    <th scope="col" className="label-rule">
                      Roles
                    </th>
                    <th scope="col" className="label-rule">
                      Estado
                    </th>
                    <th scope="col" className="label-rule">
                      Último acceso
                    </th>
                    <th scope="col" className="label-rule">
                      Alta
                    </th>
                    <th scope="col" className="label-rule text-right">
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user, index) => (
                    <tr
                      key={user.id}
                      data-accent={user.is_active ? "live" : "closed"}
                      className="row-enter"
                      style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
                    >
                      <th scope="row" className="py-4 pr-4 font-normal">
                        <span className="row-title">{user.full_name ?? user.email}</span>
                        <span className="mt-1 block text-xs text-ink-faint">{user.email}</span>
                      </th>
                      <td className="py-4 pr-4">
                        {user.is_superuser ? (
                          <Chip tone="brass" className="mb-1 mr-1">
                            Superusuario
                          </Chip>
                        ) : null}
                        {user.roles.length === 0 ? (
                          <span className="text-xs text-ink-faint">Sin roles</span>
                        ) : (
                          user.roles.map((entry) => (
                            <Chip key={entry} className="mb-1 mr-1">
                              {humanise(entry)}
                            </Chip>
                          ))
                        )}
                      </td>
                      <td className="py-4 pr-4">
                        {user.is_active ? (
                          <Chip tone="forest" dot>
                            Activo
                          </Chip>
                        ) : (
                          <Chip tone="ink" dot>
                            Inactivo
                          </Chip>
                        )}
                      </td>
                      <td className="row-meta py-4 pr-4">
                        {user.last_login_at ? (
                          formatDateTime(user.last_login_at)
                        ) : (
                          <span className="text-ink-faint">Nunca</span>
                        )}
                      </td>
                      <td className="row-meta py-4 pr-4">{formatDate(user.created_at)}</td>
                      <td className="py-4 text-right">
                        <div className="row-actions">
                          {can("users:update") ? <EditUserButton user={user} /> : null}
                          {can("users:assign_roles") ? (
                            <UserRolesButton user={user} roles={roles} />
                          ) : null}
                          {!user.is_active && can("users:update") ? (
                            <ReactivateUserButton user={user} />
                          ) : null}
                          {user.is_active && can("users:delete") ? (
                            user.id === meId ? (
                              <span className="text-xs text-ink-faint">Su propia cuenta</span>
                            ) : (
                              <DeactivateUserButton user={user} />
                            )
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Pager
          total={total}
          skip={skip}
          limit={PAGE_SIZE}
          pageHref={(next) => hrefFor("usuarios", filters, { skip: next })}
        />

        <RuleNote>
          Un usuario no se borra: se desactiva. Su correo deja de poder iniciar sesión,
          pero el nombre con el que firmó cada operación se conserva, que es lo que una
          auditoría exige.
        </RuleNote>
      </div>
    </div>
  );
}

/**
 * The role catalogue and, under it, the permissions those roles are made of.
 *
 * Both are read-only on purpose. Editing roles changes what every member of the
 * firm may do, and it does not belong on a screen someone opens to find out why
 * a colleague cannot see a case.
 */
async function RolesView({
  roles,
  can,
}: {
  roles: RoleRecord[];
  can: (permission: string) => boolean;
}) {
  if (roles.length === 0) {
    return (
      <div className="mt-6">
        <EmptyState
          title="No hay roles que mostrar"
          hint="El catálogo de roles está vacío o su perfil no puede consultarlo."
        />
      </div>
    );
  }

  const { value: permissions } = can("permissions:read")
    ? await load<PermissionRecord[]>("/api/v1/admin/permissions")
    : { value: null };
  const groups = groupBy(permissions ?? [], (entry) => entry.resource);

  return (
    <div className="mt-6">
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="ledger min-w-[46rem]">
            <caption className="sr-only">Catálogo de roles</caption>
            <thead>
              <tr>
                <th scope="col" className="label-rule">
                  Rol
                </th>
                <th scope="col" className="label-rule">
                  Descripción
                </th>
                <th scope="col" className="label-rule">
                  Permisos que concede
                </th>
                <th scope="col" className="label-rule">
                  Alta
                </th>
              </tr>
            </thead>
            <tbody>
              {roles.map((role, index) => (
                <tr
                  key={role.id}
                  data-accent="live"
                  className="row-enter"
                  style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
                >
                  <th scope="row" className="py-4 pr-4 font-normal">
                    <span className="row-title">{humanise(role.name)}</span>
                    <span className="mt-1 block text-xs text-ink-faint">{role.name}</span>
                  </th>
                  <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                    {role.description ?? <span className="text-ink-faint">—</span>}
                  </td>
                  <td className="py-4 pr-4">
                    <div className="flex flex-wrap gap-1">
                      {role.permissions.length === 0 ? (
                        <span className="text-xs text-ink-faint">Sin permisos</span>
                      ) : (
                        role.permissions.map((name) => (
                          <span
                            key={name}
                            className="rounded-card border border-rule bg-surface-sunk px-1.5 py-0.5 font-mono text-[0.6875rem] text-ink-soft"
                          >
                            {name}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="row-meta py-4">{formatDate(role.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <RuleNote>
        Los permisos de una cuenta son la unión de los de sus roles; no se conceden uno
        a uno. Si alguien necesita algo que su rol no da, se amplía el rol y no la
        cuenta, para que la excepción quede visible en vez de escondida.
      </RuleNote>

      <div className="mt-12">
        <SectionHeading eyebrow="Catálogo" title="Permisos" />
        {permissions && permissions.length > 0 ? (
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {Object.entries(groups).map(([resource, entries]) => (
              <Card key={resource} className="p-5">
                <p className="label-rule">{humanise(resource)}</p>
                <ul className="mt-3 space-y-2">
                  {entries.map((entry) => (
                    <li key={entry.id} className="flex flex-wrap items-baseline gap-x-2">
                      <code className="rounded-card bg-paper-deep px-1.5 py-0.5 text-[0.6875rem] text-ink-soft">
                        {entry.name}
                      </code>
                      <span className="text-xs text-ink-muted">
                        {entry.description ?? humanise(entry.action)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        ) : (
          <div className="mt-5">
            <EmptyState
              title="Catálogo de permisos no disponible"
              hint="Su perfil puede consultar roles pero no el catálogo que los compone (permissions:read)."
            />
          </div>
        )}
      </div>
    </div>
  );
}

async function AuditView({
  params,
  hrefFor,
  usersAvailable,
}: {
  params: Record<string, string | string[] | undefined>;
  hrefFor: HrefFor;
  usersAvailable: boolean;
}) {
  const q = first(params.q);
  const resultado = first(params.resultado);
  const actor = first(params.actor);
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);
  const filters = { q, resultado, actor };

  const { value, failed } = await load<PaginatedAuditLogs>("/api/v1/admin/audit-logs", {
    skip,
    limit: PAGE_SIZE,
    search: q,
    result: resultado || undefined,
    user_id: actor,
  });

  const entries = value?.items ?? [];
  const total = value?.total ?? 0;

  const actorOptions = usersAvailable
    ? ((await load<PaginatedUsers>("/api/v1/admin/users", { skip: 0, limit: 200 })).value
        ?.items ?? [])
    : [];

  return (
    <div className="mt-6">
      <FilterBar>
        <input type="hidden" name="vista" value="auditoria" />
        <FilterField
          label="Buscar"
          name="q"
          defaultValue={q}
          placeholder="Acción o entidad"
          className="min-w-[14rem] flex-1"
        />
        <div>
          <label htmlFor="filtro-result" className="label-rule block">
            Resultado
          </label>
          <select
            id="filtro-result"
            name="resultado"
            defaultValue={resultado ?? ""}
            className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
          >
            <option value="">Todos</option>
            <option value="success">Correcto</option>
            <option value="error">Error</option>
          </select>
        </div>
        {actorOptions.length > 0 ? (
          <div>
            <label htmlFor="filtro-actor" className="label-rule block">
              Quién
            </label>
            <select
              id="filtro-actor"
              name="actor"
              defaultValue={actor ?? ""}
              className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
            >
              <option value="">Cualquiera</option>
              {actorOptions.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.email}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-ink-faint">
              Los {actorOptions.length} usuarios más recientes.
            </p>
          </div>
        ) : null}
        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {q || resultado || actor ? (
          <Link
            href={hrefFor("auditoria")}
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar la auditoría. Sin este registro la pantalla no puede
          responder quién hizo qué, que es exactamente lo que se consulta aquí.
        </p>
      ) : null}

      <div className="mt-6">
        {entries.length === 0 ? (
          <EmptyState
            title="Sin entradas de auditoría"
            hint={
              q || resultado || actor
                ? "Pruebe con otro texto o quite los filtros."
                : "Todavía no se ha registrado ninguna operación de escritura."
            }
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="ledger min-w-[58rem]">
                <caption className="sr-only">
                  Registro de auditoría, {total} entradas
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="label-rule">
                      Momento
                    </th>
                    <th scope="col" className="label-rule">
                      Quién
                    </th>
                    <th scope="col" className="label-rule">
                      Acción
                    </th>
                    <th scope="col" className="label-rule">
                      Entidad
                    </th>
                    <th scope="col" className="label-rule">
                      Resultado
                    </th>
                    <th scope="col" className="label-rule">
                      Origen
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry, index) => (
                    <AuditRow key={entry.id} entry={entry} index={index} />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Pager
          total={total}
          skip={skip}
          limit={PAGE_SIZE}
          pageHref={(next) => hrefFor("auditoria", filters, { skip: next })}
        />

        <RuleNote>
          La auditoría guarda la operación, no su contenido: quién hizo qué, desde dónde
          y con qué resultado. Los datos de un formulario no quedan aquí; la dirección
          IP sí, porque sin ella no se distingue al titular de una sesión robada.
        </RuleNote>
      </div>
    </div>
  );
}

function AuditRow({ entry, index }: { entry: AuditLogRecord; index: number }) {
  const [method, path] = auditActionParts(entry.action);

  return (
    <tr
      data-accent={entry.result === "success" ? "live" : "urgent"}
      className="row-enter"
      style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
    >
      <td className="row-meta py-4 pr-4">{formatDateTime(entry.created_at)}</td>
      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
        {entry.user_email ?? <span className="text-ink-faint">Sin usuario</span>}
      </td>
      <td className="py-4 pr-4">
        <Chip tone={method === "DELETE" ? "wax" : "neutral"}>{method}</Chip>
        <span className="mt-1 block break-all font-mono text-[0.6875rem] text-ink-faint">
          {path}
        </span>
      </td>
      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
        {humanise(entry.entity)}
        {entry.entity_id ? (
          <span className="mt-0.5 block font-mono text-[0.6875rem] text-ink-faint">
            {entry.entity_id.slice(0, 8)}
          </span>
        ) : null}
      </td>
      <td className="py-4 pr-4">
        <Chip tone={auditResultTone(entry.result)} dot>
          {auditResultLabel(entry.result)}
        </Chip>
      </td>
      <td className="py-4 text-[0.8125rem] text-ink-muted">
        {entry.ip_address ?? <span className="text-ink-faint">—</span>}
        {entry.user_agent ? (
          <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-faint">
            {entry.user_agent}
          </span>
        ) : null}
      </td>
    </tr>
  );
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

/**
 * Load a resource for a signed-in caller.
 *
 * Redirects only when the session is genuinely gone. Any other failure returns
 * null so the caller can say the list is incomplete: an empty list and a failed
 * list must never look alike.
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
