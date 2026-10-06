"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button, FormStatus } from "@/components/admin/form-controls";
import type { ButtonVariant } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { deleteSetting } from "@/features/configuracion/actions";
import type { ActionState, SettingRecord } from "@/lib/types";

/**
 * Removing a setting, which is the exception this module exists to make.
 *
 * Everywhere else in the administration a row is deactivated, archived or closed,
 * because the rows are legal records and destroying one breaks a chain of
 * custody. A setting is not a legal record: it holds no case, no evidence and no
 * signature, so the backend removes the row and keeps the previous value in
 * `change_logs`.
 *
 * The confirmation therefore does not apologise for what it does, but it does not
 * hide it either: it names the key, says the row goes and says where the old
 * value is. The button does not take the initial focus — pre-focusing a
 * destructive control is how a stray Enter deletes something.
 */

const IDLE: ActionState = { status: "idle" };

export function DeleteSettingButton({
  setting,
  variant = "quiet",
}: {
  setting: SettingRecord;
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(deleteSetting, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant={variant} onClick={() => ref.current?.showModal()}>
        <ActionIcon name="deactivate" />
        Eliminar
      </Button>

      <dialog
        ref={ref}
        aria-label={`Eliminar ${setting.key}`}
        className="w-[min(30rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <h2 className="font-display text-xl">Eliminar el ajuste {setting.key}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            La fila <strong>se borra</strong>, y esta es la única parte de la
            administración donde eso ocurre: un ajuste no es un registro jurídico.
            No guarda expedientes ni firmas. Su valor anterior queda anotado en el
            historial de cambios, así que lo que decía se puede volver a escribir.
          </p>

          <div className="mt-5">
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <form action={formAction}>
              <input type="hidden" name="key" value={setting.key} />
              <Button type="submit" variant="danger" pending={pending}>
                <ActionIcon name="deactivate" />
                Sí, eliminar
              </Button>
            </form>
          </div>
        </div>
      </dialog>
    </>
  );
}
