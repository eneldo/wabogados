"use client";

import { useActionState, useEffect, useRef } from "react";

import { respondClientRequestAction } from "@/app/portal/actions";
import type { ActionState } from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

export function ClientRequestRespondForm({ requestId }: { requestId: string }) {
  const bound = respondClientRequestAction.bind(null, requestId);
  const [state, formAction, pending] = useActionState(bound, IDLE);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (state.status === "ok") formRef.current?.reset();
  }, [state.status]);

  return (
    <form ref={formRef} action={formAction} className="mt-4 space-y-3">
      <label className="block">
        <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">
          Su respuesta
        </span>
        <textarea
          name="response_text"
          required
          rows={3}
          maxLength={4000}
          className="mt-1.5 w-full rounded-md border border-rule bg-surface px-3 py-2 text-sm text-ink outline-none transition focus:border-forest focus:ring-1 focus:ring-forest/30"
          placeholder="Escriba aquí la información solicitada o confirme que completó la tarea..."
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-forest px-4 py-2 text-sm font-medium text-white transition hover:bg-forest/90 disabled:opacity-60"
        >
          {pending ? "Enviando..." : "Enviar respuesta"}
        </button>
        {state.status === "ok" ? (
          <p className="text-sm text-forest" role="status">{state.message}</p>
        ) : null}
        {state.status === "error" ? (
          <p className="text-sm text-wax-deep" role="alert">{state.message}</p>
        ) : null}
      </div>
    </form>
  );
}
