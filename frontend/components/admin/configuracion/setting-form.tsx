"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  Button,
  FormField,
  FormStatus,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { saveSetting } from "@/features/configuracion/actions";
import type { ActionState, SettingRecord } from "@/lib/types";
import { settingValueLabel } from "@/lib/format";

/**
 * The setting editor, used for both creating and changing a row.
 *
 * One component for the two dialogs because the fields are identical; only the
 * key is read-only when editing, since the key *is* the identifier of the row and
 * changing it would silently create a second setting instead of renaming one.
 *
 * The value is edited as the text that is stored, not as the decoded value: an
 * administrator changing `retention.default_days` from 30 to 60 must be able to
 * see the `30` the column holds. The hint says which type it will be read back
 * as, because `30` and `"30"` are the same bytes here and only one of them is a
 * number to whoever reads it later.
 */

const IDLE: ActionState = { status: "idle"};

function Fields({
  prefix,
  setting,
  lockedKey,
}: {
  prefix: string;
  /** Absent when creating. */
  setting?: SettingRecord;
  lockedKey?: boolean;
}) {
  return (
    <>
      <FormField
        label="Clave"
        name="key"
        idPrefix={prefix}
        required
        hint={
          lockedKey
            ? "La clave identifica el ajuste y no se cambia: escribirla crearía otro ajuste."
            : "Minúsculas, dígitos, punto, guion o guion bajo. Es la clave con la que el sistema lo lee."
        }
      >
        {(props) => (
          <TextInput
            {...props}
            required
            maxLength={100}
            readOnly={lockedKey}
            defaultValue={setting?.key}
            autoComplete="off"
            spellCheck={false}
            className="font-mono"
          />
        )}
      </FormField>

      <FormField
        label="Valor"
        name="value"
        idPrefix={prefix}
        required
        hint="Un número, un booleano (true/false), un objeto JSON o texto. Sin comillas: se guarda tal cual."
      >
        {(props) => (
          <TextArea
            {...props}
            required
            rows={3}
            spellCheck={false}
            defaultValue={setting ? setting.raw_value : ""}
            className="font-mono text-[0.8125rem]"
          />
        )}
      </FormField>

      <FormField
        label="Categoría"
        name="category"
        idPrefix={prefix}
        hint="Agrupa los ajustes en la pantalla. Por defecto, «general»."
      >
        {(props) => (
          <TextInput
            {...props}
            maxLength={50}
            defaultValue={setting?.category ?? "general"}
            autoComplete="off"
          />
        )}
      </FormField>

      <FormField
        label="Descripción"
        name="description"
        idPrefix={prefix}
        hint="Qué es este ajuste y qué pasa si se cambia. La siguiente persona que lo lea probablemente sea usted dentro de dos años."
      >
        {(props) => (
          <TextArea {...props} rows={2} maxLength={500} defaultValue={setting?.description ?? ""} />
        )}
      </FormField>
    </>
  );
}

export function SettingForm({ canAct }: { canAct: boolean }) {
  const [state, formAction, pending] = useActionState(saveSetting, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.status !== "ok") return;
    if (dialogRef.current?.open) dialogRef.current.close();
    // The dialog keeps its DOM between openings: without this, the next
    // "Nuevo ajuste" opens still holding the one just saved.
    formRef.current?.reset();
  }, [state]);

  if (!canAct) return null;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo ajuste
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Registrar ajuste"
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Registrar ajuste</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Un ajuste es un valor que el sistema lee mientras funciona, sin
              reinstalarlo. No es un expediente: no guarda datos del estudio.
            </p>
          </header>

          <form ref={formRef} action={formAction} className="space-y-4">
            <Fields prefix="crear-ajuste" />

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
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

/**
 * Editing one row.
 *
 * The dialog is rendered per row, so every control carries an id prefix built
 * from the key: without it the page would repeat `editar-ajuste-value` once per
 * setting and every `<label htmlFor>` on it would focus whichever control the
 * browser finds first.
 */
export function EditSettingButton({
  setting,
  canAct,
}: {
  setting: SettingRecord;
  canAct: boolean;
}) {
  const [state, formAction, pending] = useActionState(saveSetting, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = `editar-ajuste-${setting.key.replace(/[^a-z0-9]+/gi, "-")}`;

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  if (!canAct) return null;

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        Editar
      </Button>

      <dialog
        ref={dialogRef}
        aria-label={`Editar ${setting.key}`}
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Ajuste</p>
            <h2 className="font-display mt-1 break-all text-2xl">{setting.key}</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Hoy vale{" "}
              <code className="rounded bg-surface-sunk px-1 py-0.5 font-mono text-xs">
                {settingValueLabel(setting.value, setting.raw_value)}
              </code>
              .
            </p>
          </header>

          <form action={formAction} className="space-y-4">
            <Fields prefix={prefix} setting={setting} lockedKey />

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
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
