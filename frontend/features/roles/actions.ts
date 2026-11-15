"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, RoleRecord } from "@/lib/types";

const ROLES = "/api/v1/admin/roles";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function list(form: FormData, key: string): string[] {
  return form
    .getAll(key)
    .filter((value): value is string => typeof value === "string")
    .map((value) => value.trim())
    .filter(Boolean);
}

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

function revalidateRoles() {
  revalidatePath("/admin/roles");
  revalidatePath("/admin/usuarios");
  revalidatePath("/admin/seguridad");
}

export async function createRole(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const created = await apiFetch<RoleRecord>(ROLES, {
      method: "POST",
      body: {
        name: text(form, "name"),
        description: text(form, "description") || null,
        permission_names: list(form, "permission_names"),
      },
    });
    revalidateRoles();
    return { status: "ok", message: `Rol «${created.name}» creado.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateRole(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const roleId = text(form, "role_id");
  if (!roleId) {
    return { status: "error", message: "No se sabe qué rol modificar." };
  }

  try {
    const updated = await apiFetch<RoleRecord>(`${ROLES}/${roleId}`, {
      method: "PATCH",
      body: {
        name: text(form, "name") || undefined,
        description: text(form, "description"),
        permission_names: list(form, "permission_names"),
      },
    });
    revalidateRoles();
    return { status: "ok", message: `Rol «${updated.name}» actualizado.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function deleteRole(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const roleId = text(form, "role_id");
  if (!roleId) {
    return { status: "error", message: "No se sabe qué rol eliminar." };
  }

  try {
    await apiFetch<void>(`${ROLES}/${roleId}`, { method: "DELETE" });
    revalidateRoles();
    return { status: "ok", message: "Rol eliminado." };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}
