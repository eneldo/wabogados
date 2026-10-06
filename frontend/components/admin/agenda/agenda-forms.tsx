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
import { FIRM_TIME_ZONE, FIRM_UTC_OFFSET_MINUTES } from "@/lib/format";
import type {
  ActionState,
  CalendarEventRecord,
  CaseOption,
  HearingRecord,
} from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

const EVENT_TYPES = [
  ["reunion", "Reunión"],
  ["vencimiento", "Vencimiento"],
  ["llamada", "Llamada"],
  ["cita", "Cita"],
  ["recordatorio", "Recordatorio"],
] as const;

const VISIBILITIES = [
  ["interna", "Interna"],
  ["equipo", "Equipo"],
  ["publicada", "Publicada al cliente"],
] as const;

const EVENT_STATUSES = [
  ["programada", "Programada"],
  ["realizada", "Realizada"],
  ["cancelada", "Cancelada"],
  ["aplazada", "Aplazada"],
] as const;

const HEARING_STATUSES = [
  ["programada", "Programada"],
  ["realizada", "Realizada"],
  ["aplazada", "Aplazada"],
  ["cancelada", "Cancelada"],
  ["suspendida", "Suspendida"],
] as const;

const STAGES = [
  ["primera_instancia", "Primera instancia"],
  ["apelacion", "Apelación"],
  ["ejecucion", "Ejecución"],
  ["previa", "Previa"],
  ["conciliacion", "Conciliación"],
  ["otra", "Otra"],
] as const;

function localDateTime(iso?: string | null): string {
  if (!iso) return "";
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: FIRM_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

function TimezoneOffsetInput() {
  return (
    <input
      type="hidden"
      name="timezone_offset"
      value={FIRM_UTC_OFFSET_MINUTES}
      readOnly
    />
  );
}

function DialogShell({
  dialogRef,
  eyebrow,
  title,
  children,
  width = "42rem",
}: {
  dialogRef: React.RefObject<HTMLDialogElement | null>;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
  width?: string;
}) {
  return (
    <dialog
      ref={dialogRef}
      aria-label={title}
      style={{ width: `min(${width}, calc(100vw - 2rem))` }}
      className="rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
    >
      <div className="max-h-[88vh] overflow-y-auto p-6">
        <header className="mb-5 border-b border-rule pb-4">
          <p className="label-rule">{eyebrow}</p>
          <h2 className="font-display mt-1 text-2xl text-ink">{title}</h2>
        </header>
        {children}
      </div>
    </dialog>
  );
}

function CaseAndLawyerFields({
  cases,
  lawyers,
  prefix,
  errors,
  caseId,
  lawyerId,
}: {
  cases: CaseOption[];
  lawyers: CaseOption[];
  prefix: string;
  errors?: Record<string, string>;
  caseId?: string;
  lawyerId?: string | null;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Expediente" name="case_id" idPrefix={prefix} required error={errors?.case_id}>
        {(props) => (
          <SelectInput {...props} required defaultValue={caseId ?? ""}>
            <option value="">Seleccione un expediente</option>
            {cases.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </SelectInput>
        )}
      </FormField>
      <FormField label="Abogado" name="lawyer_id" idPrefix={prefix} error={errors?.lawyer_id}>
        {(props) => (
          <SelectInput {...props} defaultValue={lawyerId ?? ""}>
            <option value="">Sin asignar</option>
            {lawyers.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </SelectInput>
        )}
      </FormField>
    </div>
  );
}

export function EventForm({
  action,
  cases,
  lawyers,
  event,
  variant = "primary",
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  cases: CaseOption[];
  lawyers: CaseOption[];
  event?: CalendarEventRecord;
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const editing = Boolean(event);
  const prefix = event ? `event-${event.id}` : "new-event";

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant={variant} onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name={editing ? "edit" : "add"} />
        {editing ? "Editar" : "Nuevo evento"}
      </Button>
      <DialogShell
        dialogRef={dialogRef}
        eyebrow={editing ? "Agenda" : "Nueva anotación"}
        title={editing ? `Editar ${event?.title}` : "Añadir evento"}
      >
        <form action={formAction} className="space-y-4">
          <TimezoneOffsetInput />
          {event ? <input type="hidden" name="event_id" value={event.id} /> : null}
          {!editing ? (
            <CaseAndLawyerFields cases={cases} lawyers={lawyers} prefix={prefix} errors={state.errors} />
          ) : (
            <input type="hidden" name="lawyer_id" value={event?.lawyer_id ?? ""} />
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {!editing ? (
              <FormField label="Tipo" name="event_type" idPrefix={prefix} required error={state.errors?.event_type}>
                {(props) => (
                  <SelectInput {...props} defaultValue="reunion">
                    {EVENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </SelectInput>
                )}
              </FormField>
            ) : null}
            <FormField label="Estado" name="status" idPrefix={prefix} error={state.errors?.status}>
              {(props) => (
                <SelectInput {...props} defaultValue={event?.status ?? "programada"}>
                  {EVENT_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </SelectInput>
              )}
            </FormField>
          </div>
          <FormField label="Título" name="title" idPrefix={prefix} required error={state.errors?.title}>
            {(props) => <TextInput {...props} required minLength={3} maxLength={255} defaultValue={event?.title ?? ""} />}
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Inicio" name="starts_at" idPrefix={prefix} required error={state.errors?.starts_at}>
              {(props) => <TextInput {...props} type="datetime-local" required defaultValue={localDateTime(event?.starts_at)} />}
            </FormField>
            <FormField label="Fin" name="ends_at" idPrefix={prefix} error={state.errors?.ends_at} hint="Vacío: una hora después.">
              {(props) => <TextInput {...props} type="datetime-local" defaultValue={localDateTime(event?.ends_at)} />}
            </FormField>
          </div>
          <CheckField name="all_day" label="Ocupa todo el día" defaultChecked={event?.all_day} />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Lugar" name="location" idPrefix={prefix} error={state.errors?.location}>
              {(props) => <TextInput {...props} maxLength={255} defaultValue={event?.location ?? ""} />}
            </FormField>
            <FormField label="Visibilidad" name="visibility" idPrefix={prefix} error={state.errors?.visibility}>
              {(props) => (
                <SelectInput {...props} defaultValue={event?.visibility ?? "interna"}>
                  {VISIBILITIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </SelectInput>
              )}
            </FormField>
          </div>
          <FormField label="Avisar antes" name="reminder_minutes" idPrefix={prefix} error={state.errors?.reminder_minutes} hint="Minutos. El recordatorio automático aún requiere worker.">
            {(props) => <TextInput {...props} type="number" min={0} max={43200} defaultValue={event?.reminder_minutes ?? ""} />}
          </FormField>
          <FormField label="Descripción" name="description" idPrefix={prefix} error={state.errors?.description}>
            {(props) => <TextArea {...props} rows={3} maxLength={4000} defaultValue={event?.description ?? ""} />}
          </FormField>
          <FormStatus state={state} />
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending}>{editing ? "Guardar cambios" : "Añadir a agenda"}</Button>
          </div>
        </form>
      </DialogShell>
    </>
  );
}

export function HearingForm({
  action,
  cases,
  lawyers,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  cases: CaseOption[];
  lawyers: CaseOption[];
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = "new-hearing";
  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  return (
    <>
      <Button type="button" variant="secondary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" /> Nueva audiencia
      </Button>
      <DialogShell dialogRef={dialogRef} eyebrow="Señalamiento" title="Programar audiencia" width="46rem">
        <form action={formAction} className="space-y-4">
          <TimezoneOffsetInput />
          <CaseAndLawyerFields cases={cases} lawyers={lawyers} prefix={prefix} errors={state.errors} />
          <FormField label="Título" name="title" idPrefix={prefix} required error={state.errors?.title}>
            {(props) => <TextInput {...props} required minLength={3} maxLength={255} />}
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Inicio" name="starts_at" idPrefix={prefix} required error={state.errors?.starts_at}>
              {(props) => <TextInput {...props} type="datetime-local" required />}
            </FormField>
            <FormField label="Fin" name="ends_at" idPrefix={prefix} error={state.errors?.ends_at} hint="Vacío: una hora después.">
              {(props) => <TextInput {...props} type="datetime-local" />}
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Etapa" name="procedural_stage" idPrefix={prefix} error={state.errors?.procedural_stage}>
              {(props) => <SelectInput {...props}>{STAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</SelectInput>}
            </FormField>
            <FormField label="Juzgado" name="court" idPrefix={prefix} error={state.errors?.court}>
              {(props) => <TextInput {...props} maxLength={200} />}
            </FormField>
            <FormField label="Sala" name="courtroom" idPrefix={prefix} error={state.errors?.courtroom}>
              {(props) => <TextInput {...props} maxLength={100} />}
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Juez" name="judge" idPrefix={prefix} error={state.errors?.judge}>
              {(props) => <TextInput {...props} maxLength={200} />}
            </FormField>
            <FormField label="Radicado" name="file_number" idPrefix={prefix} error={state.errors?.file_number}>
              {(props) => <TextInput {...props} maxLength={100} />}
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Notificada" name="notified_at" idPrefix={prefix} error={state.errors?.notified_at}>
              {(props) => <TextInput {...props} type="datetime-local" />}
            </FormField>
            <FormField label="Lugar" name="location" idPrefix={prefix} error={state.errors?.location}>
              {(props) => <TextInput {...props} maxLength={255} />}
            </FormField>
            <FormField label="Visibilidad" name="visibility" idPrefix={prefix} error={state.errors?.visibility}>
              {(props) => <SelectInput {...props}>{VISIBILITIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</SelectInput>}
            </FormField>
          </div>
          <FormField label="Descripción" name="description" idPrefix={prefix} error={state.errors?.description}>
            {(props) => <TextArea {...props} rows={3} maxLength={4000} />}
          </FormField>
          <FormStatus state={state} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending}>Programar audiencia</Button>
          </div>
        </form>
      </DialogShell>
    </>
  );
}

export function HearingUpdateButton({
  action,
  hearing,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  hearing: HearingRecord;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = `hearing-${hearing.id}`;
  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);
  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="edit" /> Registrar
      </Button>
      <DialogShell dialogRef={dialogRef} eyebrow="Acta de audiencia" title={`Registrar ${hearing.title}`}>
        <form action={formAction} className="space-y-4">
          <input type="hidden" name="hearing_id" value={hearing.id} />
          <TimezoneOffsetInput />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Estado" name="status" idPrefix={prefix} error={state.errors?.status}>
              {(props) => <SelectInput {...props} defaultValue={hearing.status}>{HEARING_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</SelectInput>}
            </FormField>
            <FormField label="Asistencia" name="attendance" idPrefix={prefix} error={state.errors?.attendance}>
              {(props) => <SelectInput {...props} defaultValue={hearing.attendance}><option value="pendiente">Pendiente</option><option value="presente">Presente</option><option value="ausente">Ausente</option><option value="justificada">Justificada</option></SelectInput>}
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Etapa" name="procedural_stage" idPrefix={prefix} error={state.errors?.procedural_stage}>
              {(props) => <SelectInput {...props} defaultValue={hearing.procedural_stage}>{STAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</SelectInput>}
            </FormField>
            <FormField label="Notificada" name="notified_at" idPrefix={prefix} error={state.errors?.notified_at}>
              {(props) => <TextInput {...props} type="datetime-local" defaultValue={localDateTime(hearing.notified_at)} />}
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Juzgado" name="court" idPrefix={prefix} error={state.errors?.court}>{(props) => <TextInput {...props} defaultValue={hearing.court ?? ""} />}</FormField>
            <FormField label="Sala" name="courtroom" idPrefix={prefix} error={state.errors?.courtroom}>{(props) => <TextInput {...props} defaultValue={hearing.courtroom ?? ""} />}</FormField>
            <FormField label="Juez" name="judge" idPrefix={prefix} error={state.errors?.judge}>{(props) => <TextInput {...props} defaultValue={hearing.judge ?? ""} />}</FormField>
          </div>
          <FormField label="Radicado" name="file_number" idPrefix={prefix} error={state.errors?.file_number}>{(props) => <TextInput {...props} defaultValue={hearing.file_number ?? ""} />}</FormField>
          <FormField label="Resultado" name="result" idPrefix={prefix} error={state.errors?.result} hint="Es obligatorio al marcar la audiencia como realizada.">
            {(props) => <TextArea {...props} rows={4} maxLength={4000} defaultValue={hearing.result ?? ""} />}
          </FormField>
          <FormStatus state={state} />
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button><Button type="submit" variant="primary" pending={pending}>Guardar acta</Button></div>
        </form>
      </DialogShell>
    </>
  );
}

export function RescheduleHearingButton({
  action,
  hearing,
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  hearing: HearingRecord;
}) {
  const [state, formAction, pending] = useActionState(action, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = `reschedule-${hearing.id}`;
  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);
  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="close" /> Reprogramar
      </Button>
      <DialogShell dialogRef={dialogRef} eyebrow="Trazabilidad" title={`Reprogramar ${hearing.title}`} width="34rem">
        <form action={formAction} className="space-y-4">
          <input type="hidden" name="hearing_id" value={hearing.id} />
          <TimezoneOffsetInput />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Nuevo inicio" name="starts_at" idPrefix={prefix} required error={state.errors?.starts_at}>{(props) => <TextInput {...props} type="datetime-local" required />}</FormField>
            <FormField label="Nuevo fin" name="ends_at" idPrefix={prefix} error={state.errors?.ends_at} hint="Vacío: una hora después.">{(props) => <TextInput {...props} type="datetime-local" />}</FormField>
          </div>
          <FormField label="Motivo" name="reason" idPrefix={prefix} required error={state.errors?.reason} hint="Queda registrado en el historial.">{(props) => <TextArea {...props} required minLength={3} maxLength={1000} rows={3} />}</FormField>
          <FormStatus state={state} />
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>Cancelar</Button><Button type="submit" variant="primary" pending={pending}>Confirmar nueva fecha</Button></div>
        </form>
      </DialogShell>
    </>
  );
}
