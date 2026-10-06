"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type {
  ActionState,
  CalendarEventRecord,
  HearingRecord,
} from "@/lib/types";

const CALENDAR = "/api/v1/calendar";
const HEARINGS = "/api/v1/hearings";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function optional(form: FormData, key: string): string | null {
  return text(form, key) || null;
}

function integer(form: FormData, key: string): number | null {
  const value = text(form, key);
  if (!value) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
}

/** Convert the browser's `datetime-local` value with its own UTC offset. */
function instant(form: FormData, key: string): string | undefined {
  const value = text(form, key);
  if (!value) return undefined;
  const offset = Number(text(form, "timezone_offset") || "0");
  const localAsUtc = Date.parse(`${value}:00Z`);
  if (Number.isNaN(localAsUtc) || !Number.isFinite(offset)) return value;
  return new Date(localAsUtc + offset * 60_000).toISOString();
}

function describe(error: unknown): { message: string; errors?: Record<string, string> } {
  if (!(error instanceof ApiRequestError)) {
    return {
      message: error instanceof Error ? error.message : "No fue posible guardar la agenda.",
    };
  }
  const details = error.details as
    | { errors?: Array<{ loc?: Array<string | number>; msg?: string }> }
    | undefined;
  const errors: Record<string, string> = {};
  for (const entry of details?.errors ?? []) {
    const field = [...(entry.loc ?? [])].reverse().find(
      (part): part is string => typeof part === "string" && part !== "body",
    );
    if (field && entry.msg) errors[field] = entry.msg.replace(/^Value error,\s*/, "");
  }
  return Object.keys(errors).length > 0
    ? { message: "Revise los campos marcados.", errors }
    : { message: error.message };
}

function refresh(caseId?: string): void {
  revalidatePath("/admin/agenda");
  revalidatePath("/admin");
  if (caseId) revalidatePath(`/admin/expedientes/${caseId}`);
}

function eventBody(form: FormData, creating: boolean): Record<string, unknown> {
  const body: Record<string, unknown> = {
    title: text(form, "title"),
    description: optional(form, "description"),
    starts_at: instant(form, "starts_at"),
    ends_at: instant(form, "ends_at") ?? null,
    all_day: form.get("all_day") === "on",
    location: optional(form, "location"),
    lawyer_id: optional(form, "lawyer_id"),
    visibility: text(form, "visibility") || "interna",
    status: text(form, "status") || "programada",
    reminder_minutes: integer(form, "reminder_minutes"),
  };
  if (creating) {
    body.case_id = text(form, "case_id");
    body.event_type = text(form, "event_type");
  }
  return body;
}

export async function createEvent(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const event = await apiFetch<CalendarEventRecord>(CALENDAR, {
      method: "POST",
      body: eventBody(form, true),
    });
    refresh(event.case_id);
    return { status: "ok", message: `«${event.title}» añadido a la agenda.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateEvent(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const eventId = text(form, "event_id");
  if (!eventId) return { status: "error", message: "No se sabe qué evento modificar." };
  try {
    const event = await apiFetch<CalendarEventRecord>(`${CALENDAR}/${eventId}`, {
      method: "PATCH",
      body: eventBody(form, false),
    });
    refresh(event.case_id);
    return { status: "ok", message: `Cambios guardados en «${event.title}».` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function createHearing(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const hearing = await apiFetch<HearingRecord>(HEARINGS, {
      method: "POST",
      body: {
        case_id: text(form, "case_id"),
        title: text(form, "title"),
        starts_at: instant(form, "starts_at"),
        ends_at: instant(form, "ends_at") ?? null,
        lawyer_id: optional(form, "lawyer_id"),
        court: optional(form, "court"),
        courtroom: optional(form, "courtroom"),
        judge: optional(form, "judge"),
        procedural_stage: text(form, "procedural_stage") || "primera_instancia",
        file_number: optional(form, "file_number"),
        notified_at: instant(form, "notified_at") ?? null,
        visibility: text(form, "visibility") || "interna",
        location: optional(form, "location"),
        description: optional(form, "description"),
      },
    });
    refresh(hearing.case_id);
    return { status: "ok", message: `Audiencia «${hearing.title}» programada.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateHearing(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const hearingId = text(form, "hearing_id");
  if (!hearingId) return { status: "error", message: "No se sabe qué audiencia modificar." };
  try {
    const hearing = await apiFetch<HearingRecord>(`${HEARINGS}/${hearingId}`, {
      method: "PATCH",
      body: {
        court: optional(form, "court"),
        courtroom: optional(form, "courtroom"),
        judge: optional(form, "judge"),
        procedural_stage: text(form, "procedural_stage"),
        file_number: optional(form, "file_number"),
        notified_at: instant(form, "notified_at") ?? null,
        attendance: text(form, "attendance"),
        result: optional(form, "result"),
        status: text(form, "status"),
      },
    });
    refresh(hearing.case_id);
    return { status: "ok", message: `Audiencia «${hearing.title}» actualizada.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function rescheduleHearing(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const hearingId = text(form, "hearing_id");
  if (!hearingId) return { status: "error", message: "No se sabe qué audiencia reprogramar." };
  try {
    const hearing = await apiFetch<HearingRecord>(`${HEARINGS}/${hearingId}/reschedule`, {
      method: "POST",
      body: {
        starts_at: instant(form, "starts_at"),
        ends_at: instant(form, "ends_at") ?? null,
        reason: text(form, "reason"),
      },
    });
    refresh(hearing.case_id);
    return { status: "ok", message: `Audiencia «${hearing.title}» reprogramada.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}
