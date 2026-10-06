"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, AdminUserRecord } from "@/lib/types";

/**
 * User administration writes.
 *
 * Same rules as every other admin feature: Server Actions, never the browser
 * proxy, because the token stays on the server and nothing is added to the
 * public surface of the API. The permission check lives in the API — a check
 * here would be one the caller could skip.
 *
 * **There is no delete.** `DELETE /admin/users/{id}` marks the row inactive and
 * keeps it, and the buttons say so: a user directory that could lose the author
 * of every audit entry it exists to show would be the wrong tool for the job.
 */

const USERS = "/api/v1/admin/users";

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
    .filter((value): value is string => typeof value === "string")
    .map((value) => value.trim())
    .filter(Boolean);
}

/**
 * Turn a backend refusal into something a person can act on.
 *
 * Pydantic answers 422 with `details.errors`, a list of `{loc, msg}` where `loc`
 * ends in the field's name; flattening it to `{field: message}` is what lets the
 * form put the sentence under the input it belongs to.
 */
function describe(error: unknown): { message: string; errors?: Record<string, string> } {
  if (!(error instanceof ApiRequestError)) {
    return {
      message:
        error instanceof Error ? error.message : "No fue posible completar la operación.",
    };
  }

  const details = error.details as
    | { errors?: Array<{ loc?: Array<string | number>; msg?: string }> }
    | undefined;
  const entries = details?.errors;

  if (Array.isArray(entries) && entries.length > 0) {
    const errors: Record<string, string> = {};
    for (const entry of entries) {
      const field = [...(entry.loc ?? [])]
        .reverse()
        .find((part): part is string => typeof part === "string" && part !== "body");
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

export async function createUser(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const created = await apiFetch<AdminUserRecord>(USERS, {
      method: "POST",
      body: {
        email: text(form, "email"),
        full_name: optional(form, "full_name") ?? null,
        password: text(form, "password"),
        is_superuser: form.get("is_superuser") === "on",
        role_names: list(form, "role_names"),
      },
    });

    revalidatePath("/admin/seguridad");
    return {
      status: "ok",
      message: `Usuario «${created.email}» dado de alta. Ya puede iniciar sesión.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateUser(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const userId = text(form, "user_id");
  if (!userId) {
    return { status: "error", message: "No se sabe qué usuario modificar." };
  }

  /*
    Only the fields this dialog shows. State is deliberately absent: the account
    is activated and deactivated by its own action, each with its own wording,
    so no edit form can silently lock somebody out.
  */
  try {
    const updated = await apiFetch<AdminUserRecord>(`${USERS}/${userId}`, {
      method: "PATCH",
      body: {
        email: optional(form, "email"),
        full_name: optional(form, "full_name") ?? null,
        is_verified: form.get("is_verified") === "on",
        is_superuser: form.get("is_superuser") === "on",
      },
    });

    revalidatePath("/admin/seguridad");
    return {
      status: "ok",
      message: `Cambios guardados en «${updated.email}».`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function deactivateUser(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const userId = text(form, "user_id");
  if (!userId) {
    return { status: "error", message: "No se sabe qué usuario desactivar." };
  }

  try {
    await apiFetch<AdminUserRecord>(`${USERS}/${userId}`, { method: "DELETE" });
    revalidatePath("/admin/seguridad");
    return {
      status: "ok",
      message: "Usuario desactivado. Su historial se conserva.",
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function reactivateUser(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const userId = text(form, "user_id");
  if (!userId) {
    return { status: "error", message: "No se sabe qué usuario reactivar." };
  }

  try {
    await apiFetch<AdminUserRecord>(`${USERS}/${userId}`, {
      method: "PATCH",
      body: { is_active: true },
    });
    revalidatePath("/admin/seguridad");
    return { status: "ok", message: "Cuenta reactivada. Vuelve a poder iniciar sesión." };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/**
 * Give a user the roles that are checked and remove the rest.
 *
 * The API assigns and revokes one role at a time, which is the right shape for
 * a single button but the wrong shape for a form of checkboxes: sending a
 * request per box means the screen flashes once per role and a failure halfway
 * leaves an account in a state nobody chose. So the diff is computed here
 * against what the server currently holds — read fresh, not from a hidden
 * field — and only what actually changes is sent.
 */
export async function setUserRoles(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const userId = text(form, "user_id");
  if (!userId) {
    return { status: "error", message: "No se sabe a quién asignar roles." };
  }

  try {
    const current = await apiFetch<AdminUserRecord>(`${USERS}/${userId}`);
    const wanted = list(form, "role_name");
    const toAdd = wanted.filter((role) => !current.roles.includes(role));
    const toRemove = current.roles.filter((role) => !wanted.includes(role));

    for (const role of toAdd) {
      await apiFetch<AdminUserRecord>(`${USERS}/${userId}/roles`, {
        method: "POST",
        body: { role_name: role },
      });
    }
    for (const role of toRemove) {
      await apiFetch<AdminUserRecord>(
        `${USERS}/${userId}/roles/${encodeURIComponent(role)}`,
        { method: "DELETE" },
      );
    }

    revalidatePath("/admin/seguridad");
    if (toAdd.length === 0 && toRemove.length === 0) {
      return { status: "ok", message: "Los roles ya estaban como estaban." };
    }

    const parts: string[] = [];
    if (toAdd.length > 0) parts.push(`asignados: ${toAdd.join(", ")}`);
    if (toRemove.length > 0) parts.push(`retirados: ${toRemove.join(", ")}`);
    return { status: "ok", message: `Roles actualizados — ${parts.join("; ")}.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}
