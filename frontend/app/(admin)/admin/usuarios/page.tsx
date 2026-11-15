import Link from "next/link";
import { redirect } from "next/navigation";

import {
  DeactivateUserButton,
  ReactivateUserButton,
  UserRolesButton,
} from "@/components/admin/seguridad/user-actions";
import { EditUserButton, UserForm } from "@/components/admin/seguridad/user-form";
import { ResetPasswordButton } from "@/components/admin/seguridad/reset-password";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader, Pager } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import { formatDate, formatDateTime, humanise } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { PaginatedUsers, RoleRecord } from "@/lib/types";

const PAGE_SIZE = 25;

export default async function UsersPage({
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
  const can = (permission: string) => profile.isSuperuser || profile.permissions.includes(permission);
  if (!can("users:read")) {
    return (
      <div>
        <PageHeader
          eyebrow="Administración"
          title="Usuarios"
          description="Su perfil no tiene permiso para consultar usuarios."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso"
            hint="Consulte con un administrador si necesita gestionar usuarios."
          />
        </div>
      </div>
    );
  }

  const params = await searchParams;
  const search = first(params.search);
  const role = first(params.role);
  const estado = first(params.estado);
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);
  const filters = { search, role, estado };

  const roles = can("roles:read")
    ? ((await load<RoleRecord[]>("/api/v1/admin/roles")).value ?? [])
    : [];

  const { value, failed } = await load<PaginatedUsers>("/api/v1/admin/users", {
    skip,
    limit: PAGE_SIZE,
    search,
    role,
    is_active: estado === "activo" ? true : estado === "inactivo" ? false : undefined,
  });

  const users = value?.items ?? [];
  const total = value?.total ?? 0;

  const hrefFor = (next: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    for (const [key, val] of Object.entries(filters)) {
      if (val) query.set(key, val);
    }
    for (const [key, val] of Object.entries(next)) {
      if (val !== undefined && val !== "") query.set(key, String(val));
    }
    const qs = query.toString();
    return qs ? `/admin/usuarios?${qs}` : "/admin/usuarios";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Administración"
        title="Usuarios"
        description="Cuentas de acceso, roles asignados y estado. Cree usuarios, asígneles roles (administrador, abogado, cliente, asistente u otros) y desactive cuentas cuando corresponda."
        actions={<UserForm roles={roles} canAct={can("users:create")} />}
      />

      <div className="mt-6">
        <FilterBar>
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
              href="/admin/usuarios"
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
                  <caption className="sr-only">Directorio de usuarios, {total} en total</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="label-rule">Usuario</th>
                      <th scope="col" className="label-rule">Roles</th>
                      <th scope="col" className="label-rule">Estado</th>
                      <th scope="col" className="label-rule">Último acceso</th>
                      <th scope="col" className="label-rule">Alta</th>
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
                            <Chip tone="brass" className="mb-1 mr-1">Superusuario</Chip>
                          ) : null}
                          {user.roles.length === 0 ? (
                            <span className="text-xs text-ink-faint">Sin roles</span>
                          ) : (
                            user.roles.map((entry) => (
                              <Chip key={entry} className="mb-1 mr-1">{humanise(entry)}</Chip>
                            ))
                          )}
                        </td>
                        <td className="py-4 pr-4">
                          {user.is_active ? (
                            <Chip tone="forest" dot>Activo</Chip>
                          ) : (
                            <Chip tone="ink" dot>Inactivo</Chip>
                          )}
                        </td>
                        <td className="row-meta py-4 pr-4">
                          {user.last_login_at ? formatDateTime(user.last_login_at) : <span className="text-ink-faint">Nunca</span>}
                        </td>
                        <td className="row-meta py-4 pr-4">{formatDate(user.created_at)}</td>
                        <td className="py-4 text-right">
                          <div className="row-actions">
                            {can("users:update") && (!user.is_superuser || profile.isSuperuser) ? <EditUserButton user={user} /> : null}
                            {can("users:reset_password") && user.is_active && user.id !== profile.id && (!user.is_superuser || profile.isSuperuser) ? (
                              <ResetPasswordButton user={user} />
                            ) : null}
                            {can("users:assign_roles") ? <UserRolesButton user={user} roles={roles} /> : null}
                            {!user.is_active && can("users:update") ? <ReactivateUserButton user={user} /> : null}
                            {user.is_active && can("users:delete") ? (
                              user.id === profile.id ? (
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
            pageHref={(next) => hrefFor({ ...filters, skip: next })}
          />

          <RuleNote>
            Un usuario no se borra: se desactiva. Puede crear usuarios y asignarles roles según su función (administrador, abogado, cliente, asistente u otros roles disponibles).
          </RuleNote>
        </div>
      </div>
    </div>
  );
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

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
