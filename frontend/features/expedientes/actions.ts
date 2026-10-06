"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, CaseRecord } from "@/lib/types";

/**
 * Case writes.
 *
 * **There is no delete, and that is the design.** `PROJECT_RULES.md` forbids
 * physically deleting legal records, and a case is the definition of one. The
 * lifecycle the API offers is `abierto → en_tramitacion → suspendido →
 * cerrado → archivado`, plus `POST /cases/{id}/close`. So the button says
 * "Cerrar" and takes a closing note, and there is no path in this module that
 * removes a case.
 *
 * Same shape as the client and lawyer modules: Server Actions, permission
 * enforced by the API, validation errors flattened to the field that caused them.
 */

const CASES = "/api/v1/cases";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function optional(form: FormData, key: string): string | undefined {
  const value = text(form, key);
  return value === "" ? undefined : value;
}

function describe(error: unknown): { message: string; errors?: Record<string, string> } {
  if (!(error instanceof ApiRequestError)) {
    return {
      message:
        error instanceof Error
          ? error.message
          : "No fue posible completar la operación.",
    };
  }

  const details = error.details as
    | { errors?: Array<{ loc?: Array<string | number>; msg?: string }> }
    | undefined;
  const entries = details?.errors;

  if (Array.isArray(entries) && entries.length > 0) {
    const errors: Record<string, string> = {};
    for (const entry of entries) {
      const field = [...(entry.loc ?? [])].reverse().find(
        (part): part is string => typeof part === "string" && part !== "body",
      );
      if (field && entry.msg) {
        errors[field] = entry.msg.replace(/^Value error,\s*/, "");
      }
    }
    if (Object.keys(errors).length > 0) {
      return { message: "Revise los campos marcados.", errors };
    }
  }

  return { message: error.message };
}

/** Shared body builder. `includeRequired` differs between create and update. */
function caseBody(form: FormData, creating: boolean): Record<string, unknown> {
  const body: Record<string, unknown> = {
    title: text(form, "title"),
    process_type: text(form, "process_type"),
    priority: text(form, "priority") || "normal",
    responsible_lawyer_id: optional(form, "responsible_lawyer_id") ?? null,
    legal_area_id: optional(form, "legal_area_id") ?? null,
    jurisdiction: optional(form, "jurisdiction") ?? null,
    court: optional(form, "court") ?? null,
    file_number: optional(form, "file_number") ?? null,
    description: optional(form, "description") ?? null,
    notes: optional(form, "notes") ?? null,
    // Decimal fields arrive as strings; an empty input means "not quantified",
    // which is different from zero and is sent as null on purpose.
    amount: optional(form, "amount") ?? null,
  };

  if (creating) {
    body.client_id = text(form, "client_id");
    // `opened_at` only exists on create. Changing the opening date of a case that
    // already happened is not an edit, it is a different case.
    body.opened_at = text(form, "opened_at") || undefined;
  } else {
    body.client_id = optional(form, "client_id") ?? null;
  }

  return body;
}

export async function createCase(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const created = await apiFetch<CaseRecord>(CASES, {
      method: "POST",
      body: caseBody(form, true),
    });

    revalidatePath("/admin/expedientes");
    revalidatePath(`/admin/expedientes/${created.id}`);
    return {
      status: "ok",
      message: `Expediente ${created.case_number} abierto.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateCase(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const caseId = text(form, "case_id");
  if (!caseId) {
    return { status: "error", message: "No se sabe qué expediente modificar." };
  }

  try {
    const updated = await apiFetch<CaseRecord>(`${CASES}/${caseId}`, {
      method: "PATCH",
      body: caseBody(form, false),
    });

    revalidatePath("/admin/expedientes");
    revalidatePath(`/admin/expedientes/${caseId}`);
    return {
      status: "ok",
      message: `Cambios guardados en ${updated.case_number}.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/**
 * Close a case.
 *
 * This is the end of the lifecycle, not the end of the record. The dialog says
 * so, because "Cerrar" on a screen full of files reads as "delete" to anyone
 * who has not read the rule.
 */
export async function closeCase(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const caseId = text(form, "case_id");
  if (!caseId) {
    return { status: "error", message: "No se sabe qué expediente cerrar." };
  }

  try {
    const closed = await apiFetch<CaseRecord>(`${CASES}/${caseId}/close`, {
      method: "POST",
      body: {
        closed_at: text(form, "closed_at") || undefined,
        notes: optional(form, "notes") ?? null,
      },
    });

    revalidatePath("/admin/expedientes");
    revalidatePath(`/admin/expedientes/${caseId}`);
    return {
      status: "ok",
      message: `Expediente ${closed.case_number} cerrado. Su historial se conserva íntegro.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/** Add a collaborator. The responsible lawyer is a separate column on the case. */
export async function assignLawyer(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const caseId = text(form, "case_id");
  const lawyerId = text(form, "lawyer_id");
  if (!caseId || !lawyerId) {
    return { status: "error", message: "Elija el abogado que se incorporará." };
  }

  try {
    await apiFetch(`${CASES}/${caseId}/lawyers`, {
      method: "POST",
      body: { lawyer_id: lawyerId, role: text(form, "role") || "colaborador" },
    });
    revalidatePath(`/admin/expedientes/${caseId}`);
    return { status: "ok", message: "Abogado incorporado al expediente." };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/** Add a party: claimant, defendant, counterparty or third party. */
export async function addParty(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const caseId = text(form, "case_id");
  if (!caseId) {
    return { status: "error", message: "No se sabe a qué expediente añadir la parte." };
  }

  try {
    await apiFetch(`${CASES}/${caseId}/parties`, {
      method: "POST",
      body: {
        name: text(form, "name"),
        party_role: text(form, "party_role") || "tercero",
        client_id: optional(form, "client_id") ?? null,
        document_type: optional(form, "document_type") ?? null,
        document_number: optional(form, "document_number") ?? null,
        notes: optional(form, "notes") ?? null,
        // A party that is not one of the firm's clients is external by
        // definition; the checkbox says so out loud instead of guessing.
        is_external: form.get("is_external") === "on",
      },
    });
    revalidatePath(`/admin/expedientes/${caseId}`);
    return { status: "ok", message: "Parte añadida al expediente." };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}