"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import { Button, FormField, FormStatus, TextInput } from "@/components/admin/form-controls";
import { resetUserPassword } from "@/features/seguridad/actions";
import type { ActionState, AdminUserRecord } from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

export function ResetPasswordButton({ user }: { user: AdminUserRecord }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);

  function close() {
    dialog.current?.close();
    setOpen(false); // Unmount both password inputs and action state on every close.
    trigger.current?.focus();
  }

  return (
    <>
      <button ref={trigger} type="button" className="rounded-card border border-rule px-3 py-2 text-xs font-semibold text-ink-muted hover:text-ink"
        onClick={() => { setMessage(""); setOpen(true); dialog.current?.showModal(); }}>
        Restablecer contraseña
      </button>
      <span role="status" className="max-w-64 whitespace-normal text-left text-xs text-forest">{message}</span>
      <dialog ref={dialog} aria-label={`Restablecer contraseña de ${user.email}`}
        onClose={close}
        onCancel={(event) => {
          if (dialog.current?.querySelector('form[aria-busy="true"]')) event.preventDefault();
        }}
        className="m-auto w-[min(34rem,calc(100vw-2rem))] whitespace-normal rounded-card border border-rule-strong bg-surface p-0 text-left backdrop:bg-ink/45">
        {open ? <ResetForm user={user} onClose={close} onSuccess={(text) => { setMessage(text); close(); }} /> : null}
      </dialog>
    </>
  );
}

function ResetForm({ user, onClose, onSuccess }: {
  user: AdminUserRecord; onClose: () => void; onSuccess: (message: string) => void;
}) {
  const [state, action, pending] = useActionState(resetUserPassword, IDLE);
  const [visible, setVisible] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const submitting = useRef(false);
  const prefix = `reset-password-${user.id}`;

  useEffect(() => {
    submitting.current = false;
    form.current?.reset();
    if (state.status === "ok") onSuccess(state.message ?? "Contraseña restablecida.");
    else if (state.status === "error") {
      form.current?.querySelector<HTMLInputElement>('[aria-invalid="true"]')?.focus();
    }
  }, [state, onSuccess]);

  return (
    <div className="max-h-[85vh] overflow-y-auto p-6">
      <h2 className="font-display text-2xl">Restablecer contraseña</h2>
      <p className="mt-2 break-words text-sm text-ink-soft">{user.full_name ?? user.email} · {user.email}</p>
      <p className="my-4 text-sm text-brass">La contraseña anterior dejará de funcionar y se cerrarán todas las sesiones anteriores de esta cuenta. Verifique la identidad del titular y comunique la nueva clave por un canal seguro.</p>
      <form ref={form} action={action} aria-busy={pending} className="space-y-4" onSubmit={(event) => {
        if (submitting.current) event.preventDefault();
        else submitting.current = true;
      }}>
        <input type="hidden" name="user_id" value={user.id} />
        <fieldset disabled={pending} className="space-y-4">
          <FormField label="Nueva contraseña" name="new_password" idPrefix={prefix} required
            hint="Entre 8 y 128 caracteres. Los espacios se conservan." error={state.errors?.new_password}>
            {(props) => <TextInput {...props} type={visible ? "text" : "password"} required minLength={8} maxLength={128} autoComplete="new-password" autoFocus />}
          </FormField>
          <FormField label="Confirmar contraseña" name="confirm_password" idPrefix={prefix} required error={state.errors?.confirm_password}>
            {(props) => <TextInput {...props} type={visible ? "text" : "password"} required minLength={8} maxLength={128} autoComplete="new-password" />}
          </FormField>
          <Button type="button" variant="ghost" aria-pressed={visible} onClick={() => setVisible(!visible)}>
            {visible ? "Ocultar contraseñas" : "Mostrar contraseñas"}
          </Button>
        </fieldset>
        <FormStatus state={state} />
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" disabled={pending} onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" pending={pending}>Restablecer contraseña</Button>
        </div>
      </form>
    </div>
  );
}
