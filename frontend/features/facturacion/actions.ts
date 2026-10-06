"use server";

import { revalidatePath } from "next/cache";

import { ApiRequestError, apiFetch } from "@/lib/api";
import { formatMoneyCOP } from "@/lib/format";
import type { ActionState, InvoiceRecord, PaymentRecord } from "@/lib/types";

/**
 * Billing writes (MASTER_PROMPT V3).
 *
 * **No action sends a total.** Each one posts concepts and the server does the
 * arithmetic. That is not a stylistic choice: a Server Action is a public HTTP
 * endpoint, so a field named `total` in one of these payloads would be a number
 * the browser could choose, and the browser is not the party that owes the money.
 *
 * Issuing and voiding are separate actions behind separate permissions. Preparing
 * a bill is front-desk work; deciding what leaves the firm, and cancelling a number
 * that already exists, are not.
 */

const BILLING = "/api/v1/billing";

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function optional(form: FormData, key: string): string | undefined {
  const value = text(form, key);
  return value === "" ? undefined : value;
}

/**
 * Read the concept rows out of the form.
 *
 * The rows arrive as parallel arrays rather than as indexed names, because a form
 * that adds and removes concepts cannot know its own indices in advance. An empty
 * row is dropped rather than sent: a concept with no description is a blank line
 * on the bill, and blank lines on a bill are a question the client will ask.
 */
function readLines(form: FormData): { description: string; quantity: string; unit_price: string }[] {
  const descriptions = form.getAll("line_description");
  const quantities = form.getAll("line_quantity");
  const prices = form.getAll("line_unit_price");

  const lines: { description: string; quantity: string; unit_price: string }[] = [];
  descriptions.forEach((description, index) => {
    const clean = typeof description === "string" ? description.trim() : "";
    if (!clean) return;
    lines.push({
      description: clean,
      quantity: String(quantities[index] ?? "1").trim() || "1",
      unit_price: String(prices[index] ?? "").trim() || "0",
    });
  });
  return lines;
}

function describe(error: unknown): { message: string } {
  if (error instanceof ApiRequestError) {
    return { message: error.message };
  }
  return {
    message:
      error instanceof Error ? error.message : "No fue posible completar la operación.",
  };
}

export async function createInvoice(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const clientId = text(form, "client_id");
  if (!clientId) {
    return { status: "error", message: "Elija el cliente al que se factura." };
  }

  const lines = readLines(form);
  if (lines.length === 0) {
    return {
      status: "error",
      message: "Una factura necesita al menos un concepto.",
    };
  }

  const caseId = optional(form, "case_id");
  const notes = optional(form, "notes");
  const dueAt = optional(form, "due_at");

  try {
    const created = await apiFetch<InvoiceRecord>(`${BILLING}/invoices`, {
      method: "POST",
      body: {
        client_id: clientId,
        // The rate is sent as the string the field holds. Sending 0.19 and 0.1900
        // is the same number, and the string is what the column can hold exactly.
        tax_rate: text(form, "tax_rate") || "0",
        ...(caseId ? { case_id: caseId } : {}),
        ...(notes ? { notes } : {}),
        ...(dueAt ? { due_at: dueAt } : {}),
        lines,
      },
    });

    revalidatePath("/admin/facturacion");
    return {
      status: "ok",
      message: `Factura ${created.number} creada como borrador.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function updateInvoice(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  if (!id) return { status: "error", message: "No se sabe qué factura editar." };

  const notes = optional(form, "notes");
  const dueAt = optional(form, "due_at");

  try {
    const updated = await apiFetch<InvoiceRecord>(`${BILLING}/invoices/${id}`, {
      method: "PATCH",
      body: {
        notes: notes ?? null,
        tax_rate: text(form, "tax_rate") || "0",
        due_at: dueAt ?? null,
        case_id: optional(form, "case_id") ?? null,
        // Sent always: the concept list is replaced as a whole, and omitting it
        // would keep the old rows while the header said otherwise.
        lines: readLines(form),
      },
    });

    revalidatePath("/admin/facturacion");
    return { status: "ok", message: `Factura ${updated.number} actualizada.` };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function issueInvoice(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  if (!id) return { status: "error", message: "No se sabe qué factura emitir." };

  try {
    const issued = await apiFetch<InvoiceRecord>(`${BILLING}/invoices/${id}/issue`, {
      method: "POST",
      body: {},
    });
    revalidatePath("/admin/facturacion");
    return {
      status: "ok",
      message: `Factura ${issued.number} emitida. Ya no admite cambios en sus conceptos.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function voidInvoice(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  const reason = text(form, "reason");
  if (!id) return { status: "error", message: "No se sabe qué factura anular." };
  if (reason.length < 5) {
    return {
      status: "error",
      message: "Una anulación necesita un motivo que explique el número emitido.",
    };
  }

  try {
    const voided = await apiFetch<InvoiceRecord>(`${BILLING}/invoices/${id}/void`, {
      method: "POST",
      body: { reason },
    });
    revalidatePath("/admin/facturacion");
    return {
      status: "ok",
      message: `Factura ${voided.number} anulada. El número se conserva.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}

export async function registerPayment(
  _previous: ActionState,
  form: FormData,
): Promise<ActionState> {
  const id = text(form, "id");
  const amount = text(form, "amount");
  if (!id) return { status: "error", message: "No se sabe a qué factura aplicar el pago." };

  try {
    const payment = await apiFetch<PaymentRecord>(`${BILLING}/invoices/${id}/payments`, {
      method: "POST",
      body: {
        amount: amount || "0",
        method: text(form, "method") || "transferencia",
        paid_at: text(form, "paid_at") || undefined,
        reference: optional(form, "reference") ?? null,
        notes: optional(form, "notes") ?? null,
      },
    });

    revalidatePath("/admin/facturacion");
    return {
      status: "ok",
      message: `Pago de ${formatMoneyCOP(payment.amount)} registrado. El estado de la factura lo decide el saldo, no este formulario.`,
    };
  } catch (error) {
    return { status: "error", ...describe(error) };
  }
}
