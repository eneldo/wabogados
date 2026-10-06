"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, ClientRecord } from "@/lib/types";

/**
 * Client writes.
 *
 * **Server Actions, not the browser proxy.** `app/api/proxy/[...path]` keeps an
 * allowlist of paths a client component may reach, and it exists so that
 * interactive pieces never hold a token. Admin CRUD is exactly the case that
 * allowlist was built to keep out: an action runs on the server with the
 * session cookie, so nothing is added to the public surface of the API and no
 * credential reaches the browser.
 *
 * The permission check is **not** here. It is in the API, and it has to be:
 * a check in this file would be a check the caller could skip, and the only
 * place that cannot be skipped is the server that owns the data.
 */

const CLIENTS = "/api/v1/clients";

/** Trim a form field into `string`, collapsing the whitespace people paste. */
function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

/** Optional field: empty means "not sent", not "empty string". */
function optional(form: FormData, key: string): string | undefined {
  const value = text(form, key);
  return value === "" ? undefined : value;
}

function asObject(form: FormData): Record<string, unknown> {
  return Object.fromEntries(form.entries()) as Record<string, unknown>;
}

/**
 * Turn a backend refusal into something a person can act on.
 *
 * Pydantic answers 422 with `details.errors`, a list of `{loc, msg}` where `loc`
 * ends in the field's name. Flattening it to `{field: message}` is what lets the
 * form put the sentence under the input it belongs to instead of in a banner
 * that names nothing.
 */
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

export async function createClient(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const created = await apiFetch<ClientRecord>(CLIENTS, {
      method: "POST",
      body: {
        ...asObject(form),
        client_type: text(form, "client_type"),
        full_name: optional(form, "full_name") ?? null,
        legal_name: optional(form, "legal_name") ?? null,
        commercial_name: optional(form, "commercial_name") ?? null,
        email: optional(form, "email") ?? null,
        phone: optional(form, "phone") ?? null,
        address: optional(form, "address") ?? null,
        notes: optional(form, "notes") ?? null,
      },
    });

    revalidatePath("/admin/clientes");
    return {
      status: "ok",
      message: `Cliente «${created.display_name}» registrado.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateClient(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const clientId = text(form, "client_id");
  if (!clientId) {
    return { status: "error", message: "No se sabe qué cliente modificar." };
  }

  /*
    Only the mutable fields are sent.
    `document_type` and `document_number` identify a client and are absent from
    `ClientUpdate` on purpose: changing a client's identity document is not an
    edit, it is a different person, and it has to go through a different decision.
  */
  try {
    const updated = await apiFetch<ClientRecord>(`${CLIENTS}/${clientId}`, {
      method: "PATCH",
      body: {
        full_name: optional(form, "full_name") ?? null,
        legal_name: optional(form, "legal_name") ?? null,
        commercial_name: optional(form, "commercial_name") ?? null,
        email: optional(form, "email") ?? null,
        phone: optional(form, "phone") ?? null,
        address: optional(form, "address") ?? null,
        notes: optional(form, "notes") ?? null,
      },
    });

    revalidatePath("/admin/clientes");
    revalidatePath(`/admin/clientes/${clientId}`);
    return {
      status: "ok",
      message: `Cambios guardados en «${updated.display_name}».`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/**
 * Deactivate a client.
 *
 * Named `deactivate` rather than `delete`, because that is what the API does:
 * `DELETE /clients/{id}` marks the row inactive and keeps it. The button says
 * "Desactivar" so nobody reads it as a promise that the record is gone.
 *
 * Both paths are revalidated. Revalidating only the list leaves the **detail**
 * screen showing a record as active immediately after it was deactivated, which
 * is the one page the person is looking at when they press the button.
 */
export async function deactivateClient(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const clientId = text(form, "client_id");
  if (!clientId) {
    return { status: "error", message: "No se sabe qué cliente desactivar." };
  }

  try {
    await apiFetch<void>(`${CLIENTS}/${clientId}`, { method: "DELETE" });
    revalidatePath("/admin/clientes");
    revalidatePath(`/admin/clientes/${clientId}`);
    return { status: "ok", message: "Cliente desactivado. Su historial se conserva." };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}