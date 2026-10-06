/**
 * The upload pipeline as a model.
 *
 * MASTER_PROMPT section 39 asks the interface to show six steps. The backend
 * is synchronous: one POST validates, checks security, stores, optimises and
 * makes a preview, then answers. Two of those steps are therefore not
 * separately observable, and pretending otherwise would mean animating a
 * progress bar that is not reporting anything.
 *
 * The rule here is that a stage only advances when there is a reason to believe
 * it happened:
 *
 *   subiendo      real, from the upload's own byte counter
 *   validando     upload complete, response outstanding
 *   seguridad     the response arrived, so validation and the security check
 *                 both completed; a rejection jumps straight to `rechazado`
 *                 with the server's own sentence
 *   optimizando   the server queued work, or derivatives exist but no preview
 *   vista_previa  a preview derivative exists
 *   listo         the evidence reached the ready state
 */

export type Stage =
  | "inactivo"
  | "subiendo"
  | "validando"
  | "seguridad"
  | "optimizando"
  | "vista_previa"
  | "listo"
  | "rechazado";

export const STAGE_ORDER: readonly Stage[] = [
  "subiendo",
  "validando",
  "seguridad",
  "optimizando",
  "vista_previa",
  "listo",
] as const;

export const STAGE_LABEL: Record<Stage, string> = {
  inactivo: "En espera",
  subiendo: "Subiendo",
  validando: "Validando",
  seguridad: "Verificando seguridad",
  optimizando: "Optimizando",
  vista_previa: "Generando vista previa",
  listo: "Listo",
  rechazado: "Rechazado",
};

export const STAGE_NOTE: Record<Stage, string> = {
  inactivo: "",
  subiendo: "Transfiriendo el archivo al despacho",
  validando: "Comprobando el formato declarado y el contenido real",
  seguridad: "Descartando ejecutables, políglotos y dimensional anómalo",
  optimizando: "Generando las versiones derivadas",
  vista_previa: "Preparando la miniatura",
  listo: "La evidencia queda registrada y custodia abierta",
  rechazado: "",
};

export function stageIndex(stage: Stage): number {
  return STAGE_ORDER.indexOf(stage);
}

export function isTerminal(stage: Stage): boolean {
  return stage === "listo" || stage === "rechazado";
}

/** Bytes accepted by the evidence engine. Mirrors the backend setting. */
export const ACCEPTED_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/jpg",
  "image/webp",
  "image/tiff",
] as const;

export const ACCEPT_ATTRIBUTE = ".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff";

export const ACCEPTED_LABEL = "PDF, PNG, JPG, JPEG";

export function isAccepted(file: File): boolean {
  const byExtension = /\.(pdf|png|jpe?g|webp|tiff?)$/i.test(file.name);
  // The extension is only a hint. The backend decides from the content, and a
  // file that fails there is the file we want to show being rejected.
  return byExtension || (ACCEPTED_TYPES as readonly string[]).includes(file.type);
}

/** Map an evidence status onto the stage it implies. */
export function stageFromStatus(
  status: string,
  hasDerivatives: boolean,
  hasPreview: boolean,
): Stage {
  if (status === "quarantined" || status === "failed") return "rechazado";
  if (status === "ready" || status === "archived") return "listo";
  if (hasPreview) return "optimizando";
  if (hasDerivatives) return "optimizando";
  if (status === "processing" || status === "optimized") return "optimizando";
  if (status === "stored") return "seguridad";
  if (status === "validated") return "validando";
  return "subiendo";
}
