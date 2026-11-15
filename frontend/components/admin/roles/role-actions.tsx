"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button, FormStatus } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { deleteRole } from "@/features/roles/actions";
import type { ActionState, RoleRecord } from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

export function DeleteRoleButton({ role }: { role: RoleRecord }) {
  const [state, formAction, pending] = useActionState(deleteRole, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="deactivate" />
        Eliminar
      </Button>

      <dialog
        ref={dialogRef}
        aria-label={`Eliminar rol ${role.name}`}
        className="w-[min(30rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <h2 className="font-display text-xl">Eliminar rol «{role.name}»?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            Solo es posible eliminar un rol que no esté asignado a ningún usuario. Si está en uso, primero debe retirar el rol de esas cuentas.
          </p>

          <div className="mt-4">
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
              Cancelar
            </Button>
            <form action={formAction}>
              <input type="hidden" name="role_id" value={role.id} />
              <Button type="submit" variant="danger" pending={pending}>
                Sí, eliminar
              </Button>
            </form>
          </div>
        </div>
      </dialog>
    </>
  );
}
