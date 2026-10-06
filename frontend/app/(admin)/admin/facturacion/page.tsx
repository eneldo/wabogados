import Link from "next/link";
import { redirect } from "next/navigation";

import {
  IssueInvoiceButton,
  RegisterPaymentButton,
  VoidInvoiceButton,
} from "@/components/admin/facturacion/invoice-actions";
import { EditInvoiceButton, InvoiceForm } from "@/components/admin/facturacion/invoice-form";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader, Pager } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  formatDate,
  formatMoneyCOP,
  invoiceStatusLabel,
  invoiceStatusTone,
  paymentMethodLabel,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type {
  AgingReport,
  InvoiceRecord,
  PaginatedInvoices,
} from "@/lib/types";

/**
 * Facturación: what the firm has billed and what it is owed (MASTER_PROMPT V3).
 *
 * The screen leads with the aging report rather than with the list, because the
 * question a billing screen is opened for is almost never "show me the invoices"
 * but "how much is late and by how much". The list is underneath.
 *
 * **Drafting and issuing are different acts and the buttons say so.** A lawyer
 * prepares a bill; an administrator decides what leaves the firm. Nothing here
 * asks for a total: the amounts come from the server and the totals column is a
 * reading, not an input.
 */

const PAGE_SIZE = 25;

const AGING_LABELS: [keyof AgingReport, string][] = [
  ["vigente", "Sin vencer"],
  ["1_30", "1 a 30 días"],
  ["31_60", "31 a 60 días"],
  ["61_90", "61 a 90 días"],
  ["mas_90", "Más de 90 días"],
];

export default async function BillingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const { profile } = session;
  const can = (permission: string) => profile.permissions.includes(permission);

  if (!can("invoices:read")) {
    return (
      <div>
        <PageHeader
          eyebrow="Facturación"
          title="Facturación"
          description="Su perfil no tiene el permiso para consultar la facturación."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso a esta sección"
            hint="La facturación es interna de la firma; consulte con un administrador si necesita verla."
          />
        </div>
      </div>
    );
  }

  const params = await searchParams;
  const search = first(params.q);
  const status = first(params.estado);
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);

  const { value, failed } = await load<PaginatedInvoices>("/api/v1/billing/invoices", {
    skip,
    limit: PAGE_SIZE,
    search,
    status,
  });
  const { value: aging } = await load<AgingReport>("/api/v1/billing/aging");

  const invoices = value?.items ?? [];
  const total = value?.total ?? 0;

  const { value: clients } = can("clients:read")
    ? await load<{ items: { id: string; full_name: string | null; document_number: string }[] }>(
        "/api/v1/clients",
        { skip: 0, limit: 200 },
      )
    : { value: null };
  /*
    Cases are authorised by **scope**, not by a single permission: the API accepts
    `cases:read_all`, `cases:read_assigned` and `cases:read_published` and returns
    whatever the caller may see. A `can("cases:read")` here would always be false
    and the select would come up empty for everyone — the same trap `admin-nav.ts`
    documents for the Expedientes entry. Any of the three counts, and the API has
    the last word.
  */
  const canReadCases = ["cases:read_all", "cases:read_assigned", "cases:read_published"].some(
    (permission) => can(permission),
  );

  const { value: cases } = canReadCases
    ? await load<{ items: { id: string; case_number: string; title: string }[] }>(
        "/api/v1/cases",
        { skip: 0, limit: 200 },
      )
    : { value: null };

  const clientOptions = (clients?.items ?? []).map((entry) => ({
    id: entry.id,
    label: `${entry.full_name ?? entry.document_number}`,
  }));
  const caseOptions = (cases?.items ?? []).map((entry) => ({
    id: entry.id,
    label: `${entry.case_number} · ${entry.title}`,
  }));

  const hrefFor = (next: { q?: string; estado?: string; skip?: number }) => {
    const query = new URLSearchParams();
    const put = (key: string, value: string | number | undefined) => {
      if (value === undefined || value === "") return;
      query.set(key, String(value));
    };
    put("q", next.q ?? search);
    put("estado", next.estado ?? status);
    put("skip", next.skip);
    return query.size > 0 ? `/admin/facturacion?${query.toString()}` : "/admin/facturacion";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Facturación"
        title="Facturación"
        description="Honorarios facturados y cuentas por cobrar. Los importes los calcula el servidor a partir de los conceptos: aquí nadie escribe un total. Una factura emitida ya no cambia sus conceptos, y anularla conserva el número."
        actions={<InvoiceForm canAct={can("invoices:create")} clients={clientOptions} cases={caseOptions} />}
      />

      {aging ? (
        <section className="mt-6">
          <SectionHeading eyebrow="Cartera" title="Antigüedad de la cartera" />
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {AGING_LABELS.map(([key, label], index) => (
              <Card key={key} className="px-4 py-3">
                <p className="text-xs uppercase tracking-[0.12em] text-ink-faint">{label}</p>
                <p
                  className={`mt-1.5 font-display text-xl tnum ${
                    index >= 3 ? "text-wax-deep" : "text-ink"
                  }`}
                >
                  {formatMoneyCOP(aging[key])}
                </p>
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      <FilterBar>
        <FilterField
          label="Buscar"
          name="q"
          defaultValue={search}
          placeholder="Número o notas"
          className="min-w-[14rem] flex-1"
        />
        <div>
          <label htmlFor="filtro-estado" className="label-rule block">
            Estado
          </label>
          <select
            id="filtro-estado"
            name="estado"
            defaultValue={status ?? ""}
            className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
          >
            <option value="">Todos</option>
            <option value="borrador">Borrador</option>
            <option value="emitida">Emitida</option>
            <option value="pagada">Pagada</option>
            <option value="anulada">Anulada</option>
          </select>
        </div>
        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {search || status ? (
          <Link
            href="/admin/facturacion"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar la facturación. Una lista vacía y una lista que no se
          pudo leer no son lo mismo, y aquí no se confunden.
        </p>
      ) : null}

      <div className="mt-6">
        {invoices.length === 0 ? (
          <EmptyState
            title={
              search || status
                ? "Ninguna factura coincide"
                : "Todavía no hay facturas"
            }
            hint={
              search || status
                ? "Pruebe con otro texto o quite los filtros."
                : "Es lo normal en una instalación recién estrenada. Cree un borrador con «Nueva factura»; se emite cuando esté listo."
            }
          />
        ) : (
          <>
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="ledger min-w-[62rem]">
                  <caption className="sr-only">
                    Facturas, {total} en total
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className="label-rule">
                        Número
                      </th>
                      <th scope="col" className="label-rule">
                        Cliente
                      </th>
                      <th scope="col" className="label-rule">
                        Estado
                      </th>
                      <th scope="col" className="label-rule text-right">
                        Total
                      </th>
                      <th scope="col" className="label-rule text-right">
                        Saldo
                      </th>
                      <th scope="col" className="label-rule">
                        Vence
                      </th>
                      <th scope="col" className="label-rule text-right">
                        Acciones
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((invoice) => (
                      <InvoiceRow
                        key={invoice.id}
                        invoice={invoice}
                        canEdit={can("invoices:update")}
                        canIssue={can("invoices:issue")}
                        canVoid={can("invoices:void")}
                        canPay={can("payments:create")}
                        cases={caseOptions}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Pager
              total={total}
              skip={skip}
              limit={PAGE_SIZE}
              pageHref={(next) => hrefFor({ skip: next })}
            />
          </>
        )}

        <RuleNote>
          Una factura no se borra: se anula, y el número se conserva porque es lo que
          permite explicar más adelante por qué ese número ya no cuenta. Los importes
          y el saldo los calcula el servidor, y el estado «pagada» lo decide el saldo
          —no quien lo escribe—. El impuesto se deja en 0 por defecto: la tasa es un
          dato que tiene que traer quien conoce la posición tributaria del cliente.
        </RuleNote>
      </div>
    </div>
  );
}

function InvoiceRow({
  invoice,
  canEdit,
  canIssue,
  canVoid,
  canPay,
  cases,
}: {
  invoice: InvoiceRecord;
  canEdit: boolean;
  canIssue: boolean;
  canVoid: boolean;
  canPay: boolean;
  cases: { id: string; label: string }[];
}) {
  const accent =
    invoice.status === "anulada"
      ? "closed"
      : invoice.status === "pagada"
        ? "live"
        : "held";

  return (
    <tr data-accent={accent} className="row-enter">
      <th scope="row" className="py-4 pr-4 font-normal">
        <span className="row-title font-mono text-[0.8125rem]">{invoice.number}</span>
        <span className="mt-1 block text-xs text-ink-faint">
          {invoice.lines.length} concepto{invoice.lines.length === 1 ? "" : "s"}
          {invoice.case_number ? ` · ${invoice.case_number}` : ""}
        </span>
        {invoice.status === "anulada" && invoice.void_reason ? (
          <span className="mt-1 block max-w-[22rem] text-xs text-ink-muted">
            Anulada: {invoice.void_reason}
          </span>
        ) : null}
      </th>
      <td className="py-4 pr-4 align-top text-[0.8125rem] text-ink-muted">
        {invoice.client_name ?? "—"}
      </td>
      <td className="py-4 pr-4 align-top">
        <Chip tone={invoiceStatusTone(invoice.status)}>
          {invoiceStatusLabel(invoice.status)}
        </Chip>
      </td>
      <td className="py-4 pr-4 text-right align-top font-mono text-[0.8125rem] tnum text-ink">
        {formatMoneyCOP(invoice.total)}
      </td>
      <td className="py-4 pr-4 text-right align-top font-mono text-[0.8125rem] tnum">
        {invoice.status === "anulada" ? (
          <span className="text-ink-faint">—</span>
        ) : (
          <span className={invoice.balance === "0" ? "text-forest" : "text-wax-deep"}>
            {formatMoneyCOP(invoice.balance)}
          </span>
        )}
      </td>
      <td className="row-meta py-4 pr-4 align-top">
        {invoice.due_at ? formatDate(invoice.due_at) : "—"}
      </td>
      <td className="py-4 align-top">
        <div className="flex flex-wrap justify-end gap-1">
          {invoice.payments.length > 0 ? (
            <span className="sr-only">
              {invoice.payments
                .map(
                  (payment) =>
                    `${formatMoneyCOP(payment.amount)} por ${paymentMethodLabel(payment.method)}`,
                )
                .join("; ")}
            </span>
          ) : null}
          {canPay ? <RegisterPaymentButton invoice={invoice} /> : null}
          {invoice.status === "borrador" && canEdit ? (
            <EditInvoiceButton invoice={invoice} canAct={canEdit} cases={cases} />
          ) : null}
          {canIssue ? <IssueInvoiceButton invoice={invoice} /> : null}
          {canVoid && invoice.status !== "anulada" ? (
            <VoidInvoiceButton invoice={invoice} />
          ) : null}
        </div>
      </td>
    </tr>
  );
}

async function load<T>(
  path: string,
  query: Record<string, string | number | boolean | undefined> = {},
): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path, { query }), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}
