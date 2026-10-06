"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, ConversationSummary } from "@/lib/types";

const CONVERSATIONS = "/api/v1/conversations";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function optional(form: FormData, key: string): string | null {
  return text(form, key) || null;
}

function describe(error: unknown): ActionState {
  if (!(error instanceof ApiRequestError)) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "No fue posible guardar la conversación.",
    };
  }
  const details = error.details as
    | { errors?: Array<{ loc?: Array<string | number>; msg?: string }> }
    | Array<{ loc?: Array<string | number>; msg?: string }>
    | undefined;
  const entries = Array.isArray(details) ? details : details?.errors ?? [];
  const errors: Record<string, string> = {};
  for (const entry of entries) {
    const field = [...(entry.loc ?? [])].reverse().find(
      (part): part is string => typeof part === "string" && part !== "body",
    );
    if (field && entry.msg) errors[field] = entry.msg.replace(/^Value error,\s*/, "");
  }
  return Object.keys(errors).length > 0
    ? { status: "error", message: "Revise los campos marcados.", errors }
    : { status: "error", message: error.message };
}

function refresh(): void {
  revalidatePath("/admin/mensajes");
  revalidatePath("/admin");
  revalidatePath("/portal/mensajes");
}

export async function createConversation(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  try {
    const conversation = await apiFetch<ConversationSummary>(CONVERSATIONS, {
      method: "POST",
      body: {
        subject: text(form, "subject"),
        conversation_type: text(form, "conversation_type") || "interna",
        case_id: optional(form, "case_id"),
        client_id: optional(form, "client_id"),
        participant_ids: form
          .getAll("participant_ids")
          .filter((value): value is string => typeof value === "string"),
      },
    });
    refresh();
    return { status: "ok", message: `Conversación «${conversation.subject}» abierta.` };
  } catch (error) {
    return describe(error);
  }
}

export async function closeConversation(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const conversationId = text(form, "conversation_id");
  if (!conversationId) {
    return { status: "error", message: "No se sabe qué conversación cerrar." };
  }
  try {
    const conversation = await apiFetch<ConversationSummary>(
      `${CONVERSATIONS}/${conversationId}`,
      { method: "PATCH", body: { status: "cerrado" } },
    );
    refresh();
    return { status: "ok", message: `Conversación «${conversation.subject}» cerrada.` };
  } catch (error) {
    return describe(error);
  }
}
