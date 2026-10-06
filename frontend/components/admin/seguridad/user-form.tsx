"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  Button,
  CheckField,
  FormField,
  FormStatus,
  TextInput,
} from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { createUser, updateUser } from "@/features/seguridad/actions";
import type { ActionState, AdminUserRecord, RoleRecord } from "@/lib/types";

/**
 * The user form, used for both creating and editing.
 *
 * One component for the two dialogs because they differ by four fields and one
 * endpoint, and a second copy would drift the first time the API gained a
 * field. Every control is prefixed with the dialog's own id: the page renders
 * the create dialog plus one edit dialog per row, and a repeated id silently
 * breaks every `<label htmlFor>` on it.
 *
 * The state of the account is not here. A form that can lock somebody out with
 * a stray checkbox is the wrong place for it, so activation and deactivation
 * live behind their own actions, each with its own confirmation.
 */

const IDLE: ActionState = { status: "idle" };

export function UserForm({
  roles,
  canAct,
}: {
  /** The catalogue to choose from. Empty means the profile may not read roles. */
  roles: RoleRecord[];
  canAct: boolean;
}) {
  const [state, formAction, pending] = useActionState(createUser, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.status !== "ok") return;
    if (dialogRef.current?.open) dialogRef.current.close();
    // The dialog keeps its DOM between openings: without this, the next
    // "Nuevo usuario" starts pre-filled with the account just created.
    formRef.current?.reset();
  }, [state]);

  if (!canAct) return null;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo usuario
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Registrar usuario"
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Registrar usuario</h2>
          </header>

          <form ref={formRef} action={formAction} className="space-y-4">
            <FormField
              label="Correo electrónico"
              name="email"
              idPrefix="crear-usuario"
              required
              error={state.errors?.email}
              hint="Es también el nombre con el que inicia sesión."
            >
              {(props) => <TextInput {...props} type="email" required maxLength={255} />}
            </FormField>

            <FormField
              label="Nombre completo"
              name="full_name"
              idPrefix="crear-usuario"
              error={state.errors?.full_name}
            >
              {(props) => <TextInput {...props} maxLength={255} />}
            </FormField>

            <FormField
              label="Contraseña"
              name="password"
              idPrefix="crear-usuario"
              required
              error={state.errors?.password}
              hint="Mínimo 8 caracteres. Se guarda cifrada: nadie, aquí ni en el backend, la ve en claro."
            >
              {(props) => (
                <TextInput {...props} type="password" required minLength={8} maxLength={128} autoComplete="new-password" />
              )}
            </FormField>

            {roles.length > 0 ? (
              <fieldset>
                <legend className="label-rule">Roles</legend>
                <div className="mt-2 space-y-2">
                  {roles.map((role) => (
                    <CheckField
                      key={role.id}
                      name="role_names"
                      value={role.name}
                      label={role.name}
                      hint={role.description ?? undefined}
                    />
                  ))}
                </div>
                <p className="mt-2 text-xs text-ink-faint">
                  Los permisos del usuario son los de sus roles. Un usuario sin roles
                  no puede entrar en la administración.
                </p>
              </fieldset>
            ) : (
              <p className="rounded-card border border-brass/40 bg-brass-tint px-3 py-2.5 text-xs text-brass">
                No se pueden ofrecer roles: su perfil no puede consultarlos. La cuenta
                quedará sin roles y no podrá iniciar sesión hasta que alguien con
                <code className="mx-1">roles:read</code> se los asigne.
              </p>
            )}

            <CheckField
              name="is_superuser"
              label="Superusuario"
              hint="Ve y hace todo, incluida esta pantalla. Concédaselo solo a quien lo usará a diario."
            />

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button
                type="button"
                variant="ghost"
                onClick={() => dialogRef.current?.close()}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Dar de alta
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

export function EditUserButton({ user }: { user: AdminUserRecord }) {
  const [state, formAction, pending] = useActionState(updateUser, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = `editar-usuario-${user.id}`;

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
        aria-label={`Editar ${user.email}`}
        className="w-[min(34rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Edición</p>
            <h2 className="font-display mt-1 text-2xl">{user.full_name ?? user.email}</h2>
          </header>

          <form action={formAction} className="space-y-4">
            <input type="hidden" name="user_id" value={user.id} />

            <FormField
              label="Correo electrónico"
              name="email"
              idPrefix={prefix}
              required
              error={state.errors?.email}
            >
              {(props) => (
                <TextInput {...props} type="email" required defaultValue={user.email} maxLength={255} />
              )}
            </FormField>

            <FormField
              label="Nombre completo"
              name="full_name"
              idPrefix={prefix}
              error={state.errors?.full_name}
            >
              {(props) => (
                <TextInput {...props} defaultValue={user.full_name ?? ""} maxLength={255} />
              )}
            </FormField>

            <fieldset>
              <legend className="label-rule">Autorización</legend>
              <div className="mt-2 space-y-2">
                <CheckField
                  name="is_superuser"
                  label="Superusuario"
                  defaultChecked={user.is_superuser}
                  hint="Salta toda regla de permisos y de alcance. Es la llave maestra."
                />
                <CheckField
                  name="is_verified"
                  label="Correo verificado"
                  defaultChecked={user.is_verified}
                  hint="Solo importa si la cuenta se creó con la verificación pendiente."
                />
              </div>
            </fieldset>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button
                type="button"
                variant="ghost"
                onClick={() => dialogRef.current?.close()}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Guardar cambios
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}
