"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, MediaRecord } from "@/lib/types";

/**
 * Multimedia library writes (MASTER_PROMPT V4).
 *
 * Server Actions like every other admin write, so the token stays on the server
 * and the browser proxy allowlist does not grow. The permission check lives in the
 * API (`media:*`); one here would be a check the caller could skip.
 *
 * **Registering and uploading are two calls, on purpose.** A row may exist with no
 * file — a librarian files the recording and it arrives later — and the screen has
 * to be able to show that state rather than treat it as a failure. A single action
 * carrying both would have to invent what to do with the row when the upload fails
 * halfway, and the row is the part that matters.
 */

const MEDIA = "/api/v1/media";

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
 * The library's refusals are sentences about the file itself ("no se reconoce el
 * tipo del archivo por su contenido"), not field errors, so they are shown whole.
 * Inventing a per-field message here would put a sentence under an input it does
 * not describe.
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

export async function createMedia(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const title = text(form, "title");
  if (!title) {
    return { status: "error", message: "El recurso necesita un título." };
  }

  const caseId = optional(form, "case_id");
  const description = optional(form, "description");
  const tags = optional(form, "tags");
  const filename = optional(form, "original_filename");

  try {
    const created = await apiFetch<MediaRecord>(MEDIA, {
      method: "POST",
      body: {
        title,
        ...(description ? { description } : {}),
        ...(tags ? { tags } : {}),
        ...(caseId ? { case_id: caseId } : {}),
        ...(filename ? { original_filename: filename } : {}),
        confidentiality: text(form, "confidentiality") || "interno",
      },
    });

    // An optional file rides along when the dialog was filled in with one. The
    // record exists either way, which is the whole reason the two calls are split.
    const file = form.get("file");
    if (file instanceof File && file.size > 0) {
      try {
        const withFile = await uploadFile(created.id, file, filename);
        revalidatePath("/admin/multimedia");
        return {
          status: "ok",
          message: `«${withFile.title}» registrado con su archivo.`,
        };
      } catch (error) {
        // The row is real; the file is not. Saying so is the only honest message,
        // and it tells the person exactly what is left to do.
        revalidatePath("/admin/multimedia");
        return {
          status: "error",
          message: `El recurso «${created.title}» quedó registrado, pero el archivo no se pudo cargar: ${describe(error).message}`,
        };
      }
    }

    revalidatePath("/admin/multimedia");
    return {
      status: "ok",
      message: `Recurso «${created.title}» registrado. Puede cargar el archivo cuando quiera.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateMedia(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  if (!id) return { status: "error", message: "No se sabe qué recurso editar." };

  try {
    const updated = await apiFetch<MediaRecord>(`${MEDIA}/${id}`, {
      method: "PATCH",
      body: {
        title: text(form, "title"),
        description: optional(form, "description") ?? null,
        tags: optional(form, "tags") ?? null,
        confidentiality: text(form, "confidentiality") || "interno",
        status: text(form, "status") || "activo",
        case_id: optional(form, "case_id") ?? null,
      },
    });

    revalidatePath("/admin/multimedia");
    return { status: "ok", message: `Cambios guardados en «${updated.title}».` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/**
 * Attach or replace the file of an existing resource.
 *
 * The bytes go as `multipart/form-data` because the backend detects the type from
 * the content: a JSON base64 blob would work and would put a video in memory twice.
 */
export async function uploadFile(
  id: string,
  file: File,
  filename?: string,
): Promise<MediaRecord> {
  const form = new FormData();
  form.set("file", file, filename ?? file.name);
  return apiFetch<MediaRecord>(`${MEDIA}/${id}/content`, {
    method: "PUT",
    body: form,
  });
}

export async function uploadMediaFile(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  const file = form.get("file");

  if (!id) return { status: "error", message: "No se sabe a qué recurso añadir." };
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: "Elija un archivo para cargar." };
  }

  try {
    const updated = await uploadFile(id, file, optional(form, "original_filename"));
    revalidatePath("/admin/multimedia");
    return {
      status: "ok",
      message: `Archivo cargado en «${updated.title}».`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

/**
 * Take a resource out of the library. Nothing is deleted (ADR-051).
 *
 * The file is left in storage and the row keeps its history, which is what makes
 * the action reversible; the confirmation in the dialog says so before it asks.
 */
export async function deactivateMedia(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  if (!id) return { status: "error", message: "No se sabe qué desactivar." };

  try {
    const updated = await apiFetch<MediaRecord>(`${MEDIA}/${id}`, { method: "DELETE" });
    revalidatePath("/admin/multimedia");
    return {
      status: "ok",
      message: `«${updated.title}» sale de la biblioteca. Su archivo y su historial se conservan.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function reactivateMedia(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  if (!id) return { status: "error", message: "No se sabe qué reactivar." };

  try {
    const updated = await apiFetch<MediaRecord>(`${MEDIA}/${id}/reactivate`, {
      method: "POST",
    });
    revalidatePath("/admin/multimedia");
    return {
      status: "ok",
      message: `«${updated.title}» vuelve a la biblioteca con su archivo.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}
