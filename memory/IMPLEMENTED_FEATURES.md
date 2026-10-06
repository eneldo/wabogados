# IMPLEMENTED FEATURES

- Foundation (Fase 0A):
  - FastAPI application structure with API v1 prefix
  - Configuration via Pydantic Settings (.env)
  - SQLAlchemy 2 async engine + session factory
  - Alembic initialized with async migrations
  - Health endpoints: /live (process), /ready (process + DB)
  - Uniform error format: {error: {code, message, details}}
  - Test suite: pytest + httpx, 95% coverage
  - Lint: Ruff (E, F, I, UP, B, ASYNC, RUF), line-length 100
  - Typecheck: mypy strict + pydantic plugin
  - Dockerfile: non-root user, cap_drop ALL, no-new-privileges
  - Next.js 16 App Router, TypeScript strict, Tailwind 4
  - Status page with accessible UI, server-side fetch
  - ESLint 9 flat config, tsc --noEmit
  - Docker Compose: postgres, backend, frontend with healthchecks
   - .env.example documenting all variables without secrets

- Security and identity (Fase 1, complete):
  - User, Role, Permission, UserRole, RolePermission, AuditLog and RefreshToken models
  - Reversible Alembic migrations through d4e5f6a7b8c9
  - Argon2 password hashing and JWT access/refresh tokens
  - Login, refresh, logout, current user, roles, permissions and sessions endpoints
  - Authorization header parsed and validated for protected endpoints
  - Canonical RBAC matrix in app/security/permissions.py seeded by migration
  - require_permission dependency enforcing explicit permissions per endpoint
  - Administrative user administration with soft delete and role assignment
  - Persisted refresh sessions with rotation, revocation and logout-all
  - Audit middleware with secret redaction and injectable session factory
  - Rate limiting per user or IP with stricter limits on authentication routes
  - Bootstrap administrator CLI reading credentials from the environment
  - Negative auth tests covering credentials, inactive users and token misuse
  - PostgreSQL test isolation with ephemeral Docker storage and savepoint rollback

- Clients and lawyers (Fase 2, complete):
  - `Client` model supporting natural and legal persons with unique document
  - `Lawyer` model with document, professional card, specialties, status and areas
  - `LegalArea` catalogue seeded with 12 practice areas
  - `ChangeLog` table recording field level before/after with the responsible user
  - Reversible migrations `e5f6a7b8c9d0` (tables) and `f6a7b8c9d0e1` (permissions and areas)
  - Nine new permissions; staff roles may read, create and update but never delete
  - CRUD endpoints for clients and lawyers with explicit permission per operation
  - Listing with pagination, search, type/status filters and active-only default
  - Soft delete that preserves records with `deleted_at` and `deleted_by`
  - Modification history exposed per client and per lawyer

- Cases (Fase 3, complete):
  - `Case` model with client, responsible lawyer, legal area and process type
  - Sequential numbering `WA-AAAA-000001` guarded by `SELECT ... FOR UPDATE`
  - `CaseLawyer` assignments with responsable and colaborador roles
  - `CaseParty` for demandante, demandado, contraparte and tercero
  - Status, priority, amounts, dates and free description
  - Reversible migrations `a7b8c9d0e1f2` (tables) and `b8c9d0e1f2a3` (permissions)
  - Six case permissions with a read scope split: all versus assigned
  - Assignment aware listing and anti enumeration 404 for out of scope cases
  - Closing restricted to administrators as a reserved legal act
  - Case 360 view exposing collaborators, parties, history and pending tabs

- Actions (Fase 4, complete):
  - `Action` model bound to a case with type, datetime, result and responsible
  - Next action with its due date, validated as a pair
  - Visibility levels: interna, equipo and publicada
  - Reversible migrations `c9d0e1f2a3b4` (table) and `d0e1f2a3b4c5` (permissions)
  - Four action permissions, including a published-only read for clients
  - Case scoped access inherited from the parent case
  - Chronological timeline per case with case status and pending marker
  - Due next actions report across the caller's scope
  - Client scope: only published data inside their own cases
  - Case 360 view now serves the actuaciones section
  - 149 passing backend tests with 85.09% coverage

- Calendar and hearings (Fase 5, complete):
  - `CalendarEvent` always bound to a case with six event types
  - `Hearing` with court, courtroom, judge, procedural stage and attendance
  - Reversible migrations `e1f2a3b4c5d6` (tables) and `f2a3b4c5d6e7` (permissions)
  - Eight calendar and hearing permissions
  - Day, week, month, lawyer and case views with filters
  - Realized hearings require a recorded result
  - Overlap detection blocks double booking a lawyer
  - Rescheduling with trace, restricted to the administrator
  - Deadlines merging `vencimiento` events with pending action due dates
  - Case 360 view serves agenda and hearings
  - 172 passing backend tests with 84.65% coverage

- Documents (Fase 6, complete):
  - `Document` bound to a case with type, status, confidentiality and visibility
  - `DocumentVersion` with immutable content, SHA-256, author and per document numbering
  - `DocumentDownload` audit record for every download
  - Reversible migrations `a3b4c5d6e7f8` (tables) and `b4c5d6e7f8a9` (permissions)
  - Upload validation by magic bytes, blocking executables and MIME mismatches
  - Server generated storage keys; the user file name never reaches the path
  - Duplicate content rejected per document, existing versions never modified
  - Binary download response with `Content-Disposition`, integrity hash and `nosniff`
  - Five document permissions; clients read published metadata only
  - Publishing never grants download; out of scope documents return 404
  - Local storage behind a single class with a persistent Docker volume
  - Bootstrap admin CLI covered by tests and fixed for a greenlet bug
  - Case 360 view serves the documentos section
  - 334 passing backend tests with 84.90% coverage

- Object storage and version retention:
  - `StorageBackend` protocol with `LocalStorage` and `S3Storage` (boto3 in a thread)
  - SHA-256 verified on write, on read and after every tier change
  - Atomic local writes and server generated opaque keys
  - `document_versions.tier`, `documents.legal_hold`, reversible migration `c5d6e7f8a9b0`
  - `RetentionService` that only archives, never deletes
  - `documents:retention` and `documents:legal_hold`, administrator only
  - CLI `apply_retention` and `import_documents_to_s3`

- Backup and integrity verification (MASTER_PROMPT 44):
  - `IntegrityService`: read only SHA-256 verification of every stored version
  - Findings: corrupted, missing, size_mismatch, unreadable, orphaned
  - Orphan detection by listing the backend: proves nothing was added
  - `iter_keys` and `stat` added to the storage protocol, paginated on S3
  - Batched verification with bounded concurrency and no shared async session
  - `full` and deterministic `sample` modes
  - `integrity_scans` / `integrity_findings`, reversible migration `d6e7f8a9b0c1`
  - `BackupService`: `pg_dump` custom format, SHA-256 manifest, automatic restore
  - Restore verified into a scratch database: digest, revision, tables, counts
  - `scripts/backup.sh` covers configuration, PostgreSQL, originals, derivatives
  - `docs/RESTORE.md` documents and exercises the procedure
  - CLI `verify_integrity`, `verify_backup`, `backup_database`
  - Verification never repairs; a test fails if a write path is introduced

- Administration surface (Fase de portal privado, 2026-10-02/03):
  - Shell at `/admin`: fixed rail on desktop, hamburger panel on narrow screens
  - `lib/admin-nav.ts` with three states per module (ready, building, planned) and
    the three modules `MASTER_PROMPT.md` forbids rendered inert with their reason
  - Session guard in the layout, once, for the whole surface
  - Dashboard reusing `/dashboard`, no figure calculated in the frontend
  - Clients and lawyers: listing with search and filters, creation dialog, detail
    with editing and change history, deactivation with confirmation
  - Cases: listing with search and filters, creation dialog, 360 record on
    `GET /cases/{id}/360` with a count per section, closure with date and note,
    lawyer incorporation and party creation
  - Agenda: day, week and month views, temporal navigation, filters, grouped
    chronology, metrics and deadline panel
  - Events and hearings through Server Actions; hearings support creation,
    registration and traced rescheduling, with required result and overlap rules
  - Generic calendar routes cannot create or edit hearings; hearing reads enforce
    permission, case scope, visibility and activity
  - Institutional calendar time is consistently interpreted and displayed in
    `America/Bogota`, independently of the frontend container timezone
  - Full CRUD from the row: Editar always, Cerrar on open cases, Desactivar on
    active records. No delete anywhere, by ADR-051
  - Writes go through Server Actions; the browser proxy allowlist was not widened
  - Visual language: coloured status rule per row, one pill per row with priority
    as a dot, brass hairline above the page eyebrow, warm card shadows, `RuleNote`
    saying out loud why there is no delete button
  - Accessibility verified: no duplicate DOM ids, no horizontal overflow at 320,
    390, 768 and 1440, real `<button>` with `aria-expanded` on the menu, focus
    moved inside on open and returned on Escape
  - Row actions use one SVG family: pencil for editing, sealed file for closing,
    person removal for deactivation and plus for creation. Icons remain decorative
    beside visible labels, and the action controls share height, focus and hover
    treatment across cases, clients and lawyers
   - Messages: personal staff inbox respecting explicit participation, local filters
     and metrics, internal/client conversation creation, thread reading and replies,
     validated attachments, logical archive of own messages and confirmed closure
   - Opening a thread clears its unread badge locally; attachments state the limit
     and are checked in the browser before upload while the backend remains authoritative
   - Documents browser: `GET /api/v1/documents` reusing a shared filter helper over
     case scope, type, status, confidentiality, visibility, legal hold and search,
     returning `{items, total, skip, limit}`, with eight tests including one that
     proves the visibility filter cannot widen access and one that rejects a page
     past the limit
   - `/admin/documentos`: global listing behind `documents:read`, filter form,
     status/type/confidentiality chips, row rule for anulado, reemplazado and legal
     hold, pagination and an empty state that explains the filter rather than the
     database
   - Detail drawer over the proxy: ficha, every version with its hash, tier and
     download link gated by `documents:download`, Escape to close. No delete
     anywhere: a document ends at anulado and a version at being replaced
   - The drawer is portalled onto the body with the `viewport-overlay` class,
     because the `row-enter` transform on the rows would otherwise make one table
     row the containing block of a fixed full-screen panel
   - Security module at `/admin/seguridad`, three views driven by `?vista=` and each
     gated on its own permission: usuarios, roles and auditoría
   - User directory over `GET /api/v1/admin/users` with `search`, `role` and
     `is_active` filters and pagination; create and edit dialogs, a roles dialog
     that computes the diff server side, deactivate with confirmation and
     reactivate as its own action
   - Roles view lists the four roles with the permissions each grants, plus the
     whole permission catalogue grouped by resource with its descriptions
   - Audit trail over the new paginated `GET /api/v1/admin/audit-logs` with
     `search`, `result` and `user_id` filters; each entry carries `user_email`, so
     the trail names a person instead of a bare identifier
   - New `GET /api/v1/admin/users/{id}`, so the edit and roles dialogs read one
     record instead of deriving it from the listing
   - `UserBase.email` reads as `str` while `UserCreate.email` stays `EmailStr`:
     validating on output made `admin@wabogados.local` answer 500 for the whole
     directory, and the bootstrap CLI now checks `ADMIN_EMAIL` the same way the API
     does
   - All five identity writes commit; see the fixed-bug note below
   - Settings module at `/admin/configuracion`, gated on `settings:read`, with the
     write controls gated separately on `settings:write`
   - `system_settings` grouped by category, each block with its own ledger: key,
     stored value, a chip naming the type it will be read back as, and the moment
     of the last write. Search covers key, category, description and value, so a
     word visible on screen finds its row
   - The value is edited as the text that is stored, not as the decoded value, and
     the create dialog says so; a value that parses as JSON is sent parsed, so `30`
     is the number thirty rather than thirty characters
   - **Delete by key with a confirmation**, and it says out loud that this is the
     one exception to the project's no-deletion rule, because a setting is not a
     legal record and the previous value reaches `change_logs`. The confirm button
     does not take the initial focus
   - `SettingsService.upsert` refreshes after an UPDATE, the house pattern
     everywhere else: without it the second write of a key raised `MissingGreenlet`
     and answered 500 to a change that had already been committed
   - `.ledger tbody th` is left-aligned in `globals.css`: a row header is a `th`
     and the browser centres every `th`, which only became visible in a column wide
     enough for a description
   - Current verification baseline: 613 backend tests, 85.75% coverage; frontend
     typecheck, lint and production build clean; all three security views and the
     settings screen verified in the browser at 1600 and 390 with no horizontal
     overflow
   - The three `planned` modules carry their decided scope in `admin-nav.ts`
     (`future: {phase, scope}`) and the shared `modulo/[slug]` page renders it, so
     an inert menu entry is a roadmap the direction can read instead of a dead end
   - **Multimedial was built anyway** (ADR-055, the brief's prohibition lifted by the
     owner): `/admin/multimedia`, an internal firm library of video, image, audio
     and PDF, with `media:*` permissions, a `media_items` domain kept deliberately
     apart from the evidence engine, Range-capable streaming through its own route,
     and deactivation that keeps the file so the row can be brought back

- Operational hardening (2026-10-04):
  - `initialize_storage` runs on startup when `STORAGE_BACKEND=s3`: the bucket
    must exist (or `S3_CREATE_BUCKET=true`) and versioning must be enabled, or
    the API refuses to start. ADR-058
  - `evidence-worker` Compose service runs `app.cli.evidence_worker --loop` every
    30 seconds, ten jobs per pass, sharing database and storage volume with the
    API, `restart: unless-stopped`. A dedicated process rather than another HTTP
    worker, because the rate limiter is in memory. ADR-059
  - Sign-out revokes the refresh session server-side through
    `POST /api/v1/auth/logout` before clearing cookies, and revokes only that
    one session. ADR-060
  - Passwords hashed with `argon2-cffi` directly (argon2id, t=3, m=64 MiB, p=4),
    replacing unmaintained Passlib. A Passlib-written hash is frozen as a
    constant in `test_password_hashing.py` and still verifies; passlib is no
    longer imported and no longer in the image. ADR-061
  - `app/services/backup_manifest.py` and `app/cli/verify_backup_files.py`
    verify every file of a backup against `MANIFEST.sha256` by SHA-256, in 1 MiB
    chunks, separating corrupted, missing and unlisted. An empty manifest fails.
    `scripts/backup.sh` runs it before the off-site push. POSIX separators are
    pinned so a backup verified from Windows does not report every object
    missing. ADR-062
  - Dependency ceilings pinned to what was measured, each with its reason in
    `pyproject.toml`; the `dev` extra now declares the type stubs a clean install
    needs. ADR-063
  - `app/tests/test_packaging.py` reads the Dockerfile `CMD` and asserts the
    binary is a declared dependency, plus a check that every third-party module
    the application imports has its distribution declared. It exists because a
    missing `uvicorn` passed every gate and left the service dead
  - `app/core/http_status.py` names the two status codes Starlette renamed in
    1.x, because the new name does not exist in 0.4x and the old one warns in 1.x
  - The dashboard client-name query joins `cases` and `clients` explicitly, which
    removed the last two `SAWarning` cartesian products
  - The extractive summary without a query returns the selected sentences in
    document order; with a query it keeps relevance order
