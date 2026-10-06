"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button, FormField, FormStatus } from "@/components/admin/form-controls";
import type { ButtonVariant } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import {
  deactivateMedia,
  reactivateMedia,
  uploadMediaFile,
} from "@/features/multimedia/actions";
import type { ActionState, MediaRecord } from "@/lib/types";

/**
 * What can be done to a resource from the library.
 *
 * Upload is separated from the register form because a resource may exist without
 * a file, and this is the control that fills that gap. Deactivation confirms, and
 * reactivation does not: it reverses the first and there is nothing to undo.
 */

const IDLE: ActionState = { status: "idle"};

export function UploadMediaButton({
  item,
  canAct,
}: {
  item: MediaRecord;
  canAct: boolean;
}) {
  const [state, formAction, pending] = useActionState(uploadMediaFile, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.status !== "ok") return;
    if (dialogRef.current?.open) dialogRef.current.close();
    formRef.current?.reset();
  }, [state]);

  if (!canAct) return null;

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        {item.has_file ? "Reemplazar archivo" : "Cargar archivo"}
      </Button>

      <dialog
        ref={dialogRef}
        aria-label={`Cargar archivo de ${item.title}`}
        className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <header className="mb-4">
            <p className="label-rule">Archivo</p>
            <h2 className="font-display mt-1 text-xl">{item.title}</h2>
            <p className="mt-2 text-sm text-ink-muted">
              {item.has_file
                ? "El archivo actual se sustituye. El registro y su historial se conservan; lo que se retira es el archivo anterior."
                : "El recurso está registrado y todavía no tiene archivo."}
            </p>
          </header>

          <form ref={formRef} action={formAction} className="space-y-4">
            <input type="hidden" name="id" value={item.id} />
            <FormField
              label="Archivo"
              name="file"
              idPrefix={`subir-${item.id}`}
              required
              hint="Vídeo, imagen, audio o PDF. El tipo se reconoce por el contenido: un MP4 renombrado a .jpg se archiva como vídeo."
            >
              {(props) => (
                <input
                  {...props}
                  required
                  type="file"
                  className="w-full text-sm text-ink-muted file:mr-3 file:rounded-card file:border file:border-rule-strong file:bg-surface file:px-3 file:py-2 file:text-xs file:font-semibold"
                />
              )}
            </FormField>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Cargar
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

/**
 * Taking a resource out of the library.
 *
 * Nothing is deleted here, and the confirmation says what survives it — including
 * the file, which is the part people assume disappears. The destructive button
 * does not take the initial focus: pre-focusing it is how a stray Enter removes
 * something.
 */
export function DeactivateMediaButton({
  item,
  variant = "quiet",
}: {
  item: MediaRecord;
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(deactivateMedia, IDLE);
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
        aria-label={`Desactivar ${item.title}`}
        className="w-[min(30rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <h2 className="font-display text-xl">Desactivar {item.title}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            El registro <strong>no se borra</strong> y el archivo tampoco: sale del
            listado del día a día y deja de poder reproducirse, pero su historial y
            su contenido siguen ahí y se puede volver a activar.
          </p>

          <div className="mt-5">
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <form action={formAction}>
              <input type="hidden" name="id" value={item.id} />
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
 * Handing a resource back, as a one-button form.
 *
 * Nothing was destroyed, so there is nothing to confirm; the feedback is the row
 * itself changing under the button plus a live region for the sentence.
 */
export function ReactivateMediaButton({ item }: { item: MediaRecord }) {
  const [state, formAction, pending] = useActionState(reactivateMedia, IDLE);

  return (
    <>
      <form action={formAction} className="inline">
        <input type="hidden" name="id" value={item.id} />
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
