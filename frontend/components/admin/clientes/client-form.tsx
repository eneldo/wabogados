"use client";

import { useActionState, useEffect, useRef, useState } from "react";

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
import type { ActionState, ClientRecord } from "@/lib/types";

/**
 * The client form, used for both creating and editing.
 *
 * One component for both because the two screens differ by three fields and one
 * endpoint. Two components would drift, and the next time the API gained a field
 * only one of them would be updated — which is how a form starts rejecting valid
 * input.
 *
 * The `document_type` and `document_number` pair is shown **only** when creating.
 * They are absent from `ClientUpdate`, and showing a field that cannot be saved
 * is worse than not showing it.
 */

const DOCUMENT_TYPES = [
  { value: "DNI", label: "DNI" },
  { value: "CE", label: "Cédula de extranjero" },
  { value: "PASSPORT", label: "Pasaporte" },
  { value: "RUC", label: "RUC" },
  { value: "OTROS", label: "Otros" },
];

const IDLE: ActionState = { status: "idle" };

export function ClientForm({
  action,
  client,
  legal = false,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  /** Present when editing; absent when creating. */
  client?: ClientRecord;
  /** Open as a dialog (create) or inline (edit). */
  legal?: boolean;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const [clientType, setClientType] = useState<"natural" | "juridica">(
    client?.client_type ?? "natural",
  );
  const dialogRef = useRef<HTMLDialogElement>(null);
  const editing = Boolean(client);

  /*
    Close the dialog only after a confirmed success. Doing it on any state
    change would slam the dialog shut on the first validation error, and the
    person would lose the half-typed form to find out one field was wrong.
  */
  useEffect(() => {
    if (state.status === "ok" && legal && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [state, legal]);

  const body = (
    <form action={formAction} className="space-y-4">
      {client ? <input type="hidden" name="client_id" value={client.id} /> : null}

      {!editing ? (
        <FormField
          label="Tipo de cliente"
          name="client_type"
          required
          error={state.errors?.client_type}
          hint="Una persona natural se identifica por su nombre; una jurídica, por su razón social."
        >
          {(props) => (
            <SelectInput
              {...props}
              value={clientType}
              onChange={(event) =>
                setClientType(event.target.value as "natural" | "juridica")
              }
            >
              <option value="natural">Persona natural</option>
              <option value="juridica">Persona jurídica</option>
            </SelectInput>
          )}
        </FormField>
      ) : null}

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

      {clientType === "natural" ? (
        <FormField
          label="Nombre completo"
          name="full_name"
          required
          error={state.errors?.full_name}
        >
          {(props) => <TextInput {...props} required defaultValue={client?.full_name ?? ""} maxLength={255} />}
        </FormField>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label="Razón social"
            name="legal_name"
            error={state.errors?.legal_name}
          >
            {(props) => (
              <TextInput {...props} defaultValue={client?.legal_name ?? ""} maxLength={255} />
            )}
          </FormField>
          <FormField
            label="Nombre comercial"
            name="commercial_name"
            error={state.errors?.commercial_name}
          >
            {(props) => (
              <TextInput {...props} defaultValue={client?.commercial_name ?? ""} maxLength={255} />
            )}
          </FormField>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Correo electrónico" name="email" error={state.errors?.email}>
          {(props) => (
            <TextInput
              {...props}
              type="email"
              defaultValue={client?.email ?? ""}
              maxLength={255}
            />
          )}
        </FormField>
        <FormField label="Teléfono" name="phone" error={state.errors?.phone}>
          {(props) => (
            <TextInput
              {...props}
              type="tel"
              defaultValue={client?.phone ?? ""}
              maxLength={50}
            />
          )}
        </FormField>
      </div>

      <FormField label="Dirección" name="address" error={state.errors?.address}>
        {(props) => (
          <TextInput {...props} defaultValue={client?.address ?? ""} maxLength={500} />
        )}
      </FormField>

      <FormField
        label="Notas internas"
        name="notes"
        error={state.errors?.notes}
        hint="No aparecen en el portal del cliente."
      >
        {(props) => (
          <TextArea {...props} rows={3} maxLength={2000} defaultValue={client?.notes ?? ""} />
        )}
      </FormField>

      <FormStatus state={state} />

      <div className="flex justify-end gap-2 pt-1">
        {legal ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => dialogRef.current?.close()}
          >
            Cancelar
          </Button>
        ) : null}
        <Button type="submit" variant="primary" pending={pending}>
          {editing ? "Guardar cambios" : "Registrar cliente"}
        </Button>
      </div>
    </form>
  );

  if (!legal) return body;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo cliente
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Registrar cliente"
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Registrar cliente</h2>
          </header>
          {body}
        </div>
      </dialog>
    </>
  );
}

/**
 * The confirmation that precedes a deactivation.
 *
 * A native `<dialog>` with a cancel and a confirm, and the confirm **not**
 * pre-focused. Pre-focusing the destructive button is how a muscle-memory Enter
 * destroys something; the safe button gets the initial focus here.
 */
export function DeactivateButton({
  action,
  clientId,
  clientName,
  variant = "danger",
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  clientId: string;
  clientName: string;
  /** `quiet` inside a table row, where the real decision happens in the dialog. */
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  /*
    Close once the server confirmed. Leaving it open over a record that is now
    inactive would leave the dialog offering to do again something already done.
  */
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
        aria-label="Desactivar cliente"
        className="w-[min(30rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="p-6">
          <h2 className="font-display text-xl">Desactivar a {clientName}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            El registro <strong>no se borra</strong>. Pasará a figurar como inactivo y todos
            sus expedientes, documentos y evidencias se conservan intactos, que
            es lo que un expediente abierto exige.
          </p>

          <div className="mt-5">
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <form action={formAction}>
              <input type="hidden" name="client_id" value={clientId} />
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
