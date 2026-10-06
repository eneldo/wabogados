"use client";

import { useState } from "react";

import { DocumentDetailDrawer } from "@/components/admin/documentos/document-detail";

/**
 * The row's "Ver" action.
 *
 * A button, not a link: the detail opens in a drawer on this page rather than
 * navigating away, because a browser session spent comparing documents should
 * not have to walk back to the list after every one of them.
 */
export function DocumentViewButton({
  documentId,
  canDownload,
}: {
  documentId: string;
  canDownload: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="row-action-link cursor-pointer"
        onClick={() => setOpen(true)}
      >
        Ver
      </button>
      {open ? (
        <DocumentDetailDrawer
          key={documentId}
          documentId={documentId}
          canDownload={canDownload}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}
