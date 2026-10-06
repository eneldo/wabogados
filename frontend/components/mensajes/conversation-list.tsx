"use client";

import { useRouter } from "next/navigation";
import { useActionState, useEffect, useRef, useState } from "react";

import { Button, FormStatus } from "@/components/admin/form-controls";
import { Chip } from "@/components/primitives";
import { formatDateTime } from "@/lib/format";
import type {
  ActionState,
  ConversationSummary,
  Message,
  ThreadResponse,
} from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

type CloseAction = (state: ActionState, form: FormData) => Promise<ActionState>;

/** A personal inbox: visibility is decided by the API, never by this component. */
export function ConversationList({
  initial,
  profileId,
  canAttach = false,
  canArchive = false,
  canClose = false,
  closeAction,
  emptyMessage = "No tiene conversaciones con el despacho.",
}: {
  initial: ConversationSummary[];
  profileId: string;
  canAttach?: boolean;
  canArchive?: boolean;
  canClose?: boolean;
  closeAction?: CloseAction;
  emptyMessage?: string;
}) {
  const router = useRouter();
  const [summaries, setSummaries] = useState(initial);
  const [selected, setSelected] = useState<string | null>(
    initial.find((item) => item.unread > 0)?.id ?? initial[0]?.id ?? null,
  );
  const [loaded, setLoaded] = useState<{ id: string; thread: ThreadResponse } | null>(null);
  const [loadFailure, setLoadFailure] = useState<{ id: string; message: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState<string | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [closeState, closeFormAction, closePending] = useActionState(
    closeAction ?? unavailableCloseAction,
    IDLE,
  );
  const endRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const closeDialogRef = useRef<HTMLDialogElement>(null);

  const summary = summaries.find((item) => item.id === selected);
  const loadingError = loadFailure?.id === selected ? loadFailure.message : null;
  const thread = loaded?.id === selected
    ? {
        ...loaded.thread,
        conversation: {
          ...loaded.thread.conversation,
          status: summary?.status ?? loaded.thread.conversation.status,
        },
      }
    : null;

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;

    void (async () => {
      try {
        const response = await fetch(`/api/proxy/conversations/${selected}`, {
          cache: "no-store",
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          if (!cancelled) {
            setLoadFailure({
              id: selected,
              message: errorMessage(payload, "No fue posible cargar la conversación."),
            });
          }
          return;
        }
        if (!cancelled) {
          setLoaded({ id: selected, thread: payload as ThreadResponse });
          setLoadFailure(null);
          setSummaries((current) =>
            current.map((item) => item.id === selected ? { ...item, unread: 0 } : item),
          );
        }
      } catch {
        if (!cancelled) {
          setLoadFailure({ id: selected, message: "No fue posible cargar la conversación." });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selected]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [thread?.messages.length]);

  useEffect(() => {
    if (closeState.status === "ok") {
      closeDialogRef.current?.close();
      router.refresh();
    }
  }, [closeState.status, router]);

  async function send(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || sending) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const body = String(data.get("body") ?? "").trim();
    if (!body) return;
    const files = data.getAll("files").filter((value): value is File => value instanceof File && value.size > 0);
    if (files.length > 5) {
      setSendError("Puede adjuntar como máximo 5 archivos por mensaje.");
      return;
    }
    if (files.some((file) => file.size > 10 * 1024 * 1024)) {
      setSendError("Cada archivo debe pesar 10 MB o menos.");
      return;
    }

    setSending(true);
    setSendError(null);
    try {
      const response = await fetch(`/api/proxy/conversations/${selected}/messages`, {
        method: "POST",
        body: data,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setSendError(errorMessage(payload, "No fue posible enviar el mensaje."));
        return;
      }
      const created = payload as Message;
      setLoaded((current) =>
        current?.id === selected
          ? {
              id: current.id,
              thread: {
                ...current.thread,
                messages: [...current.thread.messages, created],
                conversation: {
                  ...current.thread.conversation,
                  message_count: current.thread.conversation.message_count + 1,
                  last_message_at: created.sent_at,
                  last_message_preview: created.body,
                  unread: 0,
                },
              },
            }
          : current,
      );
      setSummaries((current) =>
        current.map((item) =>
          item.id === selected
            ? {
                ...item,
                message_count: item.message_count + 1,
                last_message_at: created.sent_at,
                last_message_preview: created.body,
                unread: 0,
              }
            : item,
        ),
      );
      form.reset();
      router.refresh();
    } catch {
      setSendError("Se perdió la conexión.");
    } finally {
      setSending(false);
    }
  }

  async function archive(messageId: string) {
    if (archiving) return;
    setArchiving(messageId);
    setArchiveError(null);
    try {
      const response = await fetch(`/api/proxy/messages/${messageId}`, { method: "DELETE" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setArchiveError(errorMessage(payload, "No fue posible archivar el mensaje."));
        return;
      }
      setLoaded((current) =>
        current?.id === selected
          ? {
              ...current,
              thread: {
                ...current.thread,
                messages: current.thread.messages.map((message) =>
                  message.id === messageId
                    ? { ...message, body: "", deleted_at: new Date().toISOString(), attachments: [] }
                    : message,
                ),
              },
            }
          : current,
      );
      router.refresh();
    } catch {
      setArchiveError("Se perdió la conexión.");
    } finally {
      setArchiving(null);
    }
  }

  if (summaries.length === 0) {
    return (
      <p className="rounded-card border border-dashed border-rule-strong bg-surface-sunk px-6 py-12 text-center text-sm text-ink-muted">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className="message-workspace grid min-w-0 gap-5 xl:grid-cols-[21rem_minmax(0,1fr)]">
      <ol className="message-inbox max-h-[44rem] space-y-2 overflow-y-auto pr-1">
        {summaries.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => setSelected(item.id)}
              aria-current={selected === item.id ? "true" : undefined}
              className={`message-inbox-row w-full rounded-card border px-4 py-3.5 text-left transition-colors ${
                selected === item.id
                  ? "border-wax bg-surface shadow-card"
                  : "border-rule bg-surface hover:border-rule-strong"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="line-clamp-2 text-sm font-semibold leading-snug text-ink">
                  {item.subject}
                </span>
                {item.unread > 0 ? (
                  <span className="tnum shrink-0 rounded-full bg-wax px-2 py-0.5 text-[0.625rem] font-bold text-paper">
                    {item.unread}
                  </span>
                ) : null}
              </div>
              <span className="mt-2 block truncate text-xs text-ink-muted">
                {item.last_message_preview ?? "Sin mensajes"}
              </span>
              <span className="mt-2 flex items-center justify-between gap-3 text-[0.625rem] uppercase tracking-[0.1em] text-ink-faint">
                <span>{item.conversation_type === "cliente" ? "Cliente" : "Interna"}</span>
                <span className="tnum">
                  {item.last_message_at ? formatDateTime(item.last_message_at) : "Nueva"}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ol>

      <section className="message-thread flex min-h-[34rem] min-w-0 flex-col overflow-hidden rounded-card border border-rule bg-surface shadow-card">
        {loadingError ? (
          <p role="alert" className="m-5 rounded-card border border-wax/40 bg-wax-tint px-4 py-3 text-sm text-wax-deep">
            {loadingError}
          </p>
        ) : thread ? (
          <>
            <header className="border-b border-rule bg-surface-sunk px-5 py-4 sm:px-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip tone={thread.conversation.conversation_type === "cliente" ? "brass" : "neutral"} dot>
                      {thread.conversation.conversation_type === "cliente" ? "Cliente" : "Interna"}
                    </Chip>
                    <Chip tone={thread.conversation.status === "abierto" ? "forest" : "ink"}>
                      {thread.conversation.status === "abierto" ? "Abierta" : "Cerrada"}
                    </Chip>
                  </div>
                  <h2 className="font-display mt-2 text-2xl leading-tight text-ink">
                    {thread.conversation.subject}
                  </h2>
                  <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                    {thread.participants.map((item) => item.display_name).join(" · ")}
                  </p>
                </div>
                {canClose && closeAction && thread.conversation.status === "abierto" ? (
                  <>
                    <Button type="button" variant="quiet" onClick={() => closeDialogRef.current?.showModal()}>
                      Cerrar hilo
                    </Button>
                    <dialog
                      ref={closeDialogRef}
                      aria-label="Confirmar cierre de conversación"
                      className="w-[min(32rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
                    >
                      <form action={closeFormAction} className="p-6">
                        <input type="hidden" name="conversation_id" value={thread.conversation.id} />
                        <p className="label-rule">Correspondencia</p>
                        <h3 className="font-display mt-1 text-2xl text-ink">Cerrar conversación</h3>
                        <p className="mt-3 text-sm leading-relaxed text-ink-muted">
                          El hilo dejará de admitir respuestas. Los mensajes y adjuntos se conservarán íntegros.
                        </p>
                        <div className="mt-6 flex justify-end gap-2 border-t border-rule pt-4">
                          <Button type="button" variant="ghost" onClick={() => closeDialogRef.current?.close()}>Cancelar</Button>
                          <Button type="submit" variant="danger" pending={closePending}>Confirmar cierre</Button>
                        </div>
                      </form>
                    </dialog>
                  </>
                ) : null}
              </div>
              {closeState.status !== "idle" ? <div className="mt-3"><FormStatus state={closeState} /></div> : null}
            </header>

            <div className="message-scroll flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-6">
              {thread.messages.length === 0 ? (
                <p className="py-14 text-center text-sm text-ink-muted">
                  El hilo está abierto. Escriba el primer mensaje.
                </p>
              ) : null}
              {thread.messages.map((message) => {
                const mine = message.sender_id === profileId;
                return (
                  <article key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[88%] sm:max-w-[76%] ${mine ? "text-right" : "text-left"}`}>
                      <p className="mb-1 text-[0.625rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">
                        {mine ? "Tú" : message.sender_name}
                      </p>
                      <div className={`rounded-card px-4 py-3 text-sm leading-relaxed ${
                        mine ? "bg-ink text-paper" : "border border-rule bg-surface-sunk text-ink"
                      }`}>
                        {message.deleted_at ? (
                          <em className="opacity-60">Mensaje archivado</em>
                        ) : (
                          <p className="whitespace-pre-wrap break-words">{message.body}</p>
                        )}
                        {message.attachments.length > 0 ? (
                          <ul className={`mt-3 space-y-1.5 border-t pt-2 ${mine ? "border-paper/20" : "border-rule"}`}>
                            {message.attachments.map((attachment) => (
                              <li key={attachment.id}>
                                <a
                                  href={`/api/descarga/messages/attachments/${attachment.id}`}
                                  className="inline-flex max-w-full items-center gap-2 text-xs font-semibold underline underline-offset-4 hover:no-underline"
                                >
                                  <span aria-hidden="true">↓</span>
                                  <span className="truncate">{attachment.original_filename}</span>
                                  <span className="tnum shrink-0 opacity-60">{formatBytes(attachment.size_bytes)}</span>
                                </a>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                         <div className={`mt-2 flex flex-wrap items-center gap-3 text-[0.625rem] ${mine ? "justify-end text-paper/60" : "text-ink-faint"}`}>
                           <p className="tnum">{formatDateTime(message.sent_at)}</p>
                           {mine && canArchive && !message.deleted_at ? (
                             <button
                               type="button"
                               onClick={() => void archive(message.id)}
                               disabled={Boolean(archiving)}
                               className="font-semibold uppercase tracking-[0.1em] underline underline-offset-4 hover:no-underline disabled:cursor-not-allowed disabled:opacity-50"
                             >
                               {archiving === message.id ? "Archivando…" : "Archivar"}
                             </button>
                           ) : null}
                         </div>
                       </div>
                    </div>
                  </article>
                );
              })}
               <div ref={endRef} />
               {archiveError ? <p role="alert" className="text-center text-xs font-medium text-wax-deep">{archiveError}</p> : null}
             </div>
 
             {thread.conversation.status === "abierto" ? (
              <form ref={formRef} onSubmit={send} className="border-t border-rule bg-surface px-4 py-4 sm:px-6">
                <label htmlFor="message-body" className="sr-only">Escribir un mensaje</label>
                <textarea
                  id="message-body"
                  name="body"
                  required
                  maxLength={5000}
                  rows={3}
                  placeholder="Escriba una respuesta clara y verificable…"
                  className="w-full resize-y rounded-card border border-rule-strong bg-surface-sunk px-3 py-2.5 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-wax focus:bg-surface"
                />
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                   {canAttach ? (
                     <label className="cursor-pointer text-xs font-semibold text-ink-muted hover:text-wax">
                       <span>Adjuntar archivos</span>
                       <span className="ml-1 font-normal text-ink-faint">Máximo 5, hasta 10 MB cada uno</span>
                       <input
                         name="files"
                         type="file"
                         multiple
                         accept=".pdf,.png,.jpg,.jpeg,.gif,.tif,.tiff,.zip,.doc,.txt"
                         className="mt-1 block max-w-full text-xs font-normal"
                       />
                     </label>
                   ) : <span />}
                  <Button type="submit" variant="primary" pending={sending}>Enviar</Button>
                </div>
                {sendError ? <p role="alert" className="mt-3 text-xs font-medium text-wax-deep">{sendError}</p> : null}
              </form>
            ) : (
              <p className="border-t border-rule bg-surface-sunk px-5 py-4 text-center text-sm text-ink-muted">
                Este hilo está cerrado y conserva íntegra su correspondencia.
              </p>
            )}
          </>
        ) : (
          <p className="m-auto text-sm text-ink-muted">Cargando conversación…</p>
        )}
      </section>
    </div>
  );
}

async function unavailableCloseAction(): Promise<ActionState> {
  return { status: "error", message: "Esta acción no está disponible." };
}

function errorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const value = payload as { error?: { message?: string }; detail?: string };
  return value.error?.message ?? value.detail ?? fallback;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
