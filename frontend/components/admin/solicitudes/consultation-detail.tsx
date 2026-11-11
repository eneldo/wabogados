"use client";

import { useRouter } from "next/navigation";
import { useActionState, useEffect, useRef } from "react";

import {
  Button,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
} from "@/components/admin/form-controls";
import { eraseConsultation, updateConsultation } from "@/features/solicitudes/actions";
import { formatDateTime } from "@/lib/format";
import type { ActionState, ConsultationRecord } from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

export function ConsultationDetail({
  item,
  canUpdate,
  canErase,
  closeHref,
}: {
  item: ConsultationRecord;
  canUpdate: boolean;
  canErase: boolean;
  closeHref: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const eraseRef = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  const [updateState, updateAction, updatePending] = useActionState(updateConsultation, IDLE);
  const [eraseState, eraseAction, erasePending] = useActionState(eraseConsultation, IDLE);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !eraseRef.current?.open) router.push(closeHref);
    };
    document.addEventListener("keydown", onKey);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [closeHref, router]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        aria-label="Cerrar la solicitud"
        onClick={() => router.push(closeHref)}
        className="absolute inset-0 bg-overlay/70"
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-label={`Solicitud de ${item.full_name}`}
        className="relative flex h-full w-full max-w-2xl flex-col overflow-y-auto border-l border-rule-strong bg-surface shadow-card outline-none"
      >
        <header className="border-b border-rule px-6 py-5">
          <p className="label-rule">Solicitud pública</p>
          <h2 className="font-display mt-1 text-2xl">{item.full_name}</h2>
          <p className="mt-2 text-sm text-ink-muted">
            {item.area} · recibida el {formatDateTime(item.created_at)}
          </p>
        </header>

        <div className="space-y-6 px-6 py-5">
          <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
            <Field label="Correo">
              <a className="break-all underline-offset-4 hover:text-wax hover:underline" href={`mailto:${item.email}`}>
                {item.email}
              </a>
            </Field>
            <Field label="Teléfono">
              <a className="hover:text-wax hover:underline" href={`tel:${item.phone}`}>{item.phone}</a>
            </Field>
            <Field label="Consentimiento">{formatDateTime(item.consent_at)}</Field>
            <Field label="Aviso de privacidad">Versión {item.privacy_notice_version}</Field>
            <Field label="Atendida">{item.handled_at ? formatDateTime(item.handled_at) : "Sin atender"}</Field>
            <Field label="Cliente vinculado">{item.client_id ?? "Sin vincular"}</Field>
          </dl>

          <section>
            <h3 className="label-rule">Consulta</h3>
            <p className="mt-2 whitespace-pre-wrap rounded-card border border-rule bg-surface-sunk px-4 py-3 text-sm leading-relaxed text-ink">
              {item.message}
            </p>
          </section>

          {canUpdate ? (
            <form action={updateAction} className="space-y-4 border-t border-rule pt-5">
              <input type="hidden" name="id" value={item.id} />
              <FormField label="Estado" name="status" idPrefix={`solicitud-${item.id}`} required>
                {(props) => (
                  <SelectInput {...props} defaultValue={item.status}>
                    <option value="nueva">Nueva</option>
                    <option value="en_revision">En revisión</option>
                    <option value="atendida">Atendida</option>
                    <option value="convertida">Convertida</option>
                    <option value="descartada">Descartada</option>
                  </SelectInput>
                )}
              </FormField>
              <FormField label="Notas internas" name="internal_notes" idPrefix={`solicitud-${item.id}`}>
                {(props) => (
                  <TextArea {...props} rows={5} maxLength={4000} defaultValue={item.internal_notes ?? ""} />
                )}
              </FormField>
              <FormStatus state={updateState} />
              <Button type="submit" variant="primary" pending={updatePending}>Guardar cambios</Button>
            </form>
          ) : item.internal_notes ? (
            <section>
              <h3 className="label-rule">Notas internas</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-muted">{item.internal_notes}</p>
            </section>
          ) : null}

          {canErase ? (
            <section className="border-t border-rule pt-5">
              <Button type="button" variant="danger" onClick={() => eraseRef.current?.showModal()}>
                Eliminar por solicitud del titular
              </Button>
              <dialog
                ref={eraseRef}
                aria-label={`Eliminar solicitud de ${item.full_name}`}
                className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
              >
                <div className="p-6">
                  <h2 className="font-display text-xl">¿Eliminar definitivamente esta solicitud?</h2>
                  <p className="mt-3 text-sm leading-relaxed text-ink-muted">
                    Esta acción solo corresponde a una petición de supresión del titular. El nombre, los datos de contacto, la consulta y las notas internas se eliminan definitivamente. La auditoría conserva que se realizó la operación, pero no copia este contenido.
                  </p>
                  <div className="mt-5"><FormStatus state={eraseState} /></div>
                  <div className="mt-6 flex justify-end gap-2">
                    <Button type="button" variant="ghost" onClick={() => eraseRef.current?.close()}>Cancelar</Button>
                    <form action={eraseAction}>
                      <input type="hidden" name="id" value={item.id} />
                      <Button type="submit" variant="danger" pending={erasePending}>Sí, eliminar</Button>
                    </form>
                  </div>
                </div>
              </dialog>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="label-rule">{label}</dt>
      <dd className="mt-1 break-words text-ink">{children}</dd>
    </div>
  );
}
