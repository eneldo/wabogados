"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import {
  Button,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { createInvoice, updateInvoice } from "@/features/facturacion/actions";
import { formatMoneyCOP } from "@/lib/format";
import type { ActionState, InvoiceRecord } from "@/lib/types";

/**
 * The invoice form: the header and its concepts.
 *
 * **There is no total field, and its absence is the feature.** The person filling
 * this in cannot state what the client owes — the server computes it from the
 * concepts, to the cent. A field that only recomputes itself is a field that can
 * be typed over.
 *
 * Concepts are added and removed in the browser because the count is not known in
 * advance. Each row submits three parallel arrays rather than indexed names, and
 * the server drops the empty ones — a blank line on a bill is a question the
 * client will ask.
 */

const IDLE: ActionState = { status: "idle" };

type Option = { id: string; label: string };

export function InvoiceForm({
  canAct,
  clients,
  cases,
}: {
  canAct: boolean;
  clients: Option[];
  cases: Option[];
}) {
  const [state, formAction, pending] = useActionState(createInvoice, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [lines, setLines] = useState([
    { description: "", quantity: "1", unit_price: "" },
  ]);
  const [handled, setHandled] = useState(state.status);

  /*
    Reset the concept rows when the submission succeeds, and do it **during render**
    rather than in an effect: setting state from an effect is the pattern React
    warns about, and this one needs no effect at all. The rows are component state,
    not form fields, so `formRef.reset()` does not clear them — without this the
    next «Nueva factura» opens holding the concepts of the last one.
  */
  if (state.status !== handled) {
    setHandled(state.status);
    if (state.status === "ok") {
      setLines([{ description: "", quantity: "1", unit_price: "" }]);
    }
  }

  // Closing the dialog is a DOM operation and belongs in an effect.
  useEffect(() => {
    if (state.status !== "ok") return;
    if (dialogRef.current?.open) dialogRef.current.close();
    formRef.current?.reset();
  }, [state]);

  if (!canAct) return null;

  const addLine = () =>
    setLines((current) => [...current, { description: "", quantity: "1", unit_price: "" }]);
  const removeLine = (index: number) =>
    setLines((current) => current.filter((_, i) => i !== index));
  const changeLine = (index: number, field: string, value: string) =>
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, [field]: value } : line)),
    );

  return (
    <>
      <Button type="button" variant="primary" onClick={() => dialogRef.current?.showModal()}>
        <ActionIcon name="add" />
        Nueva factura
      </Button>

      <dialog
        ref={dialogRef}
        aria-label="Registrar factura"
        className="w-[min(44rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Alta</p>
            <h2 className="font-display mt-1 text-2xl">Registrar factura</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Nace como borrador. Los importes los calcula el servidor a partir de
              los conceptos; aquí no se escribe ningún total.
            </p>
          </header>

          <form ref={formRef} action={formAction} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Cliente" name="client_id" idPrefix="crear-factura" required>
                {(props) => (
                  <SelectInput {...props} required defaultValue="">
                    <option value="">Seleccione un cliente</option>
                    {clients.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.label}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </FormField>

              <FormField
                label="Expediente"
                name="case_id"
                idPrefix="crear-factura"
                hint="Opcional: una factura de honorarios puede no tener expediente."
              >
                {(props) => (
                  <SelectInput {...props} defaultValue="">
                    <option value="">Sin expediente</option>
                    {cases.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.label}
                      </option>
                    ))}
                  </SelectInput>
                )}
              </FormField>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Vencimiento"
                name="due_at"
                idPrefix="crear-factura"
                hint="Cuándo se cobra. Es lo que ordena el informe de antigüedad."
              >
                {(props) => <TextInput {...props} type="date" />}
              </FormField>

              <FormField
                label="Impuesto"
                name="tax_rate"
                idPrefix="crear-factura"
                hint="Tasa como fracción: 0.1900 es 19 %. Por defecto 0, es decir, sin impuesto aplicado."
              >
                {(props) => (
                  <TextInput
                    {...props}
                    inputMode="decimal"
                    defaultValue="0"
                    placeholder="0.0000"
                  />
                )}
              </FormField>
            </div>

            <fieldset>
              <legend className="label-rule">Conceptos</legend>
              <div className="mt-2 space-y-2">
                {lines.map((line, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="hidden"
                      name="line_quantity"
                      value={line.quantity}
                      readOnly
                    />
                    <input type="hidden" name="line_unit_price" value={line.unit_price} readOnly />
                    <input
                      name="line_description"
                      value={line.description}
                      onChange={(event) => changeLine(index, "description", event.target.value)}
                      placeholder="Concepto"
                      aria-label={`Concepto ${index + 1}`}
                      className="w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
                    />
                    <input
                      value={line.unit_price}
                      onChange={(event) => changeLine(index, "unit_price", event.target.value)}
                      inputMode="decimal"
                      aria-label={`Precio unitario del concepto ${index + 1}`}
                      placeholder="Precio"
                      className="w-28 rounded-card border border-rule-strong bg-surface px-3 py-2 text-right font-mono text-sm text-ink outline-none focus:border-wax"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => removeLine(index)}
                      aria-label={`Quitar el concepto ${index + 1}`}
                    >
                      ×
                    </Button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addLine}
                className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-wax"
              >
                Añadir concepto
              </button>
            </fieldset>

            <FormField label="Notas" name="notes" idPrefix="crear-factura">
              {(props) => <TextArea {...props} rows={2} maxLength={2000} />}
            </FormField>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Crear borrador
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}

export function EditInvoiceButton({
  invoice,
  canAct,
  cases,
}: {
  invoice: InvoiceRecord;
  canAct: boolean;
  cases: Option[];
}) {
  const [state, formAction, pending] = useActionState(updateInvoice, IDLE);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const prefix = `editar-factura-${invoice.number.toLowerCase()}`;

  const [lines, setLines] = useState(
    invoice.lines.length > 0
      ? invoice.lines.map((line) => ({
          description: line.description,
          quantity: line.quantity,
          unit_price: line.unit_price,
        }))
      : [{ description: "", quantity: "1", unit_price: "" }],
  );

  useEffect(() => {
    if (state.status === "ok" && dialogRef.current?.open) dialogRef.current.close();
  }, [state]);

  if (!canAct) return null;

  const addLine = () =>
    setLines((current) => [...current, { description: "", quantity: "1", unit_price: "" }]);
  const changeLine = (index: number, field: string, value: string) =>
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, [field]: value } : line)),
    );

  return (
    <>
      <Button type="button" variant="quiet" onClick={() => dialogRef.current?.showModal()}>
        Editar
      </Button>

      <dialog
        ref={dialogRef}
        aria-label={`Editar factura ${invoice.number}`}
        className="w-[min(44rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6">
          <header className="mb-5">
            <p className="label-rule">Factura</p>
            <h2 className="font-display mt-1 text-2xl">{invoice.number}</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Total actual {formatMoneyCOP(invoice.total)}. Los importes se recalculan al
              guardar.
            </p>
          </header>

          <form action={formAction} className="space-y-4">
            <input type="hidden" name="id" value={invoice.id} />

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Vencimiento" name="due_at" idPrefix={prefix}>
                {(props) => (
                  <TextInput
                    {...props}
                    type="date"
                    defaultValue={invoice.due_at ? invoice.due_at.slice(0, 10) : ""}
                  />
                )}
              </FormField>

              <FormField label="Impuesto" name="tax_rate" idPrefix={prefix}>
                {(props) => (
                  <TextInput
                    {...props}
                    inputMode="decimal"
                    defaultValue={invoice.tax_rate}
                    placeholder="0.0000"
                  />
                )}
              </FormField>
            </div>

            <FormField label="Expediente" name="case_id" idPrefix={prefix}>
              {(props) => (
                <SelectInput {...props} defaultValue={invoice.case_id ?? ""}>
                  <option value="">Sin expediente</option>
                  {cases.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </FormField>

            <fieldset>
              <legend className="label-rule">Conceptos</legend>
              <div className="mt-2 space-y-2">
                {lines.map((line, index) => (
                  <div key={index} className="flex gap-2">
                    <input type="hidden" name="line_quantity" value={line.quantity} readOnly />
                    <input
                      type="hidden"
                      name="line_unit_price"
                      value={line.unit_price}
                      readOnly
                    />
                    <input
                      name="line_description"
                      value={line.description}
                      onChange={(event) => changeLine(index, "description", event.target.value)}
                      aria-label={`Concepto ${index + 1}`}
                      className="w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
                    />
                    <input
                      value={line.unit_price}
                      onChange={(event) => changeLine(index, "unit_price", event.target.value)}
                      inputMode="decimal"
                      aria-label={`Precio del concepto ${index + 1}`}
                      className="w-28 rounded-card border border-rule-strong bg-surface px-3 py-2 text-right font-mono text-sm text-ink outline-none focus:border-wax"
                    />
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addLine}
                className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-wax"
              >
                Añadir concepto
              </button>
            </fieldset>

            <FormField label="Notas" name="notes" idPrefix={prefix}>
              {(props) => <TextArea {...props} rows={2} defaultValue={invoice.notes ?? ""} />}
            </FormField>

            <FormStatus state={state} />

            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialogRef.current?.close()}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" pending={pending}>
                Guardar cambios
              </Button>
            </div>
          </form>
        </div>
      </dialog>
    </>
  );
}
