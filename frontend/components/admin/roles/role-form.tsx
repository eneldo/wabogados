"use client";

import { useActionState, useEffect, useMemo, useRef, useState } from "react";

import { Button, FormField, FormStatus, TextInput } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { createRole, updateRole } from "@/features/roles/actions";
import type { ActionState, PermissionRecord, RoleRecord } from "@/lib/types";
import { humanise } from "@/lib/format";

const IDLE: ActionState = { status: "idle" };

function groupPermissions(permissions: PermissionRecord[]) {
  const groups: Record<string, PermissionRecord[]> = {};
  for (const permission of permissions) {
    (groups[permission.resource] ??= []).push(permission);
  }
  for (const entries of Object.values(groups)) {
    entries.sort((a, b) => a.name.localeCompare(b.name));
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
}

function PermissionPicker({
  permissions,
  selected,
  onChange,
  name,
  idPrefix,
}: {
  permissions: PermissionRecord[];
  selected: string[];
  onChange: (names: string[]) => void;
  name: string;
  idPrefix: string;
}) {
  const [filter, setFilter] = useState("");
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const grouped = useMemo(() => groupPermissions(permissions), [permissions]);
  const term = filter.trim().toLowerCase();

  const visible = grouped
    .map(([resource, entries]) => [
      resource,
      entries.filter((entry) => {
        if (!term) return true;
        return (
          entry.name.toLowerCase().includes(term) ||
          entry.resource.toLowerCase().includes(term) ||
          (entry.description ?? "").toLowerCase().includes(term)
        );
      }),
    ] as [string, PermissionRecord[]])
    .filter(([, entries]) => entries.length > 0);

  function toggle(permissionName: string, checked: boolean) {
    if (checked) {
      onChange(Array.from(new Set([...selected, permissionName])));
    } else {
      onChange(selected.filter((name) => name !== permissionName));
    }
  }

  return (
    <fieldset className="space-y-3">
      <legend className="label-rule">Permisos</legend>
      <div>
        <label htmlFor={`${idPrefix}-perm-filter`} className="sr-only">Filtrar permisos</label>
        <input
          id={`${idPrefix}-perm-filter`}
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Buscar permiso o recurso"
          className="w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
        />
      </div>
      <p className="text-xs text-ink-faint">
        Seleccionados: {selected.length}. Un usuario recibe la unión de permisos de todos sus roles.
      </p>
      <div className="max-h-72 overflow-auto rounded-card border border-rule bg-paper-deep/30 p-3">
        {visible.length === 0 ? (
          <p className="text-sm text-ink-muted">No hay permisos que coincidan.</p>
        ) : (
          <div className="space-y-4">
            {visible.map(([resource, entries]) => (
              <div key={resource}>
                <p className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-ink-muted">
                  {humanise(resource)}
                </p>
                <div className="space-y-1.5">
                  {entries.map((permission) => {
                    const id = `${idPrefix}-perm-${permission.name.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
                    return (
                      <label key={permission.id} htmlFor={id} className="flex cursor-pointer items-start gap-2 text-sm">
                        <input
                          id={id}
                          type="checkbox"
                          name={name}
                          value={permission.name}
                          checked={selectedSet.has(permission.name)}
                          onChange={(event) => toggle(permission.name, event.target.checked)}
                          className="mt-0.5"
                        />
                        <span>
                          <code className="rounded bg-surface-sunk px-1 py-0.5 text-[0.6875rem] text-ink-soft">{permission.name}</code>
                          {permission.description ? (
                            <span className="ml-2 text-xs text-ink-muted">{permission.description}</span>
                          ) : null}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </fieldset>
  );
}

export function CreateRoleButton({
  permissions,
  canAct,
}: {
  permissions: PermissionRecord[];
  canAct: boolean;
}) {
  const [state, formAction, pending] = useActionState(createRole, IDLE);
  const [selected, setSelected] = useState<string[]>([]);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.status !== "ok") return;
    if (dialogRef.current?.open) dialogRef.current.close();
    formRef.current?.reset();
    queueMicrotask(() => setSelected([]));
  }, [state]);

  if (!canAct) return null;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo rol
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Crear rol"
        className="w-[min(44rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Roles</p>
            <h2 className="font-display mt-1 text-2xl">Crear rol</h2>
          </header>

          <form ref={formRef} action={formAction} className="space-y-4">
            <FormField label="Nombre" name="name" idPrefix="crear-rol" required error={state.errors?.name}
              hint="Identificador único del rol (ej. administrador, abogado, cliente, asesor).">
              {(props) => <TextInput {...props} required maxLength={100} />}
            </FormField>

            <FormField label="Descripción" name="description" idPrefix="crear-rol" error={state.errors?.description}>
              {(props) => <TextInput {...props} maxLength={500} />}
            </FormField>

            <PermissionPicker
              permissions={permissions}
              selected={selected}
              onChange={setSelected}
              name="permission_names"
              idPrefix="crear-rol"
            />

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button>
              <Button type="submit" variant="primary" pending={pending}>Crear rol</Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

export function EditRoleButton({
  role,
  permissions,
}: {
  role: RoleRecord;
  permissions: PermissionRecord[];
}) {
  const [state, formAction, pending] = useActionState(updateRole, IDLE);
  const [selected, setSelected] = useState<string[]>(role.permissions);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = `editar-rol-${role.id}`;

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="edit" />
        Editar
      </Button>

      <dialog
        ref={dialogRef}
        aria-label={`Editar rol ${role.name}`}
        className="w-[min(44rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Edición</p>
            <h2 className="font-display mt-1 text-2xl">{humanise(role.name)}</h2>
          </header>

          <form action={formAction} className="space-y-4">
            <input type="hidden" name="role_id" value={role.id} />

            <FormField label="Nombre" name="name" idPrefix={prefix} required error={state.errors?.name}>
              {(props) => <TextInput {...props} required defaultValue={role.name} maxLength={100} />}
            </FormField>

            <FormField label="Descripción" name="description" idPrefix={prefix} error={state.errors?.description}>
              {(props) => <TextInput {...props} defaultValue={role.description ?? ""} maxLength={500} />}
            </FormField>

            <PermissionPicker
              permissions={permissions}
              selected={selected}
              onChange={setSelected}
              name="permission_names"
              idPrefix={prefix}
            />

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button>
              <Button type="submit" variant="primary" pending={pending}>Guardar cambios</Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}
