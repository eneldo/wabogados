"use client";

import { useActionState } from "react";

import type { ActionState } from "@/lib/types";

/**
 * Form controls for the administration.
 *
 * The project had no `Button` or `Input`: the only input in the codebase was
 * hand-written inside the login form, and nine modules about to be built would
 * have copied that line nine times. These are the extracted version, plus the
 * three things a CRUD screen needs that nobody had yet: a pending state, a
 * field-level error, and a confirmation that says what is about to happen.
 *
 * All of it is client-side because a form that reports a pending state and shows
 * a server error has to be interactive.
 */

const CONTROL =
  "w-full rounded-card border bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-wax disabled:cursor-not-allowed disabled:opacity-60";

function fieldClass(hasError: boolean, extra = ""): string {
  return `${CONTROL} ${hasError ? "border-wax" : "border-rule-strong"} ${extra}`;
}

export type ButtonVariant = "primary" | "secondary" | "quiet" | "danger" | "ghost";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-action text-on-action hover:bg-action-hover",
  secondary: "border border-rule-strong bg-surface text-ink hover:border-wax hover:text-wax",
  /*
    For a button that shares a row with a link. A bordered button next to a
    bordered link is two competing edges; `quiet` keeps the box but drops the
    fill, so the row has one clear target and one quiet one.
  */
  quiet: "border border-rule bg-transparent text-ink-muted hover:border-rule-strong hover:text-ink",
  danger: "border border-wax/40 bg-wax-tint text-wax-deep hover:bg-danger-strong hover:text-on-action",
  ghost: "text-ink-muted hover:text-ink",
};

export function Button({
  variant = "secondary",
  pending = false,
  className = "",
  children,
  ...rest
}: {
  variant?: ButtonVariant;
  pending?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || pending}
      aria-busy={pending || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-card px-3.5 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${BUTTON[variant]} ${className}`}
    >
      {pending ? "Guardando…" : children}
    </button>
  );
}

/**
 * One labelled control.
 *
 * `error` is shown next to the control and wired with `aria-describedby` and
 * `aria-invalid`, so the message reaches a screen reader at the moment the field
 * becomes invalid rather than only being seen.
 */
export function FormField({
  label,
  name,
  idPrefix,
  error,
  hint,
  required,
  children,
  className = "",
}: {
  label: string;
  name: string;
  /**
   * Prefixes the DOM id while leaving the submitted `name` alone.
   *
   * A case page renders the case form plus three dialogs, and `notes` and
   * `client_id` appear in more than one of them. Repeating an id is invalid
   * HTML and, worse, it silently breaks every `<label htmlFor>` on the page:
   * the label focuses whichever control the browser happens to find first.
   * The prefix keeps the ids unique; the field names still submit as before.
   */
  idPrefix?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: (props: {
    id: string;
    name: string;
    "aria-invalid": boolean | undefined;
    "aria-describedby": string | undefined;
  }) => React.ReactNode;
  className?: string;
}) {
  const id = idPrefix ? `${idPrefix}-${name}` : name;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy =
    [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className={className}>
      <label htmlFor={id} className="label-rule block">
        {label}
        {required ? <span className="ml-1 text-wax">*</span> : null}
      </label>
      <div className="mt-1.5">
        {children({
          id,
          name,
          "aria-invalid": error ? true : undefined,
          "aria-describedby": describedBy,
        })}
      </div>
      {hint && !error ? (
        <p id={hintId} className="mt-1 text-xs text-ink-faint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="mt-1 text-xs font-medium text-wax-deep">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput({
  invalid,
  className = "",
  ...rest
}: { invalid?: boolean } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      aria-invalid={rest["aria-invalid"] ?? (invalid ? true : undefined)}
      className={fieldClass(Boolean(invalid), className)}
    />
  );
}

export function SelectInput({
  invalid,
  className = "",
  children,
  ...rest
}: { invalid?: boolean } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...rest}
      aria-invalid={rest["aria-invalid"] ?? (invalid ? true : undefined)}
      className={fieldClass(Boolean(invalid), className)}
    >
      {children}
    </select>
  );
}

export function TextArea({
  invalid,
  className = "",
  ...rest
}: { invalid?: boolean } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      aria-invalid={rest["aria-invalid"] ?? (invalid ? true : undefined)}
      className={fieldClass(Boolean(invalid), `${className} resize-y`)}
    />
  );
}

/** A checkbox that carries its own explanation, used for consent and opt-ins. */
export function CheckField({
  name,
  value,
  label,
  hint,
  defaultChecked,
}: {
  name: string;
  value?: string;
  label: string;
  hint?: string;
  defaultChecked?: boolean;
}) {
  return (
    <label className="flex items-start gap-2.5 text-sm text-ink-soft">
      <input
        type="checkbox"
        name={name}
        value={value ?? "on"}
        defaultChecked={defaultChecked}
        className="mt-0.5 size-4 shrink-0 accent-wax"
      />
      <span>
        {label}
        {hint ? <span className="mt-0.5 block text-xs text-ink-faint">{hint}</span> : null}
      </span>
    </label>
  );
}

/**
 * The form's own status line.
 *
 * Success is only ever shown after the server confirmed. The copy is the
 * sentence the backend produced, so the screen cannot promise more than the
 * system did — the same rule the public consultation form follows.
 */
export function FormStatus({ state }: { state: ActionState }) {
  if (state.status === "idle") return null;

  if (state.status === "ok") {
    return (
      <p
        role="status"
        className="rounded-card border border-forest/30 bg-forest-tint px-3.5 py-2.5 text-sm text-forest"
      >
        {state.message}
      </p>
    );
  }

  return (
    <div
      role="alert"
      className="rounded-card border border-wax/40 bg-wax-tint px-3.5 py-2.5 text-sm text-wax-deep"
    >
      <p className="font-medium">{state.message}</p>
      {state.errors && Object.keys(state.errors).length > 0 ? (
        <ul className="mt-1.5 space-y-0.5 text-xs">
          {Object.entries(state.errors).map(([field, text]) => (
            <li key={field}>
              <span className="opacity-70">{FIELD_LABELS[field] ?? field}:</span>{" "}
              {text}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** Field names the backend uses, in the words the person filling the form used. */
const FIELD_LABELS: Record<string, string> = {
  full_name: "Nombre",
  legal_name: "Razón social",
  commercial_name: "Nombre comercial",
  document_type: "Tipo de documento",
  document_number: "Número de documento",
  email: "Correo electrónico",
  phone: "Teléfono",
  address: "Dirección",
  notes: "Notas",
  professional_card: "Tarjeta profesional",
  specialties: "Especialidades",
  legal_area_ids: "Áreas jurídicas",
  status: "Estado",
};

/**
 * A submit button wired to the action's pending state.
 *
 * `useActionState` is what gives the button its "Guardando…" without the form
 * being submitted twice: while a transition is in flight React refuses to start
 * another one, so the guard belongs here and not in the click handler.
 */
export function SubmitButton({
  action,
  label,
  variant = "primary",
  className = "",
}: {
  action: (state: ActionState, form: FormData) => Promise<ActionState>;
  label: string;
  variant?: ButtonVariant;
  className?: string;
}) {
  const [state, formAction, pending] = useActionState(action, {
    status: "idle",
  });
  return (
    <form action={formAction} className={className}>
      <Button type="submit" variant={variant} pending={pending}>
        {label}
      </Button>
      <span className="sr-only" aria-live="polite">
        {state.status === "idle" ? "" : (state.message ?? "")}
      </span>
    </form>
  );
}
