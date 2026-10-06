"use client";

import { useCallback, useEffect, useRef, type ReactNode } from "react";

/**
 * The dialog the reference uses for articles, roles and legal notes.
 *
 * `<dialog>` is kept because it brings the focus trap, the inert background and
 * the Escape handling with it. The one thing it does not do by default is
 * restore focus to whatever opened it, so that is added here: a keyboard user
 * who closes a dialog should land back on the link they pressed, not at the top
 * of the document.
 */
export function SiteDialog({
  open,
  onClose,
  label,
  children,
}: {
  open: boolean;
  onClose: () => void;
  label: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      opener.current = document.activeElement as HTMLElement | null;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const handleClose = useCallback(() => {
    ref.current?.close();
    opener.current?.focus();
    onClose();
  }, [onClose]);

  const handleClickOutside = useCallback(
    (event: React.MouseEvent<HTMLDialogElement>) => {
      // A click that lands on the dialog element itself came from the backdrop:
      // the dialog box is the element, and everything inside it is a descendant.
      if (event.target !== ref.current) return;
      const box = ref.current.getBoundingClientRect();
      const outside =
        event.clientX < box.left ||
        event.clientX > box.right ||
        event.clientY < box.top ||
        event.clientY > box.bottom;
      if (outside) handleClose();
    },
    [handleClose],
  );

  return (
    <dialog
      ref={ref}
      className="site-modal"
      aria-label={label}
      onClose={handleClose}
      onClick={handleClickOutside}
    >
      <button
        type="button"
        onClick={handleClose}
        aria-label="Cerrar ventana"
        className="absolute top-3 right-4 text-xl leading-none text-slate hover:text-gold"
      >
        <span aria-hidden="true">×</span>
      </button>
      {children}
    </dialog>
  );
}
