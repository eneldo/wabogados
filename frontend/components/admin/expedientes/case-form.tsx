"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  Button,
  CheckField,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import type { ButtonVariant } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import type { ActionState, CaseOption, CaseRecord } from "@/lib/types";

/**
 * The case form.
 *
 * `opened_at` appears only when creating. It is absent from `CaseUpdate`, and
 * changing the opening date of a case that already happened is not an edit — it
 * is a different case.
 */

const IDLE: ActionState = { status: "idle" };

const PROCESS_TYPES = [
  { value: "civil", label: "Civil" },
  { value: "penal", label: "Penal" },
  { value: "laboral", label: "Laboral" },
  { value: "administrativo", label: "Administrativo" },
  { value: "comercial", label: "Comercial" },
  { value: "familia", label: "Familia" },
  { value: "tributario", label: "Tributario" },
  { value: "arbitraje", label: "Arbitraje" },
  { value: "otro", label: "Otro" },
];

const PRIORITIES = [
  { value: "baja", label: "Baja" },
  { value: "normal", label: "Normal" },
  { value: "alta", label: "Alta" },
  { value: "urgente", label: "Urgente" },
];

const PARTY_ROLES = [
  { value: "demandante", label: "Demandante" },
  { value: "demandado", label: "Demandado" },
  { value: "contraparte", label: "Contraparte" },
  { value: "tercero", label: "Tercero" },
];

export function CaseForm({
  action,
  record,
  clients,
  lawyers,
  areas,
  legal = false,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  record?: CaseRecord;
  clients: CaseOption[];
  lawyers: CaseOption[];
  areas: CaseOption[];
  legal?: boolean;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const editing = Boolean(record);

  useEffect(() => {
    if (state.status === "ok" && legal && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [state, legal]);

  const body = (
    <form action={formAction} className="space-y-4">
      {record ? <input type="hidden" name="case_id" value={record.id} /> : null}

      <FormField
        label="Título del expediente"
        name="title"
        required
        error={state.errors?.title}
        hint="Entre cinco y 255 caracteres. Es lo que se lee en el listado."
      >
        {(props) => (
          <TextInput
            {...props}
            required
            minLength={5}
            maxLength={255}
            defaultValue={record?.title ?? ""}
          />
        )}
      </FormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="Cliente"
          name="client_id"
          required
          error={state.errors?.client_id}
        >
          {(props) => (
            <SelectInput {...props} defaultValue={record?.client_id ?? ""}>
              <option value="">Seleccione un cliente</option>
              {clients.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </FormField>

        <FormField
          label="Tipo de proceso"
          name="process_type"
          required
          error={state.errors?.process_type}
        >
          {(props) => (
            <SelectInput {...props} defaultValue={record?.process_type ?? "civil"}>
              {PROCESS_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </FormField>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="Abogado responsable"
          name="responsible_lawyer_id"
          error={state.errors?.responsible_lawyer_id}
          hint="Quien responde del expediente."
        >
          {(props) => (
            <SelectInput
              {...props}
              defaultValue={record?.responsible_lawyer_id ?? ""}
            >
              <option value="">Sin asignar</option>
              {lawyers.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </FormField>

        <FormField
          label="Área jurídica"
          name="legal_area_id"
          error={state.errors?.legal_area_id}
        >
          {(props) => (
            <SelectInput {...props} defaultValue={record?.legal_area_id ?? ""}>
              <option value="">Sin clasificar</option>
              {areas.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </FormField>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Prioridad" name="priority" error={state.errors?.priority}>
          {(props) => (
            <SelectInput {...props} defaultValue={record?.priority ?? "normal"}>
              {PRIORITIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectInput>
          )}
        </FormField>

        {!editing ? (
          <FormField
            label="Fecha de apertura"
            name="opened_at"
            error={state.errors?.opened_at}
            hint="Por defecto, hoy. Después no se modifica."
          >
            {(props) => <TextInput {...props} type="date" />}
          </FormField>
        ) : (
          <FormField label="Abierto el" name="opened_at_readonly">
            {(props) => (
              <TextInput
                {...props}
                readOnly
                value={record?.opened_at ?? ""}
                className="bg-surface-sunk text-ink-muted"
              />
            )}
          </FormField>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="Juzgado / jurisdicción"
          name="court"
          error={state.errors?.court}
        >
          {(props) => (
            <TextInput
              {...props}
              maxLength={200}
              defaultValue={record?.court ?? ""}
            />
          )}
        </FormField>
        <FormField
          label="Número de proceso"
          name="file_number"
          error={state.errors?.file_number}
          hint="El número que da el juzgado, no el interno."
        >
          {(props) => (
            <TextInput
              {...props}
              maxLength={100}
              defaultValue={record?.file_number ?? ""}
            />
          )}
        </FormField>
      </div>

      <FormField
        label="Jurisdicción"
        name="jurisdiction"
        error={state.errors?.jurisdiction}
      >
        {(props) => (
          <TextInput
            {...props}
            maxLength={150}
            defaultValue={record?.jurisdiction ?? ""}
          />
        )}
      </FormField>

      <FormField
        label="Cuantía"
        name="amount"
        error={state.errors?.amount}
        hint="Vacío significa «sin cuantificar», que no es lo mismo que cero."
      >
        {(props) => (
          <TextInput
            {...props}
            type="number"
            step="0.01"
            min="0"
            inputMode="decimal"
            defaultValue={record?.amount ?? ""}
          />
        )}
      </FormField>

      <FormField
        label="Descripción"
        name="description"
        error={state.errors?.description}
      >
        {(props) => (
          <TextArea {...props} rows={3} maxLength={4000} defaultValue={record?.description ?? ""} />
        )}
      </FormField>

      <FormField
        label="Notas internas"
        name="notes"
        error={state.errors?.notes}
        hint="No aparecen en el portal del cliente."
      >
        {(props) => (
          <TextArea {...props} rows={3} maxLength={4000} defaultValue={record?.notes ?? ""} />
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
          {editing ? "Guardar cambios" : "Abrir expediente"}
        </Button>
      </div>
    </form>
  );

  if (!legal) return body;

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nuevo expediente
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Abrir expediente"
        className="w-[min(44rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Abrir expediente</h2>
          </header>
          {body}
        </div>
      </dialog>
    </>
  );
}

/**
 * Close a case.
 *
 * The dialog states the two things that matter: the case stops being active, and
 * nothing is deleted. The closing note is not decoration either — it is the last
 * thing written in the file before it stops moving.
 */
export function CloseCaseButton({
  action,
  caseId,
  caseNumber,
  triggerLabel = "Cerrar expediente",
  idPrefix = "close",
  variant = "secondary",
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  caseId: string;
  caseNumber: string;
  /** Shorter label inside a table row; the dialog heading stays the full one. */
  triggerLabel?: string;
  /**
   * Qualifies the dialog's field ids.
   *
   * On the listing this dialog is rendered once per open case, so a fixed
   * prefix would repeat every id as many times as there are open cases, and a
   * repeated id points each label at the first dialog's control.
   */
  idPrefix?: string;
  /** `quiet` inside a table row, where the link next to it is the real target. */
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
        <ActionIcon name="close" />
        {triggerLabel}
      </Button>

      <dialog
        ref={ref}
        aria-label="Cerrar expediente"
        className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <h2 className="font-display text-xl">Cerrar {caseNumber}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            El expediente deja de estar activo y aparece como cerrado.{" "}
            <strong>No se borra nada</strong>: documentos, evidencias, actuaciones
            y audiencias se conservan y siguen consultables.
          </p>

          <div className="mt-5 space-y-4">
            <FormField label="Fecha de cierre" name="closed_at" idPrefix={idPrefix}>
              {(props) => <TextInput {...props} type="date" />}
            </FormField>
            <FormField
              label="Nota de cierre"
              name="notes"
              idPrefix={idPrefix}
              hint="Por qué termina el asunto."
            >
              {(props) => <TextArea {...props} rows={3} maxLength={4000} />}
            </FormField>
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" pending={pending}>
              <ActionIcon name="close" />
              Cerrar expediente
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/** Add a collaborator who is not the responsible lawyer. */
export function AssignLawyerButton({
  action,
  caseId,
  lawyers,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  caseId: string;
  lawyers: CaseOption[];
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant="secondary" onClick={() => ref.current?.showModal()}>
        Incorporar abogado
      </Button>

      <dialog
        ref={ref}
        aria-label="Incorporar abogado al expediente"
        className="w-[min(28rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <h2 className="font-display text-xl">Incorporar abogado</h2>

          <div className="mt-5 space-y-4">
            <FormField label="Abogado" name="lawyer_id" idPrefix="lawyer" required>
              {(props) => (
                <SelectInput {...props} required>
                  <option value="">Seleccione un abogado</option>
                  {lawyers.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </FormField>
            <FormField
              label="Papel en el expediente"
              name="role"
              idPrefix="lawyer"
              hint="Colaborador por defecto."
            >
              {(props) => (
                <TextInput {...props} defaultValue="colaborador" maxLength={50} />
              )}
            </FormField>
            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" pending={pending}>
              Incorporar
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/** Add a party: claimant, defendant, counterparty or third party. */
export function AddPartyButton({
  action,
  caseId,
  clients,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  caseId: string;
  clients: CaseOption[];
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant="secondary" onClick={() => ref.current?.showModal()}>
        Añadir parte
      </Button>

      <dialog
        ref={ref}
        aria-label="Añadir parte al expediente"
        className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <h2 className="font-display text-xl">Añadir parte</h2>

          <div className="mt-5 space-y-4">
            <FormField
              label="Nombre"
              name="name"
              idPrefix="party"
              required
              error={state.errors?.name}
            >
              {(props) => <TextInput {...props} required minLength={2} maxLength={255} />}
            </FormField>

            <FormField label="Papel procesal" name="party_role" idPrefix="party" required>
              {(props) => (
                <SelectInput {...props} defaultValue="tercero">
                  {PARTY_ROLES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </FormField>

            <CheckField
              name="is_external"
              defaultChecked
              label="Es una parte externa"
              hint="Marcarlo si no es cliente de la firma."
            />

            <FormField
              label="Cliente vinculado"
              name="client_id"
              idPrefix="party"
              hint="Solo si esta parte es cliente de la firma."
            >
              {(props) => (
                <SelectInput {...props}>
                  <option value="">Ninguno</option>
                  {clients.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </FormField>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Tipo de documento" name="document_type" idPrefix="party">
                {(props) => (
                  <SelectInput {...props} defaultValue="">
                    <option value="">Sin especificar</option>
                    <option value="DNI">DNI</option>
                    <option value="CC">Cédula</option>
                    <option value="NIF">NIF</option>
                    <option value="RUC">RUC</option>
                    <option value="CE">Cédula de extranjero</option>
                    <option value="PASSPORT">Pasaporte</option>
                    <option value="OTROS">Otros</option>
                  </SelectInput>
                )}
              </FormField>
              <FormField label="Número de documento" name="document_number" idPrefix="party">
                {(props) => <TextInput {...props} maxLength={50} />}
              </FormField>
            </div>

            <FormField label="Notas" name="notes" idPrefix="party">
              {(props) => <TextArea {...props} rows={2} maxLength={2000} />}
            </FormField>

            <FormStatus state={state} />
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" pending={pending}>
              Añadir parte
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}
