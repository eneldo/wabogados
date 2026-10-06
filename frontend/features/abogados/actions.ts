"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, LawyerRecord } from "@/lib/types";

/**
 * Lawyer writes.
 *
 * Same shape as the client actions, with two differences that come from the
 * schemas rather than from preference:
 *
 * - `specialties` and `legal_area_ids` are **lists**. A form can only submit
 *   repeated fields, so both are read with `getAll()` and sent as arrays. This
 *   is exactly the case the API rejects a plain string for.
 * - `document_type` and `document_number` are sent on create and left out of
 *   update, for the same reason as in the client module: they identify the
 *   person and are not in `LawyerUpdate`.
 */

const LAWYERS = "/api/v1/lawyers";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function optional(form: FormData, key: string): string | undefined {
  const value = text(form, key);
  return value === "" ? undefined : value;
}

function list(form: FormData, key: string): string[] {
  return form
    .getAll(key)
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean);
}

/**
 * Specialties arrive as one textarea with newlines in it.
 *
 * `getAll` would return a single element containing embedded line breaks, and the
 * API would store that whole block as one specialty. Splitting here is what makes
 * "one per line" in the form mean one entry per line in the database.
 */
function lines(form: FormData, key: string): string[] {
  return form
    .getAll(key)
    .flatMap((value) =>
      typeof value === "string" ? value.split(/\r?\n/) : [],
    )
    .map((value) => value.trim())
    .filter(Boolean);
}

function describe(error: unknown): { message: string; errors?: Record<string, string> } {
  if (!(error instanceof ApiRequestError)) {
    return {
      message:
        error instanceof Error
          ? error.message
          : "No fue posible completar la operaciÃ³n.",
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

export async function createLawyer(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const created = await apiFetch<LawyerRecord>(LAWYERS, {
      method: "POST",
      body: {
        full_name: text(form, "full_name"),
        document_type: text(form, "document_type"),
        document_number: text(form, "document_number"),
        professional_card: optional(form, "professional_card") ?? null,
        email: optional(form, "email") ?? null,
        phone: optional(form, "phone") ?? null,
        status: text(form, "status") || "activo",
        photo_url: optional(form, "photo_url") ?? null,
        specialties: lines(form, "specialties"),
        legal_area_ids: list(form, "legal_area_ids"),
      },
    });

    revalidatePath("/admin/abogados");
    return { status: "ok", message: `Abogado Â«${created.full_name}Â» registrado.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateLawyer(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const lawyerId = text(form, "lawyer_id");
  if (!lawyerId) {
    return { status: "error", message: "No se sabe quÃ© abogado modificar." };
  }

  try {
    const updated = await apiFetch<LawyerRecord>(`${LAWYERS}/${lawyerId}`, {
      method: "PATCH",
      body: {
        full_name: text(form, "full_name"),
        professional_card: optional(form, "professional_card") ?? null,
        email: optional(form, "email") ?? null,
        phone: optional(form, "phone") ?? null,
        status: text(form, "status") || "activo",
        photo_url: optional(form, "photo_url") ?? null,
        specialties: lines(form, "specialties"),
        legal_area_ids: list(form, "legal_area_ids"),
      },
    });

    revalidatePath("/admin/abogados");
    revalidatePath(`/admin/abogados/${lawyerId}`);
    return { status: "ok", message: `Cambios guardados en Â«${updated.full_name}Â».` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/** Soft delete, exactly like clients. The button must say "Desactivar". */
export async function deactivateLawyer(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const lawyerId = text(form, "lawyer_id");
  if (!lawyerId) {
    return { status: "error", message: "No se sabe quÃ© abogado desactivar." };
  }

  try {
    await apiFetch<void>(`${LAWYERS}/${lawyerId}`, { method: "DELETE" });
    revalidatePath("/admin/abogados");
    revalidatePath(`/admin/abogados/${lawyerId}`);
    return {
      status: "ok",
      message: "Abogado desactivado. Conserva sus expedientes y su historial.",
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}