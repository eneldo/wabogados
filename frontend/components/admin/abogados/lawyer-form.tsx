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
import type { ButtonVariant } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import type { ActionState, LawyerRecord, LegalAreaOption } from "@/lib/types";

/**
 * The lawyer form, for creating and editing.
 *
 * Two things here are not in the client form and both come from the schema:
 *
 * - **Specialties are free text, one per line.** The API takes a list of
 *   strings, and a textarea where each line is one specialty is the only control
 *   that maps a list onto a form without a chip editor nobody asked for.
 * - **Legal areas are the catalogue the firm already seeded.** They are read
 *   from `GET /lawyers/legal-areas`, sent back as ids, and rendered as
 *   checkboxes — the area list is reference data, not free text, and typing it
 *   would produce thirteen ways to spell "Derecho laboral".
 */

const IDLE: ActionState = { status: "idle" };

const STATUSES = [
  { value: "activo", label: "Activo" },
  { value: "inactivo", label: "Inactivo" },
  { value: "suspendido", label: "Suspendido" },
];

const DOCUMENT_TYPES = [
  { value: "DNI", label: "DNI" },
  { value: "CE", label: "Cédula de extranjero" },
  { value: "PASSPORT", label: "Pasaporte" },
  { value: "RUC", label: "RUC" },
  { value: "OTROS", label: "Otros" },
];

export function LawyerForm({
  action,
  lawyer,
  areas,
  legal = false,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  lawyer?: LawyerRecord;
  areas: LegalAreaOption[];
  legal?: boolean;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const editing = Boolean(lawyer);

  useEffect(() => {
    if (state.status === "ok" && legal && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [state, legal]);

  /*
    The API answers with area **names**, not ids, so the boxes are pre-checked by
    matching the record's names against the catalogue.
  */
  const selectedNames = new Set(lawyer?.legal_areas ?? []);

  const body = (
    <form action={formAction} className="space-y-4">
      {lawyer ? <input type="hidden" name="lawyer_id" value={lawyer.id} /> : null}

      <FormField
        label="Nombre completo"
        name="full_name"
        required
        error={state.errors?.full_name}
      >
        {(props) => (
          <TextInput
            {...props}
            required
            minLength={3}
            maxLength={255}
            defaultValue={lawyer?.full_name ?? ""}
          />
        )}
      </FormField>

      {!editing ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label="Tipo de documento"
            name="document_type"
            required
            error={state.errors?.document_type}
          >
            {(props) => (
              <SelectInput {...props} defaultValue="DNI">
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </SelectInput>
            )}
          </FormField>
          <FormField
            label="Número de documento"
            name="document_number"
            required
            error={state.errors?.document_number}
          >
            {(props) => <TextInput {...props} required minLength={3} maxLength={50} />}
          </FormField>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="Tarjeta profesional"
          name="professional_card"
          error={state.errors?.professional_card}
        >
          {(props) => (
            <TextInput
              {...props}
              maxLength={100}
              defaultValue={lawyer?.professional_card ?? ""}
            />
          )}
        </FormField>
        <FormField label="Estado" name="status" error={state.errors?.status}>
          {(props) => (
            <SelectInput {...props} defaultValue={lawyer?.status ?? "activo"}>
              {STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </FormField>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Correo electrónico" name="email" error={state.errors?.email}>
          {(props) => (
            <TextInput
              {...props}
              type="email"
              maxLength={255}
              defaultValue={lawyer?.email ?? ""}
            />
          )}
        </FormField>
        <FormField label="Teléfono" name="phone" error={state.errors?.phone}>
          {(props) => (
            <TextInput
              {...props}
              type="tel"
              maxLength={50}
              defaultValue={lawyer?.phone ?? ""}
            />
          )}
        </FormField>
      </div>

      <FormField
        label="Especialidades"
        name="specialties"
        error={state.errors?.specialties}
        hint="Una por línea. El servidor las divide y descarta las repetidas."
      >
        {(props) => (
          <TextArea
            {...props}
            rows={3}
            maxLength={400}
            defaultValue={(lawyer?.specialties ?? []).join("\n")}
          />
        )}
      </FormField>

      <fieldset>
        <legend className="label-rule">Áreas jurídicas</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {areas.map((area) => (
            <label
              key={area.id}
              className="flex items-start gap-2 text-sm text-ink-soft"
            >
              <input
                type="checkbox"
                name="legal_area_ids"
                value={area.id}
                defaultChecked={selectedNames.has(area.name)}
                className="mt-0.5 size-4 shrink-0 accent-wax"
              />
              <span>
                {area.name}
                {area.description ? (
                  <span className="mt-0.5 block text-xs text-ink-faint">
                    {area.description}
                  </span>
                ) : null}
              </span>
            </label>
          ))}
        </div>
        {state.errors?.legal_area_ids ? (
          <p className="mt-1.5 text-xs font-medium text-wax-deep">
            {state.errors.legal_area_ids}
          </p>
        ) : null}
      </fieldset>

      <FormField
        label="URL de la fotografía"
        name="photo_url"
        error={state.errors?.photo_url}
        hint="Opcional. Mientras no haya una imagen aprovada, la web pública no muestra retratos."
      >
        {(props) => (
          <TextInput
            {...props}
            type="url"
            maxLength={500}
            defaultValue={lawyer?.photo_url ?? ""}
          />
        )}
      </FormField>

      <FormStatus state={state} />

      <div className="flex justify-end gap-2 pt-1">
        {legal ? (
          <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
            Cancelar
          </Button>
        ) : null}
        <Button type="submit" variant="primary" pending={pending}>
          {editing ? "Guardar cambios" : "Registrar abogado"}
        </Button>
      </div>
    </form>
  );

  if (!legal) return body;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo abogado
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Registrar abogado"
        className="w-[min(40rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Registrar abogado</h2>
          </header>
          {body}
        </div>
      </dialog>
    </>
  );
}

export function DeactivateLawyerButton({
  action,
  lawyerId,
  lawyerName,
  variant = "danger",
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  lawyerId: string;
  lawyerName: string;
  /** `quiet` inside a table row, where the real decision happens in the dialog. */
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
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
        aria-label="Desactivar abogado"
        className="w-[min(30rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <h2 className="font-display text-xl">Desactivar a {lawyerName}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            El registro se conserva. Sus expedientes, documentos, evidencias y su
            historial permanecen intactos y no volverá a aparecer en la
            asignación de trabajo.
          </p>

          <div className="mt-5">
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <form action={formAction}>
              <input type="hidden" name="lawyer_id" value={lawyerId} />
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
