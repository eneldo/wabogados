"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, SettingRecord } from "@/lib/types";

/**
 * Runtime settings writes.
 *
 * Server Actions, like every other admin write, so the token stays on the server
 * and the browser proxy allowlist does not grow. The permission check lives in
 * the API (`settings:write`); one here would be a check the caller could skip.
 *
 * **This is the one screen in the administration with a delete button.** The
 * project forbids removing legal records (ADR-051), and a system setting is not
 * one: it holds no case, no evidence and no signature. The backend deletes the
 * row for exactly that reason and keeps the previous value in `change_logs`, so
 * what the setting used to say remains recoverable. The rest of the surface
 * deactivates instead of deleting, and the button here says so before it asks.
 */

const SETTINGS = "/api/v1/admin/settings";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function optional(form: FormData, key: string): string | undefined {
  const value = text(form, key);
  return value === "" ? undefined : value;
}

/**
 * Turn a backend refusal into something a person can act on.
 *
 * A 422 from this module carries one sentence with no field attached, because the
 * rule that refused the write lives in the service (`validate_key`,
 * `reject_credential_keys`, the length cap) rather than in a schema, so there is
 * no `{loc, msg}` list to flatten. Guessing which input the sentence is about
 * would put it under the wrong control, so the message is shown on its own: it
 * already names the rule it broke.
 */
function describe(error: unknown): { message: string } {
  if (error instanceof ApiRequestError) {
    return { message: error.message };
  }
  return {
    message:
      error instanceof Error ? error.message : "No fue posible completar la operación.",
  };
}

/**
 * Read what the administrator typed back into the type the API stores.
 *
 * `system_settings` keeps text and decodes it as JSON on the way out, so a value
 * that looks like JSON is already a number, a boolean or an object once it comes
 * back. Sending the text as a string would store the same bytes in almost every
 * case and differ only in spacing and key order, but sending the parsed value is
 * what the field means: `30` is the number thirty, not thirty characters.
 *
 * A value that does not parse is sent as text, which is the only other thing the
 * column can hold.
 */
function parseValue(raw: string): unknown {
  if (raw === "") return "";
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return raw;
  }
}

export async function saveSetting(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const key = text(form, "key");

  if (!key) {
    return { status: "error", message: "El ajuste necesita una clave." };
  }

  const raw = typeof form.get("value") === "string" ? String(form.get("value")) : "";
  const body: Record<string, unknown> = {
    value: parseValue(raw),
    category: text(form, "category") || "general",
  };
  const description = optional(form, "description");
  if (description !== undefined) body.description = description;

  try {
    const saved = await apiFetch<SettingRecord>(
      // The key is the identifier of the row, so it travels in the path. It is
      // encoded rather than pasted: a key with a dot or a slash must not become
      // a different route.
      `${SETTINGS}/${encodeURIComponent(key)}`,
      { method: "PUT", body },
    );

    revalidatePath("/admin/configuracion");
    return {
      status: "ok",
      message: `Ajuste «${saved.key}» guardado.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function deleteSetting(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const key = text(form, "key");

  if (!key) {
    return { status: "error", message: "No se sabe qué ajuste eliminar." };
  }

  try {
    await apiFetch<void>(`${SETTINGS}/${encodeURIComponent(key)}`, { method: "DELETE" });
    revalidatePath("/admin/configuracion");
    return {
      status: "ok",
      message: `Ajuste «${key}» eliminado. Su valor anterior queda en el historial de cambios.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}
