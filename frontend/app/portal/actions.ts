"use server";

import { revalidatePath } from "next/cache";

import { apiFetch, ApiNotAuthenticated, ApiRequestError } from "@/lib/api";
import type { ActionState } from "@/lib/types";

function toMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof ApiNotAuthenticated) return "Su sesión no está activa. Vuelva a ingresar.";
  if (error instanceof Error) return error.message;
  return "No fue posible completar la acción.";
}

export async function respondClientRequestAction(
  requestId: string,
  _state: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const responseText = String(formData.get("response_text") ?? "").trim();
  if (!responseText) {
    return { status: "error", message: "Escriba una respuesta antes de enviar." };
  }
  try {
    await apiFetch(`/api/v1/client-requests/${requestId}/respond`, {
      method: "POST",
      body: { response_text: responseText },
    });
    revalidatePath("/portal");
    revalidatePath("/portal/casos/[caseId]", "page");
    return { status: "ok", message: "Respuesta enviada al despacho." };
  } catch (error) {
    return { status: "error", message: toMessage(error) };
  }
}
