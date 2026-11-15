import { redirect } from "next/navigation";

import { DeleteRoleButton } from "@/components/admin/roles/role-actions";
import { CreateRoleButton, EditRoleButton } from "@/components/admin/roles/role-form";
import { PageHeader } from "@/components/admin/page-furniture";
import { Card, EmptyState, RuleNote, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import { formatDate, humanise } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { PermissionRecord, RoleRecord } from "@/lib/types";

export default async function RolesPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const { profile } = session;
  const can = (permission: string) => profile.permissions.includes(permission);
  if (!can("roles:read")) {
    return (
      <div>
        <PageHeader
          eyebrow="Administración"
          title="Roles"
          description="Su perfil no tiene permiso para consultar roles."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso"
            hint="Consulte con un administrador si necesita gestionar roles y permisos."
          />
        </div>
      </div>
    );
  }

  const roles = (await load<RoleRecord[]>("/api/v1/admin/roles")).value ?? [];
  const permissions = can("permissions:read")
    ? ((await load<PermissionRecord[]>("/api/v1/admin/permissions")).value ?? [])
    : [];
  const canManage = can("roles:manage");
  const groups = groupBy(permissions, (entry) => entry.resource);

  return (
    <div>
      <PageHeader
        eyebrow="Administración"
        title="Roles"
        description="Cree y administre roles, y defina los permisos que otorga cada uno. Los usuarios reciben los permisos de los roles que tengan asignados (por ejemplo, administrador, abogado, cliente, asistente u otros)."
        actions={canManage ? <CreateRoleButton permissions={permissions} canAct={canManage && permissions.length > 0} /> : null}
      />

      {canManage && permissions.length === 0 ? (
        <p className="mt-4 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No se puede crear o editar roles sin acceso al catálogo de permisos (`permissions:read`).
        </p>
      ) : null}

      <div className="mt-6">
        {roles.length === 0 ? (
          <EmptyState
            title="No hay roles registrados"
            hint={canManage ? "Cree el primer rol con «Nuevo rol»." : "No hay roles disponibles."}
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="ledger min-w-[52rem]">
                <caption className="sr-only">Catálogo de roles</caption>
                <thead>
                  <tr>
                    <th scope="col" className="label-rule">Rol</th>
                    <th scope="col" className="label-rule">Descripción</th>
                    <th scope="col" className="label-rule">Permisos</th>
                    <th scope="col" className="label-rule">Alta</th>
                    <th scope="col" className="label-rule text-right"><span className="sr-only">Acciones</span></th>
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
                      <th scope="row" className="py-4 pr-4 font-normal align-top">
                        <span className="row-title">{humanise(role.name)}</span>
                        <span className="mt-1 block text-xs text-ink-faint">{role.name}</span>
                      </th>
                      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted align-top">
                        {role.description ?? <span className="text-ink-faint">—</span>}
                      </td>
                      <td className="py-4 pr-4 align-top">
                        <div className="flex max-w-[36rem] flex-wrap gap-1">
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
                        <p className="mt-2 text-xs text-ink-faint">{role.permissions.length} permiso(s)</p>
                      </td>
                      <td className="row-meta py-4 pr-4 align-top">{formatDate(role.created_at)}</td>
                      <td className="py-4 text-right align-top">
                        <div className="row-actions">
                          {canManage && permissions.length > 0 ? (
                            <EditRoleButton role={role} permissions={permissions} />
                          ) : null}
                          {canManage ? <DeleteRoleButton role={role} /> : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <RuleNote>
          Modificar los permisos de un rol afecta a todos los usuarios que lo tengan asignado. Si un rol está asignado, no podrá eliminarse hasta retirarlo de esas cuentas.
        </RuleNote>

        <div className="mt-12">
          <SectionHeading eyebrow="Catálogo" title="Permisos disponibles" />
          {permissions.length > 0 ? (
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
                hint="Se requiere `permissions:read` para ver y asignar permisos."
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  const groups: Record<string, T[]> = {};
  for (const item of items) {
    const group = key(item);
    (groups[group] ??= []).push(item);
  }
  return groups;
}

async function load<T>(path: string): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}
