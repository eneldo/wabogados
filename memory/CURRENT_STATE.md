# CURRENT STATE

## Working
- Backend FastAPI 0.116+ with Python 3.12
- SQLAlchemy 2 async + asyncpg
- Pydantic v2 settings
- Alembic migrations applied through **b2c3d4e5f6a7** (media access logs). The
  2026-10-06 audit added `a1b2c3d4e5f6` (`evidences:update`, which the router
  required and the catalogue never had) and `b2c3d4e5f6a7` (`media_access_logs`).
  All three new revisions were verified with `downgrade` + `upgrade`.
- Health endpoints: /api/v1/health/live (liveness), /api/v1/health/ready (readiness with DB check)
- Uniform error responses (404, 409, 422, 503)
- pytest: **810 passing tests, 86.95% coverage** (target >=80%), **zero warnings**
- Ruff and mypy strict **clean**, and reproducible: the ceilings in
  `pyproject.toml` are pinned to what was measured (`ruff>=0.12,<0.13`,
  `mypy>=1.17,<1.18`, `sqlalchemy>=2.1,<2.2`) and the `dev` extra declares the
  type stubs (`types-passlib`, `types-python-jose`) without which a clean install
  could not pass the gate. The SQLAlchemy 2.1 typing work reduced 33 errors to
  zero by fixing one root cause. See `NEXT_STEPS.md` and ADR-063
- Dockerfile (non-root, cap_drop ALL, no-new-privileges)
- Frontend Next.js 16 + React 19 + TypeScript strict + Tailwind 4
- Status page consuming /api/v1/health/ready server-side
- ESLint clean, tsc --noEmit clean, next build successful
- **Session with httpOnly cookies; the access token never reaches browser JS**
- Token renewal in `proxy.ts`, before rendering, never inside a render
- **Client panel**: processes, hearings, deadlines, published documents,
  visible evidence and a thread with the firm
- **Evidence manager**: card and table views, thumbnails, drag and drop with the
  six stage rail of section 39, custody drawer
- Downloads stream through a route handler so no token ever appears in a URL
- Client isolation verified over HTTP: a client sees their own case and gets 404
- **Case scope is enforced on every router whose resource relates to `Case`**:
  actions, billing, calendar, cases, dashboard, documents, evidences, legal_ai,
  media. The eight that do not carry `get_user_scope` (admin, admin_metrics,
  admin_settings, auth, clients, consultations, health, lawyers) were reviewed
  one by one and are correct: firm-wide masters with no relation to `Case`.
  **`messages.py` is the one exception still open** — see `NEXT_STEPS.md`.
  for anyone else's
- **Public site at `/`** built from `WABOGADOS_web.html`: petrol blue, gold and
  ivory, with the reference's section order and proportions
- Corporate palette lives beside the portal's document palette, on purpose
- Login routes by role: a client to `/portal`, staff to `/expedientes`
- Nothing invented on the public site: photographs, names, addresses, phones
  and credentials are marked pending, and the contact form declares it sends
  nothing
- Public site uses a fluid `clamp()` type scale and scroll reveals keyed on
  `html.js`, so no animation is ever able to hide content
- **Responsive from 320 to 3840px, measured rather than eyeballed**: no
  horizontal overflow at nine device sizes, `.site-canvas` equal to the viewport
  at all of them, usable content 270 → 1496px, grids closing square, hero title
  39 → 65px
- Single fluid measure `width: 100%; max-width: 1560px`. An earlier ladder of five
  container tiers plus large-screen type overrides was reverted: it made the page
  worse
- `public-site.css` was truncated to 24 lines by a bad scripted edit and rebuilt
  from the compiled stylesheet of the last good build; it must be written as UTF-8
  **without BOM**, because a BOM makes the parser fold the first comment and the
  first selector into one invalid selector and drop the rule silently
- The header condenses, marks the section being read and shows a reading-progress
  bar, all from one rAF on a passive listener
- Hero illustration carries a parallax written as `--site-parallax`, not React
  state, and is off under reduced motion and on coarse pointers
- **Public site paints the full viewport width with `.site-canvas`; the portal and
  login keep the document paper, and no route overflows horizontally**
- **The firm's real identity is on the public site**, verified against
  wabogados.co: three professionals with names, roles and photographs, the seven
  practice areas the firm lists, its published address, phone and opening hours,
  the Santander quote, and its two allied marks
- Team photographs recovered from `WABOGADOS_recursos` and served from
  `frontend/public/equipo` and `frontend/public/aliados`
- **Administration portal** at `/admin` with a fixed rail and twelve modules in
  three states: ready, building (API exists, screens pending) and planned
  (Multimedial, IA Jurídica and Facturación, forbidden by `MASTER_PROMPT.md`, so
  they render inert with a reason)
- Dashboard, Clientes, Abogados, **Expedientes** and **Agenda** are built; the session guard
  lives in the layout rather than in each page
- **Expedientes**: listing with search and filters, creation drawer, 360 record
  built on `GET /cases/{id}/360` with per-section counts, closure with date and
  note, lawyer incorporation and party creation
- **Agenda**: day, week and month views with temporal navigation and filters;
  generic events, deadlines and the full hearing cycle (creation, record and
  traced rescheduling) through Server Actions. Generic calendar endpoints cannot
  bypass hearing rules. Dates are read and written in `America/Bogota`
- **Seguridad** at `/admin/seguridad`, three views driven by `?vista=`:
  usuarios (directory with search, role and state filters, create and edit
  dialogs, roles dialog, deactivate/reactivate), roles (the four roles with the
  permissions each grants, plus the whole catalogue grouped by resource) and
  auditoría (`GET /admin/audit-logs` paginated, filters by text, result and
  actor). Every tab is gated on its own permission and the rail entry is
  `users:read`
- **Centro multimedia** at `/admin/multimedia` (MASTER_PROMPT V4, construido el
  2026-10-03 anulando la prohibición del brief, ADR-055): biblioteca **interna** de
  la firma con vídeo, imagen, audio y PDF. `media_items` es un dominio aparte del
  motor de evidencias —sin inmutabilidad, derivados ni custodia— y
  `EVIDENCE_MIME_TYPES` sigue sin aceptar `video/*`
- **El tipo de un recurso lo deciden los bytes.** `kind` decide si el navegador
  ofrece un `<video>`, así que se detecta por la cabecera y no se acepta del
  cliente; `RIFF` se resuelve por su tipo en el offset 8 porque es un contenedor
- **Registrar y subir son dos llamadas**, porque un recurso puede existir sin
  archivo y ese estado es normal; `has_file` separa los dos
- **`DELETE /media/{id}` desactiva y deja el archivo**: una fila desactivada sin
  sus bytes no se podría reactivar, que es la razón de la regla de no borrar
- **Una ruta de streaming propia** (`/api/media/[id]`) en vez del proxy
  compartido, que lee el cuerpo con `text()` y aplana lo que un reproductor
  necesita por partes. `Range` se reenvía tal cual y el estado se copia, para que
  un `206` llegue como `206` y un `416` como `416`
- **`apiFetch` pasa un `FormData` intacto y sin `Content-Type`**: el navegador
  tiene que escribir el límite multipart y una cabecera puesta aquí lo deja
  ilegible
- **Una utilidad de Tailwind no puede ganar a `globals.css`.** `text-right` en la
  cabecera de «Acciones» no funcionaba en ninguno de los siete listados porque la
  hoja va sin capas; se corrigió con una regla `.ledger thead th.text-right`
- **El chunk de CSS del servidor de desarrollo se queda cacheado**: una regla
  nueva en `globals.css` puede no aparecer aunque el build de producción la tenga.
  Ante «mi CSS no se aplica», comparar el CSS servido con el compilado antes de
  culpar a la regla
- **La base de pruebas persiste entre invocaciones.** `docker compose run --rm
  test` reutiliza el contenedor `postgres-test`, así que una migración ya aplicada
  no se vuelve a aplicar: una concesión corregida en el código sigue en la base
  porque el `INSERT ... ON CONFLICT DO NOTHING` no la revierte. Recrear
  `postgres-test` es parte de corregir un fallo de permisos
- **Configuración** at `/admin/configuracion`: `system_settings` grouped by
  category, create and edit dialogs, delete by key with a confirmation, and the
  value column shows the stored text while a `tipo` chip names what it will be
  read back as. **The only screen in the administration with a delete button**,
  and the copy says why: a setting is not a legal record, and the previous value
  stays in `change_logs`
- **La fila del ledger se alinea a la izquierda por hoja, no por marcado.**
  `<th scope="row">` es un `th`, y la hoja del navegador centra todos los `th`; la
  regla existente solo corregía `thead`, así que en columnas anchas el texto
  flotaba en el centro. Una regla `.ledger tbody th` lo arregla en los ocho
  listados de una vez
- **`admin.py` had no `session.commit()` anywhere**: all five identity writes
  answered 2xx and rolled back when `get_session` closed the transaction. Every
  other write router commits, which is why only this module lost data
- **A flushed row is visible to a test that shares the session.** The test
  fixture binds one session and one SAVEPOINT across request and assertion, so
  612 passing tests never noticed. The regression test counts `commit` calls
  instead of reading data back
- **`settings.py` was the only mutating service without a `refresh()`**, and that
  made every *second* write to a key a 500: `updated_at` is `onupdate=func.now()`,
  a server-side expression that leaves the attribute expired after an UPDATE, and
  the router serialises the response from a plain function, outside the greenlet.
  Only the first write (an INSERT) was ever tested
- The admin menu gates a module by permission only when the permission really
  exists. Expedientes is authorised by **scope** (`cases:read_all`,
  `read_assigned`, `read_published`), so the menu must not filter it
- Admin forms remount on `updated_at` so a save is reflected in the control and
  not only in the message, and every admin page has **no duplicate DOM ids**
  (`FormField` takes an `idPrefix`; filters are prefixed `filtro-`; a component
  mounted once per row takes the prefix as a prop)
- **A phone gets a hamburger, not a shorter rail.** `AdminMobileMenu` holds the
  same twelve modules and the same footer as the desktop rail, behind a real
  `<button>` with `aria-expanded`/`aria-controls`. The panel unmounts when closed,
  Escape closes it and returns focus, opening moves focus inside and locks the
  background scroll, and it closes by itself on navigation — state adjusted during
  render, not in an effect, so the browser's back button is covered too
- `AdminRail` marks the active item by **prefix** so a detail page keeps its
  module lit — **except `/admin`**, which is a prefix of every other screen and
  would otherwise light up everywhere
- **Every listing offers the full CRUD in the row**: Editar always, Cerrar on open
  cases, Desactivar on active clients and lawyers
- **Visual language of the admin surface**, revised without touching the palette:
  a coloured status rule down the left edge of every row (`live` forest, `held`
  brass, `urgent` wax, `closed` rule grey), one pill per row (status) with priority
  as a colour dot, a brass hairline above the page eyebrow, and KPI cards whose
  top rule separates volume from work pending. `RuleNote` says out loud why there
  is no delete button
- Row accents are `background-image`, **not** `box-shadow`: a `border-collapse`
  table does not paint a cell's inset shadow even though the computed style says
  it does. `.row-title` / `.row-meta` are standalone classes, not nested under
  `.ledger`, because the Dashboard uses the same pair outside any table
- **No delete anywhere, by the firm's decision.** The brief asked for deletion and
  `PROJECT_RULES.md` rule 5 forbids it; asked, the firm chose desactivar/archivar.
  `DELETE /clients/{id}` and `DELETE /lawyers/{id}` are logical deactivations.
  Consequence: a deactivated client leaves the default listing and only returns
  with `include_inactive`, and a closed case cannot be reopened from the UI
- Administration writes go through **Server Actions**, so the browser proxy
  allowlist was not widened and no credential reaches the client
- `GET /clients` used to answer 500 for everyone: `document_type` was a closed
  `Literal` and one seeded row carried a `NIF`. Fixed in both schemas with two
  regression tests
- Only the public consultation form is an unauthenticated write, unchanged
- **The public consultation form really sends**: `POST /api/v1/consultations` is
  the only unauthenticated write in the application, allowlisted in
  `PUBLIC_PATHS`, with its own three-per-hour IP budget, a honeypot, and
  consent stored as columns
- Consultation rows hold no IP, no user agent and no `change_logs` entries, so a
  right-to-erasure request means deleting one row, not chasing copies
- Staff read, re-status and erase requests through `consultations:read`, `:update`
  and `:erase`; erasure is a real delete, because a request that never became an
  expediente is a lead and not a legal record
- Still pending on the public site: the firm's email (published behind
  Cloudflare, unreadable from source), legal review of the privacy notice,
  approved editorial content, and any UI for the intake queue
- Docker Compose: postgres:17-alpine, backend, frontend with healthchecks
- .env.example with all required variables (no real secrets)
- Identity: users, roles, permissions, assignments, audit logs, refresh sessions
- RBAC enforcement via require_permission on every administrative endpoint
- Persisted refresh sessions with rotation, revocation and logout
- Audit middleware for login, logout, refresh and administrative writes
- Rate limiting per authenticated user or IP, stricter on auth endpoints
- Admin CLI to bootstrap the first superuser without storing secrets
- Clients: natural and legal persons, unique document, soft delete and history
- Lawyers: professional card, specialties, legal areas and status
- Legal area catalogue with 12 seeded practice areas
- Field level change history shared by business modules
- Cases: sequential numbering, assignments, parties, lifecycle and 360 view
- Case read scope split between staff wide and assigned only
- Actions bound to cases with visibility levels and a per case timeline
- Client scope: published content of their own cases only
- Calendar events bound to cases with day, week and month views
- Hearings with procedural data, conflict detection and rescheduling trace
- Deadlines merging calendar and action due dates
- Documents bound to cases with status, confidentiality and visibility
- Immutable document versions: previous content is never overwritten or deleted
- Upload validation by magic bytes, blocking executables and MIME mismatches
- SHA-256 per version, duplicates rejected, server generated storage keys
- Audited downloads returning binary bytes with integrity headers
- Local document storage with a persistent Docker volume
- Bootstrap admin CLI now covered by tests and fixed for a greenlet bug
- StorageBackend interface with LocalStorage and S3Storage behind it
- S3/MinIO backend with digest verification on write, read and tier change
- Version tiering with legal hold; retention only archives and never deletes
- Admin endpoints for the retention report, policy run and legal hold
- CLI apply_retention and CLI import_documents_to_s3
- Case scope translated to a semijoin so inherited filters cannot leak
- Read only bucket integrity verification with orphan detection
- `integrity_scans` / `integrity_findings` record every verification run
- `pg_dump` backup with SHA-256 manifest and automatic restore verification
- `scripts/backup.sh` covers config, PostgreSQL, originals and derivatives
- `docs/RESTORE.md` documents and exercises the restore procedure
- Off site backup with read-back digest verification and conservative retention
- `remote_backup` CLI: push, verify, fetch, list, prune
- Evidence engine: 6 tables for chain of custody, files, derivatives and jobs
- Immutable evidence originals enforced by the schema and a unique constraint
- Polyglot and decompression bomb detection on evidence uploads
- Image processing with Pillow: EXIF, aspect ratio, alpha, size profiles
- PDF processing with pikepdf: pages, metadata and digital signature detection
- A signed PDF is copied byte for byte and never re-encoded
- Ten `evidences:*` permissions; clients never receive `download_original`
- `evidence_worker` CLI claiming jobs with `FOR UPDATE SKIP LOCKED`
- Read by identifier requires visibility AND case scope, inside the query
- Messaging: 5 tables for conversations, participants, messages, attachments
  and notifications
- Internal conversations are invisible to the portal: adding a client user to
  one is refused with an error, not silently ignored
- Visibility is membership first, not role: administrators cannot read threads
  they do not participate in
- Chat attachments validated by magic bytes, digest verified on every download,
  storage key built from server side identifiers
- Message audit records the fact of sending, never the body
- Eight `messages:*` / `notifications:*` permissions; the client portal may
  read, send and be notified, but never open a thread, attach or archive
- Message rate limiting uses its own profile, applied to writes only
- Dashboards: one endpoint per scope, not per role; every figure is a COUNT over
  a query that already carries the case scope and visibility
- `/api/v1/dashboard` plus `/api/v1/dashboard/summary` for the header badge
- Overdue deadlines reported apart from upcoming ones
- `dashboard:read` granted to all four roles: it gates the aggregate, not new data
- `system_settings` table with typed values, audit trail and credential-key refusal
- Observability: every figure of MASTER_PROMPT section 43, summed in SQL
- `JobStatus` enum replacing four bare strings
- Contract tests: no public route beyond login/refresh, and no UUID ever reaches
  a user without permissions
- CI pipeline running the six gates of section 41 on every push
- `docs/DEPLOY.md` runbook: configuration, verification, routine, rollback

## In Progress
- Ninguna. Fases 0A a 10 completadas, con interfaz de usuario. El producto está
  en manos del despacho; lo que falta es infraestructura, no código.

## Pending
- Ninguna fase de producto. Quedan siete bloqueantes de produccion, todos de
  infraestructura o de proveedor, detallados al final de este archivo y en
  `docs/DEPLOY.md`.
- En la web publica: endpoint de contacto, informacion de la firma (fotografias,
  nombres, areas, direccion, telefono y correo), textos legales de privacidad y
  terminos, y contenido editorial aprobado.

## Active Endpoints
- GET /api/v1/health/live, GET /api/v1/health/ready
- POST /api/v1/auth/login, POST /api/v1/auth/refresh, POST /api/v1/auth/logout
- GET /api/v1/auth/me, /auth/me/roles, /auth/me/permissions, /auth/me/sessions
- GET/POST/PATCH/DELETE /api/v1/admin/users
- POST/DELETE /api/v1/admin/users/{id}/roles
- GET /api/v1/admin/roles, /api/v1/admin/permissions, /api/v1/admin/audit-logs
- GET/POST /api/v1/clients, GET/PATCH/DELETE /api/v1/clients/{id}
- GET /api/v1/clients/{id}/history
- GET/POST /api/v1/lawyers, GET /api/v1/lawyers/legal-areas
- GET/PATCH/DELETE /api/v1/lawyers/{id}, GET /api/v1/lawyers/{id}/history
- GET/POST /api/v1/cases, GET/PATCH /api/v1/cases/{id}
- POST /api/v1/cases/{id}/close, GET /api/v1/cases/{id}/360
- POST/DELETE /api/v1/cases/{id}/lawyers
- GET/POST /api/v1/cases/{id}/parties, GET /api/v1/cases/{id}/history
- POST /api/v1/cases/{id}/actions, GET /api/v1/cases/{id}/timeline
- GET /api/v1/actions, GET /api/v1/actions/pending
- GET/PATCH /api/v1/actions/{id}, GET /api/v1/actions/{id}/history
- GET/POST /api/v1/calendar, PATCH /api/v1/calendar/{id}
- GET /api/v1/calendar/deadlines
- GET/POST /api/v1/hearings, PATCH /api/v1/hearings/{id}
- POST /api/v1/hearings/{id}/reschedule
- GET/POST /api/v1/cases/{id}/documents
- GET/PATCH /api/v1/cases/{id}/documents/{document_id}
- POST /api/v1/documents/{document_id}/versions
- GET /api/v1/documents/{document_id}/versions/{version_id}/download
- GET /api/v1/documents/{document_id}/history
- GET /api/v1/documents/retention/report
- POST /api/v1/documents/retention/apply
- PATCH /api/v1/documents/{document_id}/legal-hold
- GET /api/v1/documents/integrity/latest
- GET/POST /api/v1/cases/{id}/evidences
- GET/PATCH /api/v1/evidences/{id}
- POST /api/v1/evidences/{id}/original
- GET /api/v1/evidences/{id}/original
- GET /api/v1/evidences/{id}/derivatives/{derivative_id}
- GET /api/v1/evidences/{id}/custody, /evidences/{id}/history
- POST/GET /api/v1/conversations, GET/PATCH /api/v1/conversations/{id}
- POST /api/v1/conversations/{id}/messages
- POST /api/v1/conversations/{id}/participants
- GET /api/v1/messages/{id}, DELETE /api/v1/messages/{id}
- GET /api/v1/messages/attachments/{attachment_id}
- GET /api/v1/messages/unread/summary
- GET /api/v1/notifications, POST /api/v1/notifications/{id}/read
- POST /api/v1/notifications/read-all
- GET /api/v1/dashboard, GET /api/v1/dashboard/summary
- GET/PUT/DELETE /api/v1/admin/settings/{key}, GET /api/v1/admin/settings
- GET /api/v1/admin/metrics/evidence, /metrics/evidence/derivatives

## Problems
- Rate limiter is in-memory and single process; requires Redis before scaling out
- MinIO in compose is unverified: this environment cannot pull `minio/minio`,
  so the S3 backend is only tested against `moto`
- Bucket privacy and `ContentMD5` rejection cannot be verified with `moto`
- The object backup is now verified by digest (`verify_backup_files`, run by
  `backup.sh` before the off-site push); what is still unproven is a full restore
  with the application stopped
- The stack's off site target shares the host, so it proves the mechanism only
- Integrity and backup CLI `run()` bodies are exercised manually, not by pytest
- Evidence validation is structural; there is no antivirus engine
- Compose runs `evidence-worker` continuously for queued large files
- PDF signatures are detected but not cryptographically verified
- Message bodies have no dedicated encryption at rest; they rely on database
  volume encryption
- No full text search, no group conversations and no `reply_to` threading
- Sin pruebas unitarias de frontend: no hay runner. La puerta de calidad del
  frontend es el triple `tsc --noEmit` / `eslint` / `next build`, mas la
  verificacion manual sobre HTTP real
- El gestor de evidencias no muestra el nombre del usuario en la ficha, que
  `MASTER_PROMPT` 39 pide: el endpoint de custodia expone `actor_id` y `ip`, no
  el nombre
- El panel del cliente no tiene series temporales ni comparativa de expedientes

## Blocking Production
Ordered by what they cost. The first three lose data.
1. `BACKUP_REMOTE_ENDPOINT` on another host or provider.
2. Full restore rehearsal with the application stopped.
3. Object backup verified by digest, not by count.
4. Antivirus engine for evidence: validation is structural only.
6. Bucket versioning enabled.
7. Rate limiter on Redis: in memory it is per worker and lost on restart.
