"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import {
  Button,
  FormField,
  FormStatus,
  SelectInput,
  TextInput,
} from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import type {
  ActionState,
  CaseOption,
  ParticipantOption,
} from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

export function NewConversationDialog({
  action,
  cases,
  clients,
  participants,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  cases: CaseOption[];
  clients: CaseOption[];
  participants: ParticipantOption[];
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const [type, setType] = useState<"interna" | "cliente">("interna");
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nueva conversación
      </Button>
      <dialog
        ref={dialogRef}
        aria-label="Abrir conversación"
        className="w-[min(44rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[88vh] overflow-y-auto p-6">
          <header className="mb-5 border-b border-rule pb-4">
            <p className="label-rule">Correspondencia</p>
            <h2 className="font-display mt-1 text-2xl text-ink">Abrir conversación</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-muted">
              Un hilo interno nunca aparece en el portal. Un hilo de cliente incorpora automáticamente su cuenta activa.
            </p>
          </header>
          <form action={formAction} className="space-y-5">
            <FormField label="Asunto" name="subject" idPrefix="new-conversation" required error={state.errors?.subject}>
              {(props) => <TextInput {...props} required minLength={3} maxLength={255} autoFocus />}
            </FormField>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Canal" name="conversation_type" idPrefix="new-conversation" required error={state.errors?.conversation_type}>
                {(props) => (
                  <SelectInput
                    {...props}
                    value={type}
                    onChange={(event) => setType(event.target.value as "interna" | "cliente")}
                  >
                    <option value="interna">Interna del despacho</option>
                    <option value="cliente">Visible al cliente</option>
                  </SelectInput>
                )}
              </FormField>
              <FormField label="Expediente" name="case_id" idPrefix="new-conversation" error={state.errors?.case_id} hint="Opcional. Si el canal es de cliente, debe pertenecer al cliente seleccionado.">
                {(props) => (
                  <SelectInput {...props} defaultValue="">
                    <option value="">Sin expediente</option>
                    {cases.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                  </SelectInput>
                )}
              </FormField>
            </div>
            {type === "cliente" ? (
              <FormField label="Cliente con acceso al portal" name="client_id" idPrefix="new-conversation" required error={state.errors?.client_id}>
                {(props) => (
                  <SelectInput {...props} required defaultValue="">
                    <option value="">Seleccione un cliente</option>
                    {clients.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                  </SelectInput>
                )}
              </FormField>
            ) : <input type="hidden" name="client_id" value="" />}

            <fieldset>
              <legend className="label-rule">Participantes del despacho</legend>
              <p className="mt-1 text-xs text-ink-faint">Usted se incorpora como propietario. Añada solo a quienes deben leer esta correspondencia.</p>
              <div className="mt-3 grid gap-2 rounded-card border border-rule bg-surface-sunk p-3 sm:grid-cols-2">
                {participants.length > 0 ? participants.map((participant) => (
                  <label key={participant.id} className="flex items-center gap-2.5 rounded-sm px-2 py-2 text-sm text-ink-soft hover:bg-surface">
                    <input type="checkbox" name="participant_ids" value={participant.id} className="size-4 accent-wax" />
                    <span>{participant.display_name}</span>
                  </label>
                )) : <p className="text-sm text-ink-muted">No hay otras cuentas de personal disponibles.</p>}
              </div>
            </fieldset>

            <FormStatus state={state} />
            <div className="flex justify-end gap-2 border-t border-rule pt-4">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button>
              <Button type="submit" variant="primary" pending={pending}>Abrir hilo</Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}
