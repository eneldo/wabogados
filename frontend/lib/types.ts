/**
 * Types mirroring the backend response contracts.
 *
 * These are hand-written rather than generated. The cost is that a backend
 * change can drift silently, so every field the UI actually reads is asserted
 * at the call site in `api.ts` instead of being cast blindly.
 */

export type ApiError = {
  status: number;
  message: string;
  code?: string;
  details?: unknown;
};

export type SessionProfile = {
  id: string;
  email: string;
  fullName: string;
  roles: string[];
  permissions: string[];
};

export type LoginResult = {
  accessToken: string;
  refreshToken: string;
};

export type DashboardKpis = {
  active_clients: number;
  active_cases: number;
  closed_cases: number;
  active_lawyers: number;
  actions_this_month: number;
  upcoming_hearings: number;
  pending_actions: number;
  open_deadlines: number;
  overdue_deadlines: number;
  evidences: number;
  pending_messages: number;
  unread_notifications: number;
};

export type DashboardCase = {
  id: string;
  case_number: string;
  title: string;
  status: string;
  priority: string;
  client_name: string;
  opened_at: string;
};

export type DashboardHearing = {
  id: string;
  event_id: string;
  case_id: string;
  title: string;
  starts_at: string;
  status: string;
  court: string | null;
  courtroom: string | null;
  procedural_stage: string | null;
};

export type DashboardDeadline = {
  source: string;
  reference_id: string;
  case_id: string;
  title: string;
  due_at: string;
  is_overdue: boolean;
};

export type DashboardDocument = {
  id: string;
  case_id: string;
  title: string;
  document_type: string;
  status: string;
  created_at: string;
};

export type DashboardEvidence = {
  id: string;
  case_id: string;
  title: string;
  evidence_type: string;
  status: string;
  created_at: string;
};

export type DashboardPayload = {
  view: "administrador" | "abogado" | "cliente";
  generated_at: string;
  kpis: DashboardKpis;
  cases: DashboardCase[];
  next_hearing: DashboardHearing | null;
  hearings: DashboardHearing[];
  deadlines: DashboardDeadline[];
  recent_actions: Array<{
    id: string;
    case_id: string;
    action_type: string;
    description: string;
    occurred_at: string;
    next_action: string | null;
    next_action_at: string | null;
  }>;
  documents: DashboardDocument[];
  evidences: DashboardEvidence[];
};

export type EvidenceFile = {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  sha256: string;
  width: number | null;
  height: number | null;
  page_count: number | null;
  is_original: boolean;
  is_signed_pdf: boolean;
  signature_broken: boolean;
  created_at: string;
};

export type EvidenceDerivative = {
  id: string;
  derivative_type: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  compression_ratio: number | null;
  profile: string | null;
  width: number | null;
  height: number | null;
  page_count: number | null;
  created_at: string;
};

export type Evidence = {
  id: string;
  case_id: string;
  case_number: string;
  action_id: string | null;
  title: string;
  description: string | null;
  evidence_type: string;
  status: string;
  visibility: string;
  confidentiality: string;
  original_filename: string | null;
  original_mime_type: string | null;
  original_size: number | null;
  original_sha256: string | null;
  is_signed_pdf: boolean;
  captured_at: string | null;
  captured_location: string | null;
  derivative_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type EvidenceDetail = Evidence & {
  files: EvidenceFile[];
  derivatives: EvidenceDerivative[];
};

export type EvidenceUploadResult = {
  evidence: EvidenceDetail;
  derivatives_created: number;
  queued: boolean;
  page_count: number | null;
  is_signed_pdf: boolean;
  signature_broken: boolean;
  detail: string | null;
};

export type CustodyEvent = {
  id: string;
  event_type: string;
  from_value: string | null;
  to_value: string | null;
  detail: string | null;
  actor_id: string | null;
  ip_address: string | null;
  created_at: string;
};

export type CustodyAccess = {
  id: string;
  access_type: string;
  user_id: string | null;
  ip_address: string | null;
  created_at: string;
};

export type Custody = {
  evidence_id: string;
  original_sha256: string | null;
  events: CustodyEvent[];
  accesses: CustodyAccess[];
};

export type ConversationSummary = {
  id: string;
  subject: string;
  case_id: string | null;
  case_number: string | null;
  client_id: string | null;
  conversation_type: "interna" | "cliente";
  status: "abierto" | "cerrado";
  last_message_at: string | null;
  last_message_preview: string | null;
  message_count: number;
  unread: number;
  participant_count: number;
  created_at: string;
  updated_at: string;
};

export type MessageAttachment = {
  id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  sender_name: string;
  body: string;
  is_system: boolean;
  sent_at: string;
  edited_at: string | null;
  deleted_at: string | null;
  attachments: MessageAttachment[];
};

export type ConversationParticipant = {
  id: string;
  user_id: string;
  display_name: string;
  role: string;
  joined_at: string;
  last_read_at: string | null;
  is_muted: boolean;
};

export type ThreadResponse = {
  conversation: ConversationSummary;
  participants: ConversationParticipant[];
  messages: Message[];
  unread: number;
};

export type ParticipantOption = {
  id: string;
  display_name: string;
  account_type: "personal" | "cliente";
  client_id: string | null;
};

export type Notification = {
  id: string;
  notification_type: string;
  title: string;
  body: string | null;
  entity: string | null;
  entity_id: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
};

export type UnreadSummary = {
  unread_messages: number;
  unread_notifications: number;
};

/* --- Administration ----------------------------------------------------- */

/**
 * What a server action reports back to the form that called it.
 *
 * `status: "ok"` is only ever returned after the backend confirmed the write.
 * The shape exists so no screen has to invent a success message of its own,
 * which is the failure mode this project keeps having to guard against.
 */
export type ActionState = {
  status: "idle" | "ok" | "error";
  message?: string;
  /** Field name to message, keyed on the backend's field names. */
  errors?: Record<string, string>;
};

export type ClientRecord = {
  id: string;
  client_type: "natural" | "juridica";
  document_type: "DNI" | "RUC" | "CE" | "PASSPORT" | "OTROS";
  document_number: string;
  full_name: string | null;
  legal_name: string | null;
  commercial_name: string | null;
  display_name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  notes: string | null;
  user_id: string | null;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedClients = {
  items: ClientRecord[];
  total: number;
  skip: number;
  limit: number;
};

export type LawyerRecord = {
  id: string;
  document_type: "DNI" | "RUC" | "CE" | "PASSPORT" | "OTROS";
  document_number: string;
  full_name: string;
  professional_card: string | null;
  email: string | null;
  phone: string | null;
  specialties: string[];
  status: "activo" | "inactivo" | "suspendido";
  photo_url: string | null;
  user_id: string | null;
  /** Names, not ids: the API flattens them on the way out. */
  legal_areas: string[];
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedLawyers = {
  items: LawyerRecord[];
  total: number;
  skip: number;
  limit: number;
};

export type LegalAreaOption = {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
};

export type CaseProcessType =
  | "civil"
  | "penal"
  | "laboral"
  | "administrativo"
  | "comercial"
  | "familia"
  | "tributario"
  | "arbitraje"
  | "otro";

export type CaseStatus = "abierto" | "en_tramitacion" | "suspendido" | "cerrado" | "archivado";

export type CasePriority = "baja" | "normal" | "alta" | "urgente";

export type CaseRecord = {
  id: string;
  case_number: string;
  title: string;
  client_id: string;
  client_name: string;
  responsible_lawyer_id: string | null;
  responsible_lawyer_name: string | null;
  legal_area_id: string | null;
  legal_area_name: string | null;
  process_type: CaseProcessType;
  jurisdiction: string | null;
  court: string | null;
  file_number: string | null;
  status: CaseStatus;
  priority: CasePriority;
  opened_at: string;
  closed_at: string | null;
  description: string | null;
  /** Decimal in the API. Serialised as a string so no cents are lost in JSON. */
  amount: string | number | null;
  notes: string | null;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedCases = {
  items: CaseRecord[];
  total: number;
  skip: number;
  limit: number;
};

export type CaseParty = {
  id: string;
  case_id: string;
  client_id: string | null;
  name: string;
  party_role: "demandante" | "demandado" | "contraparte" | "tercero";
  document_type: string | null;
  document_number: string | null;
  is_external: boolean;
  notes: string | null;
  created_at: string;
};

export type CaseCollaborator = {
  lawyer_id: string;
  lawyer_name: string;
  role: string;
  assigned_at: string;
};

/** One tab of the 360 view. `available: false` means the section has no data. */
export type CaseSection = {
  available: boolean;
  items: Array<Record<string, unknown>>;
};

export type Case360 = {
  case: CaseRecord;
  collaborators: CaseCollaborator[];
  parties: CaseParty[];
  history_entries: number;
  actuaciones: CaseSection;
  actuaciones_total: number;
  agenda: CaseSection;
  agenda_total: number;
  audiencias: CaseSection;
  audiencias_total: number;
  documentos: CaseSection;
  documentos_total: number;
  evidencias: CaseSection;
  evidencias_total: number;
  tareas: CaseSection;
  mensajes: CaseSection;
};

/** A case in the list. What the `client_id` and `lawyer_id` selects need. */
export type CaseOption = { id: string; label: string };

export type DocumentRecord = {
  id: string;
  case_id: string;
  case_number: string;
  document_type: string;
  title: string;
  description: string | null;
  status: string;
  confidentiality: string;
  visibility: string;
  current_version: number | null;
  version_count: number;
  legal_hold: boolean;
  legal_hold_reason: string | null;
  legal_hold_at: string | null;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentVersionRecord = {
  id: string;
  document_id: string;
  version_number: number;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  notes: string | null;
  is_current: boolean;
  tier: string;
  tiered_at: string | null;
  created_by: string | null;
  created_at: string;
};

export type DocumentDetail = DocumentRecord & {
  versions: DocumentVersionRecord[];
};

export type PaginatedDocuments = {
  items: DocumentRecord[];
  total: number;
  skip: number;
  limit: number;
};

export type CalendarEventType =
  | "audiencia"
  | "reunion"
  | "vencimiento"
  | "llamada"
  | "cita"
  | "recordatorio";

export type CalendarEventStatus = "programada" | "realizada" | "cancelada" | "aplazada";
export type CalendarVisibility = "interna" | "equipo" | "publicada";
export type CalendarView = "day" | "week" | "month";

export type CalendarEventRecord = {
  id: string;
  case_id: string;
  case_number: string;
  event_type: CalendarEventType;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  location: string | null;
  lawyer_id: string | null;
  lawyer_name: string | null;
  visibility: CalendarVisibility;
  status: CalendarEventStatus;
  reminder_minutes: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CalendarViewResponse = {
  view: CalendarView;
  start: string;
  end: string;
  total: number;
  events: CalendarEventRecord[];
};

export type HearingStatus =
  | "programada"
  | "realizada"
  | "aplazada"
  | "cancelada"
  | "suspendida";

export type HearingRecord = {
  id: string;
  event_id: string;
  case_id: string;
  case_number: string;
  title: string;
  starts_at: string;
  ends_at: string;
  status: HearingStatus;
  attendance: "pendiente" | "presente" | "ausente" | "justificada";
  court: string | null;
  courtroom: string | null;
  judge: string | null;
  procedural_stage:
    | "primera_instancia"
    | "apelacion"
    | "ejecucion"
    | "previa"
    | "conciliacion"
    | "otra";
  file_number: string | null;
  notified_at: string | null;
  result: string | null;
  rescheduled_from_id: string | null;
  reschedule_count: number;
  is_active: boolean;
  updated_at: string;
};

export type DeadlineRecord = {
  source: "evento" | "actuacion";
  reference_id: string;
  case_id: string;
  case_number: string;
  title: string;
  due_at: string;
  overdue: boolean;
  source_label: string;
};

/**
 * Identity and access.
 *
 * `roles` and `permissions` are already flattened to names by the backend: the
 * authorization payload is computed in `UserResponse`, so the screen never has
 * to walk a role's permission list to decide what to render.
 */
export type AdminUserRecord = {
  id: string;
  email: string;
  full_name: string | null;
  is_superuser: boolean;
  is_verified: boolean;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  roles: string[];
  permissions: string[];
};

export type PaginatedUsers = {
  items: AdminUserRecord[];
  total: number;
  skip: number;
  limit: number;
};

export type RoleRecord = {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  created_at: string;
};

export type PermissionRecord = {
  id: string;
  name: string;
  resource: string;
  action: string;
  description: string | null;
};

export type AuditLogRecord = {
  id: string;
  user_id: string | null;
  /** Null when the request carried no readable token: an anonymous failure. */
  user_email: string | null;
  /** `"POST /api/v1/admin/users"` — verb and path, as the middleware records it. */
  action: string;
  entity: string;
  entity_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  result: "success" | "error" | string;
  created_at: string;
};

export type PaginatedAuditLogs = {
  items: AuditLogRecord[];
  total: number;
  skip: number;
  limit: number;
};

/**
 * One row of `system_settings`.
 *
 * `value` is the stored text run through the backend's JSON decode, so a setting
 * holding `30` arrives as a number and one holding `America/Bogota` arrives as a
 * string. `raw_value` is the same row without the decoding, and it is what the
 * editor shows: an administrator must be able to see and change exactly the bytes
 * that are stored, not a value the browser has already reinterpreted.
 */
export type SettingRecord = {
  key: string;
  value: unknown;
  raw_value: string;
  description: string | null;
  category: string;
  /** ISO 8601. A string, not a `Date`: it crosses the server/client boundary. */
  updated_at: string;
};

export type ConsultationStatus =
  | "nueva"
  | "en_revision"
  | "atendida"
  | "convertida"
  | "descartada";

export type ConsultationRecord = {
  id: string;
  full_name: string;
  phone: string;
  email: string;
  area: string;
  message: string;
  status: ConsultationStatus;
  consent_at: string;
  privacy_notice_version: string;
  handled_by: string | null;
  handled_at: string | null;
  client_id: string | null;
  internal_notes: string | null;
  created_at: string;
};

export type PaginatedConsultations = {
  items: ConsultationRecord[];
  total: number;
  skip: number;
  limit: number;
};

export type MediaKind = "video" | "image" | "audio" | "document";
export type MediaStatus = "activo" | "archivado";
export type MediaConfidentiality = "interno" | "restringido" | "confidencial";

/**
 * One asset of the multimedia library.
 *
 * `kind` arrives from the server because the server decided it from the bytes. A
 * browser that renamed an MP4 to `.jpg` would have the row filed as a video anyway,
 * and `has_file` is what separates a resource that was registered from one whose
 * file actually arrived — two normal states, not an error.
 */
export type MediaRecord = {
  id: string;
  title: string;
  description: string | null;
  kind: MediaKind;
  status: MediaStatus;
  confidentiality: MediaConfidentiality;
  tags: string | null;
  original_filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  tier: string;
  duration_seconds: number | null;
  case_id: string | null;
  case_number: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  deleted_at: string | null;
  has_file: boolean;
};

export type PaginatedMedia = {
  items: MediaRecord[];
  total: number;
  skip: number;
  limit: number;
};

/** One field-level history entry of a media resource. */
export type MediaHistoryEntry = {
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  change_reason: string | null;
  created_at: string;
};

export type InvoiceStatus = "borrador" | "emitida" | "pagada" | "anulada";
export type PaymentMethod = "efectivo" | "transferencia" | "tarjeta" | "cheque";

/**
 * One invoice.
 *
 * Every amount arrives as a **string** on purpose. A bill that travels through the
 * browser as a float has already lost the cents it was issued with — `0.1 + 0.2` is
 * not `0.3` in binary — so the wire format keeps the decimal as text and only the
 * formatting step turns it into a number for display.
 *
 * `balance` and `paid_amount` are derived by the server from the payments. The
 * status follows them, and a screen that recomputed either would be able to
 * disagree with the ledger.
 */
export type InvoiceRecord = {
  id: string;
  number: string;
  client_id: string;
  client_name: string | null;
  case_id: string | null;
  case_number: string | null;
  status: InvoiceStatus;
  issued_at: string | null;
  due_at: string | null;
  tax_rate: string;
  subtotal: string;
  tax_amount: string;
  total: string;
  paid_amount: string;
  balance: string;
  notes: string | null;
  void_reason: string | null;
  voided_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  lines: InvoiceLineRecord[];
  payments: PaymentRecord[];
};

export type InvoiceLineRecord = {
  id: string;
  position: number;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
};

export type PaymentRecord = {
  id: string;
  amount: string;
  method: PaymentMethod;
  paid_at: string;
  reference: string | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
};

export type PaginatedInvoices = {
  items: InvoiceRecord[];
  total: number;
  skip: number;
  limit: number;
};

/** What is owed and how late, in the buckets an accountant asks for. */
export type AgingReport = {
  vigente: string;
  "1_30": string;
  "31_60": string;
  "61_90": string;
  mas_90: string;
};

// --- Legal AI -------------------------------------------------------------

export type LegalHitKind = "case" | "document" | "media";

export type LegalSearchHit = {
  kind: LegalHitKind;
  id: string;
  title: string;
  /** A window around the match, not the whole field. */
  excerpt: string;
  case_id: string | null;
  case_number: string | null;
  /** Higher is a better match. Opaque on purpose: `terms` is what explains it. */
  score: number;
};

export type LegalSearchResponse = {
  query: string;
  /** The words actually ranked on, after dropping stop words. */
  terms: string[];
  total: number;
  items: LegalSearchHit[];
};

export type LegalSummary = {
  kind: LegalHitKind;
  id: string;
  title: string;
  /** The source's own sentences, verbatim. Not paraphrased. */
  sentences: string[];
  /** Always `extractive`, and shown on screen: a summary that rewrites is a claim. */
  method: string;
  terms: string[];
};

/**
 * What a generation backend would need, and which of it is missing.
 *
 * The screen shows this instead of a prompt box. Naming the absences is more useful
 * than a disabled field, and it keeps the module honest that nothing calls a model.
 */
export type LegalProviderStatus = {
  provider: string | null;
  model: string | null;
  embeddings: boolean;
  vector_store: boolean;
  queue: boolean;
  available: boolean;
  missing: string[];
  app_name: string;
};
