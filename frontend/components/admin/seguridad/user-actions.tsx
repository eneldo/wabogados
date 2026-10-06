"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button, CheckField, FormStatus } from "@/components/admin/form-controls";
import type { ButtonVariant } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { deactivateUser, reactivateUser, setUserRoles } from "@/features/seguridad/actions";
import type { ActionState, AdminUserRecord, RoleRecord } from "@/lib/types";

/**
 * What can be done to a user from the directory: change who they are allowed to
 * be, take the account away, hand it back.
 *
 * Three separate controls rather than one menu, because they differ in what
 * they need. Roles are a choice among many and belong in a dialog of checkboxes;
 * deactivation is destructive and gets a confirmation that says what survives
 * it; reactivation reverses the first and needs neither a menu nor a warning.
 */

const IDLE: ActionState = { status: "idle" };

export function UserRolesButton({
  user,
  roles,
}: {
  user: AdminUserRecord;
  roles: RoleRecord[];
}) {
  const [state, formAction, pending] = useActionState(setUserRoles, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  // Without the catalogue there is nothing to choose from, and the action would
  // only ever be able to remove roles.
  if (roles.length === 0) return null;

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        Roles
      </Button>

      <dialog
        ref={dialogRef}
        aria-label={`Roles de ${user.email}`}
        className="w-[min(34rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Autorización</p>
            <h2 className="font-display mt-1 text-2xl">Roles de {user.full_name ?? user.email}</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Los permisos de esta cuenta son la unión de los permisos de los roles
              marcados. Al guardar solo se envía lo que cambia.
            </p>
          </header>

          <form action={formAction} className="space-y-4">
            <input type="hidden" name="user_id" value={user.id} />

            <fieldset>
              <legend className="sr-only">Roles disponibles</legend>
              <div className="space-y-2.5">
                {roles.map((role) => (
                  <CheckField
                    key={role.id}
                    name="role_name"
                    value={role.name}
                    label={role.name}
                    hint={
                      role.description ??
                      `${role.permissions.length} permiso${role.permissions.length === 1 ? "" : "s"}`
                    }
                    defaultChecked={user.roles.includes(role.name)}
                  />
                ))}
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
                Guardar roles
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

/**
 * The confirmation that precedes taking an account away.
 *
 * The confirm button does not take the initial focus: pre-focusing a
 * destructive button is how muscle-memory Enter kills an account. And the copy
 * says what survives the click, because "desactivar" reads as "borrar" to
 * anyone who has not been told otherwise.
 *
 * The signed-in user is not offered the action at all. The API refuses it, and
 * a button that always fails is worse than no button.
 */
export function DeactivateUserButton({
  user,
  variant = "quiet",
}: {
  user: AdminUserRecord;
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(deactivateUser, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant={variant} onClick={() => ref.current?.showModal()}>
        <ActionIcon name="deactivate" />
        Desactivar
      </Button>

      <dialog
        ref={ref}
        aria-label={`Desactivar ${user.email}`}
        className="w-[min(30rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <h2 className="font-display text-xl">Desactivar a {user.full_name ?? user.email}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            El registro <strong>no se borra</strong>. Dejará de poder iniciar sesión y
            pasará a figurar como inactivo, pero sus expedientes, documentos y — lo que
            importa aquí — su rastro en la auditoría se conservan intactos.
          </p>

          <div className="mt-5">
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <form action={formAction}>
              <input type="hidden" name="user_id" value={user.id} />
              <Button type="submit" variant="danger" pending={pending}>
                <ActionIcon name="deactivate" />
                Sí, desactivar
              </Button>
            </form>
          </div>
        </div>
      </dialog>
    </>
  );
}

/**
 * Handing an account back, as a one-button form.
 *
 * Nothing is destroyed, so there is nothing to confirm. The feedback is the row
 * itself changing under the button — the account stops being inactive — plus a
 * live region for the sentence, because a refusal the eye never sees is a
 * refusal that did not happen as far as the person clicking is concerned.
 */
export function ReactivateUserButton({ user }: { user: AdminUserRecord }) {
  const [state, formAction, pending] = useActionState(reactivateUser, IDLE);

  return (
    <>
      <form action={formAction} className="inline">
        <input type="hidden" name="user_id" value={user.id} />
        <Button type="submit" variant="quiet" pending={pending}>
          Reactivar
        </Button>
      </form>
      {state.status === "error" ? (
        <span role="alert" className="mt-1 block text-xs text-wax-deep">
          {state.message}
        </span>
      ) : null}
      <span className="sr-only" aria-live="polite">
        {state.status === "ok" ? state.message : ""}
      </span>
    </>
  );
}
