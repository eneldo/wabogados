"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiRequestError, apiFetch } from "@/lib/api";
import type { ActionState, ConsultationRecord, ConsultationStatus } from "@/lib/types";

const CONSULTATIONS = "/api/v1/consultations";
const STATUSES: ConsultationStatus[] = [
  "nueva",
  "en_revision",
  "atendida",
  "convertida",
  "descartada",
];

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function describe(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : "No fue posible completar la operación.";
}

export async function updateConsultation(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  const status = text(form, "status") as ConsultationStatus;

  if (!id) return { status: "error", message: "No se sabe qué solicitud actualizar." };
  if (!STATUSES.includes(status)) {
    return { status: "error", message: "Seleccione un estado válido." };
  }

  try {
    const saved = await apiFetch<ConsultationRecord>(
      `${CONSULTATIONS}/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        body: {
          status,
          internal_notes: text(form, "internal_notes"),
        },
      },
    );
    revalidatePath("/admin/solicitudes");
    return {
      status: "ok",
      message: `Solicitud de ${saved.full_name} actualizada.`,
    };
  } catch (error) {
    return { status: "error", message: describe(error) };
  }
}

export async function eraseConsultation(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  if (!id) return { status: "error", message: "No se sabe qué solicitud eliminar." };

  try {
    await apiFetch<void>(`${CONSULTATIONS}/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    revalidatePath("/admin/solicitudes");
  } catch (error) {
    return { status: "error", message: describe(error) };
  }

  redirect("/admin/solicitudes");
}
