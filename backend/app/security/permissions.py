"""Canonical RBAC matrix and legal area catalogue for WABOGADOS V1.

This module is the single source of truth for permission identifiers, the
default role/permission mapping and the seeded legal areas. The migrations
mirror these definitions, so any change here must ship with a new reversible
migration.
"""

from typing import NamedTuple


class PermissionDefinition(NamedTuple):
    name: str
    resource: str
    action: str
    description: str


IDENTITY_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("users:read", "users", "read", "Consultar usuarios"),
    PermissionDefinition("users:create", "users", "create", "Crear usuarios"),
    PermissionDefinition("users:update", "users", "update", "Actualizar usuarios"),
    PermissionDefinition("users:delete", "users", "delete", "Desactivar usuarios"),
    PermissionDefinition(
        "users:assign_roles", "users", "assign_roles", "Asignar y revocar roles"
    ),
    PermissionDefinition("roles:read", "roles", "read", "Consultar roles"),
    PermissionDefinition("roles:manage", "roles", "manage", "Crear y modificar roles"),
    PermissionDefinition(
        "permissions:read", "permissions", "read", "Consultar el catálogo de permisos"
    ),
    PermissionDefinition("audit_logs:read", "audit_logs", "read", "Consultar auditoría"),
)

CLIENT_LAWYER_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("clients:read", "clients", "read", "Consultar clientes"),
    PermissionDefinition("clients:create", "clients", "create", "Registrar clientes"),
    PermissionDefinition("clients:update", "clients", "update", "Actualizar clientes"),
    PermissionDefinition("clients:delete", "clients", "delete", "Desactivar clientes"),
    PermissionDefinition("lawyers:read", "lawyers", "read", "Consultar abogados"),
    PermissionDefinition("lawyers:create", "lawyers", "create", "Registrar abogados"),
    PermissionDefinition("lawyers:update", "lawyers", "update", "Actualizar abogados"),
    PermissionDefinition("lawyers:delete", "lawyers", "delete", "Desactivar abogados"),
    PermissionDefinition("legal_areas:read", "legal_areas", "read", "Consultar áreas jurídicas"),
)

ROLE_DEFINITIONS: dict[str, str] = {
    "administrador": "Acceso general con permisos explícitos",
    "abogado": "Acceso a expedientes asignados o autorizados",
    "asistente": "Acceso operativo limitado según permisos",
    "cliente": "Acceso únicamente a información publicada y vinculada a su identidad",
}

CASE_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "cases:read_all", "cases", "read_all", "Consultar todos los expedientes"
    ),
    PermissionDefinition(
        "cases:read_assigned",
        "cases",
        "read_assigned",
        "Consultar expedientes asignados o autorizados",
    ),
    PermissionDefinition(
        "cases:read_published",
        "cases",
        "read_published",
        "Consultar únicamente lo publicado de sus propios expedientes",
    ),
    PermissionDefinition("cases:create", "cases", "create", "Abrir expedientes"),
    PermissionDefinition("cases:update", "cases", "update", "Actualizar expedientes"),
    PermissionDefinition("cases:close", "cases", "close", "Cerrar y archivar expedientes"),
    PermissionDefinition(
        "cases:assign", "cases", "assign", "Asignar abogados y partes"
    ),
)

ACTION_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("actions:read", "actions", "read", "Consultar actuaciones"),
    PermissionDefinition(
        "actions:read_published",
        "actions",
        "read_published",
        "Consultar únicamente actuaciones publicadas",
    ),
    PermissionDefinition("actions:create", "actions", "create", "Registrar actuaciones"),
    PermissionDefinition("actions:update", "actions", "update", "Actualizar actuaciones"),
)

CALENDAR_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("calendar:read", "calendar", "read", "Consultar la agenda"),
    PermissionDefinition(
        "calendar:read_published",
        "calendar",
        "read_published",
        "Consultar únicamente los eventos publicados de sus expedientes",
    ),
    PermissionDefinition("calendar:create", "calendar", "create", "Registrar eventos"),
    PermissionDefinition("calendar:update", "calendar", "update", "Actualizar eventos"),
    PermissionDefinition("hearings:read", "hearings", "read", "Consultar audiencias"),
    PermissionDefinition("hearings:create", "hearings", "create", "Registrar audiencias"),
    PermissionDefinition("hearings:update", "hearings", "update", "Registrar el resultado"),
    PermissionDefinition(
        "hearings:reschedule",
        "hearings",
        "reschedule",
        "Programar o reprogramar audiencias",
    ),
)

DOCUMENT_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("documents:read", "documents", "read", "Consultar documentos"),
    PermissionDefinition(
        "documents:read_published",
        "documents",
        "read_published",
        "Consultar únicamente los documentos publicados de sus expedientes",
    ),
    PermissionDefinition("documents:create", "documents", "create", "Registrar documentos"),
    PermissionDefinition(
        "documents:update", "documents", "update", "Actualizar los metadatos del documento"
    ),
    PermissionDefinition(
        "documents:download", "documents", "download", "Descargar el contenido de un documento"
    ),
    PermissionDefinition(
        "documents:legal_hold",
        "documents",
        "legal_hold",
        "Activar o levantar la retención legal que congela la política de versiones",
    ),
    PermissionDefinition(
        "documents:retention",
        "documents",
        "retention",
        "Consultar y ejecutar la política de retención de versiones",
    ),
)

LEGAL_AREAS: tuple[tuple[str, str], ...] = (
    ("Civil", "Derecho civil y obligaciones"),
    ("Penal", "Derecho penal y defensa"),
    ("Laboral", "Derecho laboral y contratos de trabajo"),
    ("Comercial", "Derecho comercial y societario"),
    ("Familia", "Derecho de familia y sucesiones"),
    ("Tributario", "Derecho tributario y fiscal"),
    ("Administrativo", "Derecho administrativo y procedimientos"),
    ("Internacional", "Derecho internacional y comercio exterior"),
    ("Procesal", "Derecho procesal y estrategia de litigio"),
    ("Inmobiliario", "Derecho inmobiliario y notarial"),
    ("Bancario", "Derecho financiero y bancario"),
    ("Ambiental", "Derecho ambiental"),
)

STAFF_LAWYER_PERMISSIONS: tuple[str, ...] = (
    "clients:read",
    "clients:create",
    "clients:update",
    "lawyers:read",
    "legal_areas:read",
)

LAWYER_CASE_PERMISSIONS: tuple[str, ...] = (
    "cases:read_assigned",
    "cases:create",
    "cases:update",
    "cases:assign",
)

ASSISTANT_CASE_PERMISSIONS: tuple[str, ...] = (
    "cases:read_all",
    "cases:create",
    "cases:update",
    "cases:assign",
)

STAFF_ACTION_PERMISSIONS: tuple[str, ...] = (
    "actions:read",
    "actions:create",
    "actions:update",
)

STAFF_CALENDAR_PERMISSIONS: tuple[str, ...] = (
    "calendar:read",
    "calendar:create",
    "calendar:update",
    "hearings:read",
    "hearings:create",
    "hearings:update",
)

STAFF_DOCUMENT_PERMISSIONS: tuple[str, ...] = (
    "documents:read",
    "documents:create",
    "documents:update",
    "documents:download",
)

# Retention is an infrastructure decision, not a case level one: a single
# archive run touches every case in the firm, so it stays with the administrator.
ADMINISTRATOR_RETENTION_PERMISSIONS: tuple[str, ...] = (
    "documents:legal_hold",
    "documents:retention",
)

# Resource names are the English form of the Spanish names in MASTER_PROMPT
# section 32 (`evidencias.view` -> `evidences:view`), consistent with `cases:`,
# `documents:` and `actions:`.
EVIDENCE_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "evidences:view", "evidences", "view", "Consultar evidencias"
    ),
    PermissionDefinition(
        "evidences:create", "evidences", "create", "Registrar una evidencia"
    ),
    PermissionDefinition(
        "evidences:upload", "evidences", "upload", "Cargar el archivo original de una evidencia"
    ),
    PermissionDefinition(
        "evidences:download_original",
        "evidences",
        "download_original",
        "Descargar el archivo original inmutable",
    ),
    PermissionDefinition(
        "evidences:download_optimized",
        "evidences",
        "download_optimized",
        "Descargar una versión derivada para consulta",
    ),
    PermissionDefinition(
        "evidences:update",
        "evidences",
        "update",
        "Editar los metadatos de una evidencia",
    ),
    PermissionDefinition(
        "evidences:publish_to_client",
        "evidences",
        "publish_to_client",
        "Publicar una evidencia para que el cliente la vea",
    ),
    PermissionDefinition(
        "evidences:classify",
        "evidences",
        "classify",
        "Clasificar y etiquetar una evidencia",
    ),
    PermissionDefinition(
        "evidences:archive", "evidences", "archive", "Archivar una evidencia"
    ),
    PermissionDefinition(
        "evidences:audit",
        "evidences",
        "audit",
        "Consultar la cadena de custodia y los accesos",
    ),
    PermissionDefinition(
        "evidences:view_published",
        "evidences",
        "view_published",
        "Consultar únicamente las evidencias publicadas de sus expedientes",
    ),
)

# `hearings:reschedule` is intentionally absent from the staff list: only the
# administrator reschedules a hearing because the date comes from the court.

# The client only ever sees what the firm has explicitly published, and only
# inside the cases that belong to their own identity. Publishing a document does
# not grant file download: that stays with the firm.
CLIENT_CASE_PERMISSIONS: tuple[str, ...] = ("cases:read_published",)
CLIENT_READ_PERMISSIONS: tuple[str, ...] = (
    "actions:read_published",
    "calendar:read_published",
    "documents:read_published",
    "evidences:view_published",
    "messages:read",
    "messages:send",
    "notifications:read",
)

# Staff can file and read evidence inside their assigned cases. Downloading the
# original is a deliberate separate decision: an original download is a custody
# event, not a convenience.
STAFF_EVIDENCE_PERMISSIONS: tuple[str, ...] = (
    "evidences:view",
    "evidences:create",
    "evidences:upload",
    "evidences:download_original",
    "evidences:download_optimized",
    "evidences:update",
    "evidences:publish_to_client",
    "evidences:classify",
    "evidences:archive",
)

# Archiving an evidence and reading the full custody trail are administrative.
ADMINISTRATOR_EVIDENCE_PERMISSIONS: tuple[str, ...] = ("evidences:audit",)

MESSAGE_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "messages:read", "messages", "read", "Leer conversaciones en las que participa"
    ),
    PermissionDefinition(
        "messages:send", "messages", "send", "Enviar mensajes en una conversación"
    ),
    PermissionDefinition(
        "messages:create_conversation",
        "messages",
        "create_conversation",
        "Abrir una conversación",
    ),
    PermissionDefinition(
        "messages:attach", "messages", "attach", "Adjuntar archivos a un mensaje"
    ),
    PermissionDefinition(
        "messages:archive",
        "messages",
        "archive",
        "Archivar un mensaje propio (el registro se conserva)",
    ),
    PermissionDefinition(
        "messages:manage_participants",
        "messages",
        "manage_participants",
        "Añadir o quitar participantes de una conversación",
    ),
    PermissionDefinition(
        "notifications:read", "notifications", "read", "Consultar las notificaciones propias"
    ),
    PermissionDefinition(
        "notifications:send",
        "notifications",
        "send",
        "Enviar notificaciones a otro usuario",
    ),
)

SETTINGS_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "settings:read", "settings", "read", "Consultar los ajustes del sistema"
    ),
    PermissionDefinition(
        "settings:write", "settings", "write", "Modificar los ajustes del sistema"
    ),
    PermissionDefinition(
        "metrics:read", "metrics", "read", "Consultar las métricas de operación"
    ),
)


# Dashboards read the same rows the rest of the application exposes, so the
# permission gates access to the aggregate, not to new data. Every role gets it:
# the figures differ by scope, not by whether the endpoint is reachable.
DASHBOARD_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "dashboard:read", "dashboard", "read", "Consultar el panel propio"
    ),
)


# A client may take part in a conversation, but may not open one, attach a file
# or remove a message. A portal is a channel to the firm, not a workplace.
CLIENT_MESSAGE_PERMISSIONS: tuple[str, ...] = (
    "messages:read",
    "messages:send",
    "notifications:read",
    "dashboard:read",
)

STAFF_MESSAGE_PERMISSIONS: tuple[str, ...] = (
    "messages:read",
    "messages:send",
    "messages:create_conversation",
    "messages:attach",
    "messages:archive",
    "messages:manage_participants",
    "notifications:read",
    "notifications:send",
)

STAFF_DASHBOARD_PERMISSIONS: tuple[str, ...] = ("dashboard:read",)

# The client sees that a published evidence exists and may fetch its
# consultation derivative. The original stays with the firm: downloading it
# would expose material the firm never agreed to hand over.
CLIENT_EVIDENCE_PERMISSIONS: tuple[str, ...] = (
    "evidences:view_published",
    "evidences:download_optimized",
)

# A consultation request arrives from the public site with no credentials, so
# reading and working it is a separate grant: the intake is open, the file is
# not. A lawyer takes the case; an assistant triages it; an administrator
# configures and, when a person exercises their right to erasure, removes it.
CONSULTATION_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "consultations:read", "consultations", "read", "Consultar solicitudes de consulta"
    ),
    PermissionDefinition(
        "consultations:update",
        "consultations",
        "update",
        "Actualizar el estado de una solicitud",
    ),
    PermissionDefinition(
        "consultations:erase",
        "consultations",
        "erase",
        "Eliminar solicitudes por petición del titular",
    ),
)

# Every role that can answer a phone can answer a request that arrived through
# the form. The client role does not: these rows belong to nobody yet.
STAFF_CONSULTATION_PERMISSIONS: tuple[str, ...] = (
    "consultations:read",
    "consultations:update",
)

# The multimedia library (MASTER_PROMPT V4, "Videos y biblioteca").
#
# It is an **internal** collection of the firm, not a case-scoped resource and not
# something the portal publishes: a video of an inspection or a deposition is firm
# material, and the client role therefore gets nothing here. That is deliberate
# and it is what makes the single `media:read` grant safe — ADR-045 says a
# permission without a scope is a leak, and the scope of this resource is "inside
# the firm" rather than "inside a case".
#
# Reading and playing are separate grants because they are not the same act: a
# profile may catalogue material without being allowed to stream it to a
# browser, which is the difference between an archive and a distribution channel.
MEDIA_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "media:read", "media", "read", "Consultar la biblioteca multimedia"
    ),
    PermissionDefinition(
        "media:create", "media", "create", "Registrar un recurso en la biblioteca"
    ),
    PermissionDefinition(
        "media:upload", "media", "upload", "Cargar el archivo de un recurso"
    ),
    PermissionDefinition(
        "media:update", "media", "update", "Editar los datos de un recurso"
    ),
    PermissionDefinition(
        "media:download", "media", "download", "Descargar o reproducir un recurso"
    ),
    PermissionDefinition(
        "media:delete", "media", "delete", "Desactivar un recurso de la biblioteca"
    ),
)

# A lawyer and an assistant work the library; neither may take a row out of it.
# Deactivation stays with the administrator, like every other `:delete` in the
# project, because it is the axis nobody can undo from the screen.
STAFF_MEDIA_PERMISSIONS: tuple[str, ...] = (
    "media:read",
    "media:create",
    "media:upload",
    "media:update",
    "media:download",
)

#: Everything an administrator may do with a stored file, whoever uploaded it.
ADMINISTRATOR_MEDIA_PERMISSIONS: tuple[str, ...] = ("media:delete",)

# Billing (MASTER_PROMPT V3, "Honorarios, pagos y cuentas").
#
# **The client role gets nothing.** A firm's invoice is not published to the portal
# in this scope, and the client already receives what concerns them through the
# consultation and case surfaces. Granting `invoices:read` to a client would be a
# leak with a decimal point on it: `total` exposes what the matter is worth to
# whoever is on the other side of it.
#
# Issuing and voiding are separate on purpose. Issuing says the firm is asking for
# money, which is a day-to-day act; voiding says a number that already exists was
# wrong, and that stays with the administrator for the same reason deactivation does
# everywhere else in the project.
BILLING_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("invoices:read", "invoices", "read", "Consultar facturas"),
    PermissionDefinition(
        "invoices:create", "invoices", "create", "Registrar una factura"
    ),
    PermissionDefinition("invoices:update", "invoices", "update", "Editar una factura"),
    PermissionDefinition(
        "invoices:issue", "invoices", "issue", "Emitir una factura al cliente"
    ),
    PermissionDefinition(
        "invoices:void", "invoices", "void", "Anular una factura emitida"
    ),
    PermissionDefinition(
        "payments:read", "payments", "read", "Consultar pagos registrados"
    ),
    PermissionDefinition(
        "payments:create", "payments", "create", "Registrar un pago recibido"
    ),
)

#: Drafting an invoice, recording a payment and reading the ledger is the daily work
#: of whoever handles the front desk.
STAFF_BILLING_PERMISSIONS: tuple[str, ...] = (
    "invoices:read",
    "invoices:create",
    "invoices:update",
    "payments:read",
    "payments:create",
)

#: Issuing and voiding stay with the administrator.
ADMINISTRATOR_BILLING_PERMISSIONS: tuple[str, ...] = (
    "invoices:issue",
    "invoices:void",
)

# Legal AI (MASTER_PROMPT V5).
#
# **There is no provider behind these permissions**, and that is not an oversight to
# be papered over: the project has no model, no key and no vector store (ADR-057).
# What the permissions guard is the half that is real — searching the firm's own
# classified material and producing an extractive summary of it — and both are
# reads. A generate permission does not exist because there is nothing behind it, and
# inventing one would be a permission for a feature that answers with fiction.
AI_PERMISSIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "ai:search", "ai", "search", "Buscar en el material de la firma"
    ),
    PermissionDefinition(
        "ai:summarize", "ai", "summarize", "Resumir un documento o expediente"
    ),
)

#: Reading the index is as safe as reading the modules it covers: every hit is a
#: row the caller could already reach through its own screen. No generate grant.
STAFF_AI_PERMISSIONS: tuple[str, ...] = ("ai:search", "ai:summarize")


ADMINISTRATOR_PERMISSIONS: tuple[str, ...] = tuple(
    definition.name
    for definition in (
        *IDENTITY_PERMISSIONS,
        *CLIENT_LAWYER_PERMISSIONS,
        *CASE_PERMISSIONS,
        *ACTION_PERMISSIONS,
        *CALENDAR_PERMISSIONS,
        *DOCUMENT_PERMISSIONS,
        *EVIDENCE_PERMISSIONS,
        *MESSAGE_PERMISSIONS,
        *DASHBOARD_PERMISSIONS,
        *SETTINGS_PERMISSIONS,
        *CONSULTATION_PERMISSIONS,
        *MEDIA_PERMISSIONS,
        *BILLING_PERMISSIONS,
        *AI_PERMISSIONS,
    )
)

ROLE_PERMISSION_MATRIX: dict[str, tuple[str, ...]] = {
    "administrador": ADMINISTRATOR_PERMISSIONS,
    "abogado": STAFF_LAWYER_PERMISSIONS
    + LAWYER_CASE_PERMISSIONS
    + STAFF_ACTION_PERMISSIONS
    + STAFF_CALENDAR_PERMISSIONS
    + STAFF_DOCUMENT_PERMISSIONS
    + STAFF_EVIDENCE_PERMISSIONS
    + ADMINISTRATOR_EVIDENCE_PERMISSIONS
    + STAFF_MESSAGE_PERMISSIONS
    + STAFF_DASHBOARD_PERMISSIONS
    + STAFF_CONSULTATION_PERMISSIONS
    + STAFF_MEDIA_PERMISSIONS
    + STAFF_BILLING_PERMISSIONS
    + STAFF_AI_PERMISSIONS,
    "asistente": STAFF_LAWYER_PERMISSIONS
    + ASSISTANT_CASE_PERMISSIONS
    + STAFF_ACTION_PERMISSIONS
    + STAFF_CALENDAR_PERMISSIONS
    + STAFF_DOCUMENT_PERMISSIONS
    + STAFF_EVIDENCE_PERMISSIONS
    + STAFF_MESSAGE_PERMISSIONS
    + STAFF_DASHBOARD_PERMISSIONS
    + STAFF_CONSULTATION_PERMISSIONS
    + STAFF_MEDIA_PERMISSIONS
    + STAFF_BILLING_PERMISSIONS
    + STAFF_AI_PERMISSIONS,
    "cliente": CLIENT_CASE_PERMISSIONS
    + CLIENT_READ_PERMISSIONS
    + CLIENT_EVIDENCE_PERMISSIONS
    + CLIENT_MESSAGE_PERMISSIONS,
}


def get_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return (
        *IDENTITY_PERMISSIONS,
        *CLIENT_LAWYER_PERMISSIONS,
        *CASE_PERMISSIONS,
        *ACTION_PERMISSIONS,
        *CALENDAR_PERMISSIONS,
        *DOCUMENT_PERMISSIONS,
        *EVIDENCE_PERMISSIONS,
        *MESSAGE_PERMISSIONS,
        *DASHBOARD_PERMISSIONS,
        *SETTINGS_PERMISSIONS,
        *CONSULTATION_PERMISSIONS,
        *MEDIA_PERMISSIONS,
        *BILLING_PERMISSIONS,
        *AI_PERMISSIONS,
    )


def get_role_definitions() -> dict[str, str]:
    return ROLE_DEFINITIONS


def get_permissions_for_role(role_name: str) -> tuple[str, ...]:
    return ROLE_PERMISSION_MATRIX.get(role_name, ())


def get_legal_areas() -> tuple[tuple[str, str], ...]:
    return LEGAL_AREAS
