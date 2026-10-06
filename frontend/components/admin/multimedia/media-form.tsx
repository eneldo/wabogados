"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  Button,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { createMedia, updateMedia } from "@/features/multimedia/actions";
import type { ActionState, MediaRecord } from "@/lib/types";

/**
 * The library form, for registering a resource and for editing one.
 *
 * **The file is not part of it.** A resource can be registered before its file
 * exists — a librarian files the recording and it arrives later — and the list
 * shows that state honestly as "sin archivo". The upload has its own control for
 * the same reason: one dialog that both registers and uploads would have to decide
 * what to do with the row when the upload fails, and the row is the part that
 * matters.
 *
 * The kind is not editable and not offered: the server derives it from the bytes,
 * so a field for it would be a value nobody can set truthfully.
 */

const IDLE: ActionState = { status: "idle"};

export function MediaForm({
  canAct,
  cases,
}: {
  canAct: boolean;
  /** Expedientes offered as an optional link. Empty means none were loaded. */
  cases: { id: string; case_number: string; title: string }[];
}) {
  const [state, formAction, pending] = useActionState(createMedia, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.status !== "ok") return;
    if (dialogRef.current?.open) dialogRef.current.close();
    // The dialog keeps its DOM between openings: without this, the next
    // "Nuevo recurso" opens still holding the file just chosen.
    formRef.current?.reset();
  }, [state]);

  if (!canAct) return null;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo recurso
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Registrar recurso"
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Registrar recurso</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Un recurso de la biblioteca de la firma. El archivo puede esperar: se
              registra ahora y se carga cuando llegue.
            </p>
          </header>

          <form ref={formRef} action={formAction} className="space-y-4">
            <FormField label="Título" name="title" idPrefix="crear-recurso" required>
              {(props) => <TextInput {...props} required minLength={3} maxLength={255} />}
            </FormField>

            <FormField
              label="Descripción"
              name="description"
              idPrefix="crear-recurso"
              hint="Qué es, dónde se grabó y quién aparece. Es lo que se lee dentro de seis meses."
            >
              {(props) => <TextArea {...props} rows={2} maxLength={4000} />}
            </FormField>

            <FormField
              label="Etiquetas"
              name="tags"
              idPrefix="crear-recurso"
              hint="Separadas por comas. Texto libre: no hay un vocabulario cerrado."
            >
              {(props) => <TextInput {...props} maxLength={1000} placeholder="obra, vía, inspección" />}
            </FormField>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Confidencialidad" name="confidentiality" idPrefix="crear-recurso">
                {(props) => (
                  <SelectInput {...props} defaultValue="interno">
                    <option value="interno">Interno</option>
                    <option value="restringido">Restringido</option>
                    <option value="confidencial">Confidencial</option>
                  </SelectInput>
                )}
              </FormField>

              <FormField
                label="Expediente"
                name="case_id"
                idPrefix="crear-recurso"
                hint="Opcional: el material de la biblioteca no pertenece a ningún expediente."
              >
                {(props) => (
                  <SelectInput {...props} defaultValue="">
                    <option value="">Sin expediente</option>
                    {cases.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.case_number} · {entry.title}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </FormField>
            </div>

            <FormField
              label="Archivo"
              name="file"
              idPrefix="crear-recurso"
              hint="Opcional. El tipo se reconoce por el contenido, no por el nombre."
            >
              {(props) => <input {...props} type="file" className="w-full text-sm text-ink-muted file:mr-3 file:rounded-card file:border file:border-rule-strong file:bg-surface file:px-3 file:py-2 file:text-xs file:font-semibold" />}
            </FormField>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Registrar
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

export function EditMediaButton({
  item,
  canAct,
  cases,
}: {
  item: MediaRecord;
  canAct: boolean;
  cases: { id: string; case_number: string; title: string }[];
}) {
  const [state, formAction, pending] = useActionState(updateMedia, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);

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
        aria-label={`Editar ${item.title}`}
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Recurso</p>
            <h2 className="font-display mt-1 text-2xl">{item.title}</h2>
          </header>

          <form action={formAction} className="space-y-4">
            <input type="hidden" name="id" value={item.id} />

            <FormField label="Título" name="title" idPrefix="editar-recurso" required>
              {(props) => (
                <TextInput {...props} required minLength={3} maxLength={255} defaultValue={item.title} />
              )}
            </FormField>

            <FormField label="Descripción" name="description" idPrefix="editar-recurso">
              {(props) => (
                <TextArea {...props} rows={2} maxLength={4000} defaultValue={item.description ?? ""} />
              )}
            </FormField>

            <FormField label="Etiquetas" name="tags" idPrefix="editar-recurso">
              {(props) => <TextInput {...props} maxLength={1000} defaultValue={item.tags ?? ""} />}
            </FormField>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Confidencialidad" name="confidentiality" idPrefix="editar-recurso">
                {(props) => (
                  <SelectInput {...props} defaultValue={item.confidentiality}>
                    <option value="interno">Interno</option>
                    <option value="restringido">Restringido</option>
                    <option value="confidencial">Confidencial</option>
                  </SelectInput>
                )}
              </FormField>

              <FormField label="Estado" name="status" idPrefix="editar-recurso">
                {(props) => (
                  <SelectInput {...props} defaultValue={item.status}>
                    <option value="activo">Activo</option>
                    <option value="archivado">Archivado</option>
                  </SelectInput>
                )}
              </FormField>
            </div>

            <FormField label="Expediente" name="case_id" idPrefix="editar-recurso">
              {(props) => (
                <SelectInput {...props} defaultValue={item.case_id ?? ""}>
                  <option value="">Sin expediente</option>
                  {cases.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.case_number} · {entry.title}
                    </option>
                  ))}
                </SelectInput>
              )}
            </FormField>

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
