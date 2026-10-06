"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  Button,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import type { ButtonVariant } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { issueInvoice, registerPayment, voidInvoice } from "@/features/facturacion/actions";
import { formatMoneyCOP } from "@/lib/format";
import type { ActionState, InvoiceRecord } from "@/lib/types";

/**
 * What can be done to an invoice from the listing.
 *
 * Three controls rather than one menu, because they differ in what they need.
 * Issuing is a one-click decision with no fields. Voiding is destructive and
 * demands a reason, because an unexplained void cannot be explained to an
 * accountant. Recording a payment is a small form. And they sit behind different
 * permissions, so a lawyer sees the first and the third and an administrator sees
 * all three.
 */

const IDLE: ActionState = { status: "idle" };

export function IssueInvoiceButton({
  invoice,
  variant = "quiet",
}: {
  invoice: InvoiceRecord;
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(issueInvoice, IDLE);

  if (invoice.status !== "borrador") return null;

  return (
    <>
      <form action={formAction} className="inline">
        <input type="hidden" name="id" value={invoice.id} />
        <Button type="submit" variant={variant} pending={pending}>
          Emitir
        </Button>
      </form>
      {state.status === "error" ? (
        <span role="alert" className="mt-1 block text-xs text-wax-deep">
          {state.message}
        </span>
      ) : null}
      <span className="sr-only" aria-live="polite">
        {state.status === "ok" ? state.message : ""}
      </span>
    </>
  );
}

/**
 * Cancelling a number that already exists.
 *
 * The dialog says the row is **not** deleted and the number is kept, because
 * "anular" reads as "borrar" to anyone who has not been told otherwise, and the
 * reason field is mandatory: an unexplained void is the one thing in this module
 * that could not be audited six months later.
 */
export function VoidInvoiceButton({
  invoice,
  variant = "quiet",
}: {
  invoice: InvoiceRecord;
  variant?: ButtonVariant;
}) {
  const [state, formAction, pending] = useActionState(voidInvoice, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);

  if (invoice.status === "anulada") return null;

  return (
    <>
      <Button type="button" variant={variant} onClick={() => ref.current?.showModal()}>
        <ActionIcon name="deactivate" />
        Anular
      </Button>

      <dialog
        ref={ref}
        aria-label={`Anular factura ${invoice.number}`}
        className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <h2 className="font-display text-xl">Anular la factura {invoice.number}?</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            La factura <strong>no se borra</strong> y el número{" "}
            <strong>se conserva</strong>: es lo que permite explicar dentro de seis
            meses por qué ese número ya no cuenta. Los pagos ya registrados quedan
            como están.
          </p>

          <form action={formAction} className="mt-4 space-y-4">
            <input type="hidden" name="id" value={invoice.id} />
            <FormField
              label="Motivo"
              name="reason"
              idPrefix={`anular-${invoice.number.toLowerCase()}`}
              required
              hint="Queda escrito en el historial y no se puede cambiar después."
            >
              {(props) => <TextArea {...props} required minLength={5} rows={3} />}
            </FormField>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
                Cancelar
              </Button>
              <Button type="submit" variant="danger" pending={pending}>
                <ActionIcon name="deactivate" />
                Sí, anular
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

export function RegisterPaymentButton({ invoice }: { invoice: InvoiceRecord }) {
  const [state, formAction, pending] = useActionState(registerPayment, IDLE);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);

  // A draft takes no payment and a voided one takes none either; offering the
  // button would be offering something the API is going to refuse.
  if (invoice.status === "borrador" || invoice.status === "anulada") return null;

  const prefix = `pago-${invoice.number.toLowerCase()}`;

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => ref.current?.showModal()}>
        Registrar pago
      </Button>

      <dialog
        ref={ref}
        aria-label={`Registrar pago de la factura ${invoice.number}`}
        className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-4">
            <p className="label-rule">Cobro</p>
            <h2 className="font-display mt-1 text-xl">{invoice.number}</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Total {formatMoneyCOP(invoice.total)} · pagado {formatMoneyCOP(invoice.paid_amount)} ·
              saldo {formatMoneyCOP(invoice.balance)}
            </p>
          </header>

          <form action={formAction} className="space-y-4">
            <input type="hidden" name="id" value={invoice.id} />

            <FormField
              label="Importe"
              name="amount"
              idPrefix={prefix}
              required
              hint="Lo que entró hoy. Un pago parcial deja la factura emitida."
            >
              {(props) => (
                <TextInput
                  {...props}
                  required
                  inputMode="decimal"
                  defaultValue={invoice.balance !== "0" ? invoice.balance : ""}
                />
              )}
            </FormField>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Medio" name="method" idPrefix={prefix}>
                {(props) => (
                  <SelectInput {...props} defaultValue="transferencia">
                    <option value="transferencia">Transferencia</option>
                    <option value="efectivo">Efectivo</option>
                    <option value="tarjeta">Tarjeta</option>
                    <option value="cheque">Cheque</option>
                  </SelectInput>
                )}
              </FormField>

              <FormField label="Fecha" name="paid_at" idPrefix={prefix}>
                {(props) => <TextInput {...props} type="date" />}
              </FormField>
            </div>

            <FormField
              label="Referencia"
              name="reference"
              idPrefix={prefix}
              hint="Comprobante, número de cheque: lo que lo prueba después."
            >
              {(props) => <TextInput {...props} maxLength={120} />}
            </FormField>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Registrar
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}
