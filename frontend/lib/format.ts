/**
 * Formatting helpers.
 *
 * Spanish conventions throughout: the decimal comma, a dot for thousands, and
 * dates written the way a Spanish court would write them. A file of evidence
 * metadata is read by lawyers; `1.234,5 MB` is what they expect, not
 * `1,234.5 MB`.
 */

const NBSP = "\u00a0";

/** The court calendar is read in the firm's Colombian civil time, not container UTC. */
export const FIRM_TIME_ZONE = "America/Bogota";
export const FIRM_UTC_OFFSET_MINUTES = 300;

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes === 0) return `0${NBSP}B`;
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(
    Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** exponent;
  const decimals = exponent === 0 ? 0 : value >= 100 ? 0 : value >= 10 ? 1 : 2;
  return `${formatNumber(value, decimals)}${NBSP}${units[exponent]}`;
}

export function formatNumber(value: number, decimals = 0): string {
  return value.toLocaleString("es-ES", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${formatNumber(value, value >= 10 ? 0 : 1)}${NBSP}%`;
}

/**
 * Reduction between the original and its derivatives.
 *
 * Returns null when there is nothing to compare, so the caller can render a
 * dash instead of a misleading 0%.
 */
export function formatReduction(
  originalBytes: number | null | undefined,
  optimisedBytes: number | null | undefined,
): string | null {
  if (!originalBytes || !optimisedBytes) return null;
  if (optimisedBytes > originalBytes) return null;
  const reduction = (originalBytes - optimisedBytes) / originalBytes;
  return formatPercent(reduction * 100);
}

const DATE = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: FIRM_TIME_ZONE,
});

const DATE_TIME = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: FIRM_TIME_ZONE,
});

const TIME_ONLY = new Intl.DateTimeFormat("es-ES", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: FIRM_TIME_ZONE,
});

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : DATE.format(date);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : DATE_TIME.format(date);
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : TIME_ONLY.format(date);
}

/**
 * A moment as a standalone label: "Hoy · 10:00", "Mañana · 09:30", "13 oct 2026".
 * Used where the value stands on its own, under a heading.
 */
export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";

  const days = wholeDaysUntil(date);
  if (days === 0) return `Hoy · ${formatTime(iso)}`;
  if (days === 1) return `Mañana · ${formatTime(iso)}`;
  if (days === -1) return `Ayer · ${formatTime(iso)}`;
  if (days > 1 && days <= 30) return `En ${days} días`;
  if (days < -1) return `Hace ${Math.abs(days)} días`;
  return formatDate(iso);
}

function wholeDaysUntil(date: Date): number {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfTarget = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.round((startOfTarget.getTime() - startOfToday.getTime()) / 86_400_000);
}

/**
 * A moment as a phrase meant to sit inside a sentence, lower case.
 *
 * "Su próxima audiencia es en 11 días" reads wrong with a capitalised phrase
 * dropped in the middle, and this was visible on the panel before it was
 * written down here.
 */
export function relativeMoment(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;

  const days = wholeDaysUntil(date);
  if (days === 0) return `hoy a las ${formatTime(iso)}`;
  if (days === 1) return `mañana a las ${formatTime(iso)}`;
  if (days > 1 && days <= 30) return `en ${days} días`;
  if (days < 0) return `hace ${Math.abs(days)} días`;
  return `el ${formatDate(iso)}`;
}

/** Short form of a SHA-256, for a chip. The full value is always one click away. */
export function shortHash(sha256: string | null | undefined): string {
  if (!sha256) return "—";
  return `${sha256.slice(0, 8)}…${sha256.slice(-6)}`;
}

const HASH_WORDS = [
  " cero", " uno", " dos", " tres", " cuatro", " cinco", " seis", " siete",
  " ocho", " nueve", " diez", " once", " doce", " trece", " catorce", " quince",
];

/**
 * Group a digest into legible pairs. A hash a person can read aloud is more
 * useful when confirming a chain of custody over the telephone.
 */
export function hashSyllables(sha256: string): string {
  const nibble = Number.parseInt(sha256[0] ?? "0", 16);
  return HASH_WORDS[nibble] ?? ` ${nibble}`;
}

/** Human label for an evidence type coming from the backend enum. */
export function evidenceTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    documental: "Documental",
    fotografica: "Fotográfica",
    audio: "Audio",
    video: "Vídeo",
    testifical: "Testifical",
    pericial: "Pericial",
    informatica: "Informática",
  };
  return labels[value] ?? value;
}

export function visibilityLabel(value: string): string {
  const labels: Record<string, string> = {
    publicada: "Publicada",
    interna: "Interna",
    equipo: "Equipo",
  };
  return labels[value] ?? humanise(value);
}

/**
 * Turn a backend enum into readable Spanish.
 *
 * The enums are snake_case on purpose: they are stable in the database and in
 * the API. This is where they become language. `primera_instancia` reaching a
 * screen as `primera_instancia` is the bug this exists to prevent.
 */
export function humanise(value: string): string {
  const text = value.replace(/[_-]+/g, " ").trim();
  if (!text) return value;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const PROCEDURAL_STAGES: Record<string, string> = {
  preparacion: "Preparación de la prueba",
  prueba: "Prueba",
  prueba_iniciada: "Prueba iniciada",
  conclusiones: "Conclusiones",
  sentencia: "Sentencia",
  ejecucion: "Ejecución",
  primera_instancia: "Primera instancia",
  segunda_instancia: "Segunda instancia",
};

export function proceduralStageLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return PROCEDURAL_STAGES[value] ?? humanise(value);
}

export function attendanceLabel(value: string): string {
  const labels: Record<string, string> = {
    pendiente: "Pendiente",
    confirmed: "Confirmada",
    confirmada: "Confirmada",
    declined: "Confirmada en contra",
    ausente: "Ausente",
  };
  return labels[value] ?? humanise(value);
}

export function hearingStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    programada: "Programada",
    celebrated: "Celebrada",
    celebrada: "Celebrada",
    cancelled: "Cancelada",
    cancelada: "Cancelada",
    postponed: "Aplazada",
  };
  return labels[value] ?? humanise(value);
}

export function evidenceStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    upload: "Recibida",
    uploaded: "Recibida",
    validated: "Validada",
    stored: "Almacenada",
    processing: "Procesando",
    optimized: "Optimizada",
    ready: "Lista",
    failed: "Fallida",
    quarantined: "En cuarentena",
    archived: "Archivada",
  };
  return labels[value] ?? humanise(value);
}

/** Tone for a status chip. One place, so a state always looks the same. */
export type Tone = "neutral" | "forest" | "brass" | "wax" | "ink";

export function evidenceStatusTone(value: string): Tone {
  if (value === "ready" || value === "validated" || value === "stored") return "forest";
  if (value === "quarantined" || value === "failed") return "wax";
  if (value === "processing" || value === "optimized" || value === "uploaded") return "brass";
  if (value === "archived") return "ink";
  return "neutral";
}

export function visibilityTone(value: string): Tone {
  if (value === "publicada") return "forest";
  if (value === "equipo") return "brass";
  return "ink";
}

export function caseStatusTone(value: string): Tone {
  if (value === "cerrado" || value === "archivado") return "ink";
  if (value === "suspendido") return "brass";
  return "forest";
}

/** The nine process types the API accepts, in the words the firm would use. */
export function processTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    civil: "Civil",
    penal: "Penal",
    laboral: "Laboral",
    administrativo: "Administrativo",
    comercial: "Comercial",
    familia: "Familia",
    tributario: "Tributario",
    arbitraje: "Arbitraje",
    otro: "Otro",
  };
  return labels[value] ?? humanise(value);
}

export function priorityLabel(value: string): string {
  const labels: Record<string, string> = {
    baja: "Baja",
    normal: "Normal",
    alta: "Alta",
    urgente: "Urgente",
  };
  return labels[value] ?? humanise(value);
}

/**
 * Priority reads as urgency, and urgency is the one thing on this screen that
 * must never be mistaken for a decoration. Only the two ends get a colour.
 */
export function priorityTone(value: string): Tone {
  if (value === "urgente") return "wax";
  if (value === "alta") return "brass";
  return "neutral";
}

export function partyRoleLabel(value: string): string {
  const labels: Record<string, string> = {
    demandante: "Demandante",
    demandado: "Demandado",
    contraparte: "Contraparte",
    tercero: "Tercero",
  };
  return labels[value] ?? humanise(value);
}

export function caseStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    abierto: "Abierto",
    en_tramitacion: "En tramitación",
    suspendido: "Suspendido",
    cerrado: "Cerrado",
    archivado: "Archivado",
  };
  return labels[value] ?? humanise(value);
}

export function documentStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    borrador: "Borrador",
    vigente: "Vigente",
    reemplazado: "Reemplazado",
    anulado: "Anulado",
  };
  return labels[value] ?? humanise(value);
}

/**
 * Document state as it looks on the row.
 *
 * `vigente` is the only green because it is the only state that means "this is
 * the document". A draft is being written (brass, in progress), a replaced one
 * is history (ink) and an anulled one is struck out of the record (also ink:
 * it is kept, not flagged for attention).
 */
export function documentStatusTone(value: string): Tone {
  if (value === "vigente") return "forest";
  if (value === "borrador") return "brass";
  if (value === "anulado" || value === "reemplazado") return "ink";
  return "neutral";
}

export function documentTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    contrato: "Contrato",
    poder: "Poder",
    demanda: "Demanda",
    contestacion: "Contestación",
    memorial: "Memorial",
    auto: "Auto",
    sentencia: "Sentencia",
    prueba: "Prueba",
    identificacion: "Identificación",
    comunicacion: "Comunicación",
    otro: "Otro",
  };
  return labels[value] ?? humanise(value);
}

export function confidentialityLabel(value: string): string {
  const labels: Record<string, string> = {
    publico: "Público",
    interno: "Interno",
    confidencial: "Confidencial",
    secreto: "Secreto",
  };
  return labels[value] ?? humanise(value);
}

/**
 * How carefully the file must be handled.
 *
 * Only the two ends are coloured: `secreto` is red because opening it is a
 * decision, and `publico` is green because no restriction applies. The middle
 * two are ordinary handling and stay neutral.
 */
export function confidentialityTone(value: string): Tone {
  if (value === "secreto") return "wax";
  if (value === "publico") return "forest";
  return "neutral";
}

/**
 * Money, Spanish style.
 *
 * The API sends a Decimal, which arrives as a string so the cents survive. It is
 * read as a number only for display; `null` is a dash and not `0,00 €`, because
 * a case with no quantified amount and a case worth nothing are different things.
 */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const amount = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(amount)) return "—";
  return `${amount.toLocaleString("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}\u00a0€`;
}

export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function fileExtensionOf(name: string | null | undefined): string {
  if (!name) return "";
  const index = name.lastIndexOf(".");
  return index === -1 ? "" : name.slice(index + 1).toLowerCase();
}

/**
 * An audit entry is recorded as `"POST /api/v1/admin/users"`: the verb and the
 * path in one string. Split for display so the row can badge the verb and set
 * the path beside it, without the screen having to guess where the space is.
 */
export function auditActionParts(action: string): [method: string, path: string] {
  const index = action.indexOf(" ");
  if (index === -1) return [action, ""];
  return [action.slice(0, index), action.slice(index + 1)];
}

/**
 * The audit middleware writes exactly two results: every status below 400 is a
 * `success`, everything else is an `error`. Anything else would be a value the
 * backend does not produce, so it falls through to the raw word rather than
 * being quietly read as one of the two.
 */
export function auditResultLabel(result: string | null | undefined): string {
  if (!result) return "—";
  if (result === "success") return "Correcto";
  if (result === "error") return "Error";
  return humanise(result);
}

export function auditResultTone(result: string | null | undefined): Tone {
  if (result === "success") return "forest";
  if (result === "error") return "wax";
  return "neutral";
}

/**
 * Name the type a setting is read back as.
 *
 * `system_settings` stores text and decodes it as JSON on the way out, so the
 * same row can be a number, a boolean, an object or a plain string. Which one it
 * is decides how it is edited and whether a typo is caught: `30` is a number the
 * backend will compare as a number, while `America/Bogota` stays text. Showing
 * the type is cheaper than letting somebody discover it by breaking a consumer.
 */
export function settingValueType(value: unknown): string {
  if (value === null) return "nulo";
  if (Array.isArray(value)) return "lista";
  switch (typeof value) {
    case "number":
      return "número";
    case "boolean":
      return "booleano";
    case "object":
      return "objeto";
    case "string":
      return "texto";
    default:
      return "texto";
  }
}

/**
 * Render a setting for the ledger without inventing a value.
 *
 * An empty string is a legitimate setting — it is how a blank timezone or a blank
 * default is expressed — so it is shown as such and never as a dash, which would
 * read as "nothing stored".
 */
export function settingValueLabel(value: unknown, raw: string): string {
  if (typeof value === "string") return value === "" ? "(cadena vacía)" : value;
  if (value === null) return "nulo";
  if (value === undefined) return raw;
  try {
    return JSON.stringify(value, null, 2) ?? raw;
  } catch {
    return raw;
  }
}

/**
 * What a resource of the library is, in words.
 *
 * The four kinds are the whole vocabulary, and a screen that shows "video" or
 * "audio" next to the file type helps nobody: the words a librarian uses are
 * "grabación", "fotografía", "audio" and "documento".
 */
export function mediaKindLabel(kind: string): string {
  switch (kind) {
    case "video":
      return "Grabación";
    case "image":
      return "Fotografía";
    case "audio":
      return "Audio";
    case "document":
      return "Documento";
    default:
      return humanise(kind);
  }
}

export function mediaKindTone(kind: string): Tone {
  switch (kind) {
    case "video":
      return "wax";
    case "image":
      return "forest";
    case "audio":
      return "brass";
    default:
      return "neutral";
  }
}

/**
 * Confidentiality reads louder the narrower it gets.
 *
 * The colour is the point: a row that plays a deposition in front of somebody else
 * should be recognisable from across the desk, before the word is read.
 */
export function mediaConfidentialityTone(value: string): Tone {
  if (value === "confidencial") return "wax";
  if (value === "restringido") return "brass";
  return "neutral";
}

export function mediaConfidentialityLabel(value: string): string {
  if (value === "confidencial") return "Confidencial";
  if (value === "restringido") return "Restringido";
  return "Interno";
}

/** Duration in `m:ss` / `h:mm:ss`, or a dash when nothing has measured it. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return "—";
  }
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  const padded = (value: number) => String(value).padStart(2, "0");
  if (hours > 0) return `${hours}:${padded(minutes)}:${padded(rest)}`;
  return `${minutes}:${padded(rest)}`;
}

/**
 * Money for an invoice, in Colombian pesos.
 *
 * A **separate** function from `formatMoney`, and deliberately so: that one renders
 * euros and is used for the amount of a case, while a bill this firm issues is in
 * pesos — the firm's jurisdiction is `America/Bogota` and its clients carry RUC and
 * DNI. The two amounts have different currencies, so giving them one formatter would
 * mean one of them is always mislabelled. The inconsistency is in the data, not in
 * the formatting, and it is recorded in ADR-056 rather than hidden here.
 *
 * Amounts arrive as decimal strings and are parsed at the last moment, so nothing
 * upstream holds a float that has already lost a cent.
 */
export function formatMoneyCOP(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const amount = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(amount)) return "—";
  return amount.toLocaleString("es-CO", {
    style: "currency",
    currency: "COP",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** A decimal rate as a percentage: `0.1900` becomes `19 %`. */
export function formatRate(value: string | null | undefined): string {
  if (!value) return "0 %";
  const rate = Number(value);
  if (Number.isNaN(rate)) return "0 %";
  return `${rate * 100} %`;
}

export function invoiceStatusLabel(status: string): string {
  switch (status) {
    case "borrador":
      return "Borrador";
    case "emitida":
      return "Emitida";
    case "pagada":
      return "Pagada";
    case "anulada":
      return "Anulada";
    default:
      return humanise(status);
  }
}

export function invoiceStatusTone(status: string): Tone {
  switch (status) {
    case "pagada":
      return "forest";
    case "emitida":
      return "brass";
    case "anulada":
      return "wax";
    default:
      return "neutral";
  }
}

export function paymentMethodLabel(method: string): string {
  switch (method) {
    case "efectivo":
      return "Efectivo";
    case "transferencia":
      return "Transferencia";
    case "tarjeta":
      return "Tarjeta";
    case "cheque":
      return "Cheque";
    default:
      return humanise(method);
  }
}

