# DEPLOY

Runbook for putting WABOGADOS into production and keeping it there.

Read `docs/RESTORE.md` before the first deploy. A backup nobody has restored is
a hypothesis, not a backup.

---

## 1. What is not ready

This list is not a wish list. Each item is a way the system can lose a legal
record or expose a client's data, and none of them is optional.

| # | Blocker | Why it blocks |
| --- | --- | --- |
| 1 | `BACKUP_REMOTE_ENDPOINT` on another host | A second copy on the same machine does not survive a fire, a stolen disk or a ransom note. **Provider decided (2026-10-05): a bucket at another S3 provider.** What remains is the account and the credentials, which only the firm can create |
| 2 | Full restore rehearsal with the app stopped | **Done (2026-10-05)** — base wiped, restored, objects replaced with the app down; counts identical and 6 of 6 document digests verify. Report in `docs/RESTORE.md` §9. Still worth repeating by someone other than the author |
| 3 | ~~Object backup verified by digest~~ **Closed** — `verify_backup_files` re-reads every object against `MANIFEST.sha256` and `backup.sh` fails before pushing |
| 4 | Antivirus for evidence | Validation is structural. A structurally valid macro document passes |
| 5 | ~~Rate limiter on Redis~~ **Closed (2026-10-05)** — `REDIS_URL` selects a shared counter; with several workers the budget is no longer multiplied per process. A store outage degrades to a per-process count and logs an error |

Items 1 and 2 cost data. Items 4 and 5 cost availability or defence in depth.

---

## 2. Configuration that must change

`.env.example` is development. Copy it, then change at minimum:

```dotenv
APP_ENVIRONMENT=production

# Strong, unique, and not in version control.
SECRET_KEY=<openssl rand -hex 32>

POSTGRES_PASSWORD=<strong password>
DATABASE_URL=postgresql+asyncpg://wabogados:<password>@postgres:5432/wabogados

# No wildcards. TrustedHostMiddleware derives its allow-list from CORS_ORIGINS,
# so an entry of ["*"] disables host header protection as well.
CORS_ORIGINS=["https://app.mi-despacho.example"]
CORS_ALLOW_METHODS=["GET","POST","PATCH","PUT","DELETE"]
CORS_ALLOW_HEADERS=["Authorization","Content-Type","X-Request-ID"]

STORAGE_BACKEND=s3
S3_CREATE_BUCKET=false          # the bucket is provisioned, not guessed
S3_USE_SSL=true
S3_ACCESS_KEY=<...>
S3_SECRET_KEY=<...>

BACKUP_REMOTE_ENABLED=true
BACKUP_REMOTE_ENDPOINT=https://<other provider>
BACKUP_REMOTE_VERIFY_UPLOAD=true
```

`system_settings` is for operational values, **not for secrets**. Any row there
is readable by every administrator, included in `pg_dump`, and its previous
value written to `change_logs`. The service refuses keys that look like
credentials, but that check catches the obvious mistake only.

---

## 3. First deploy

```bash
# 1. Configuration
cp .env.example .env
# edit .env, then confirm nothing sensitive is staged
git check-ignore -v .env

# 2. Build. Always with --build: without it compose reuses the previous image
#    and the deploy silently ships the old code.
docker compose build --pull

# 3. Schema
docker compose run --rm backend alembic upgrade head

# 4. First administrator. Interactive, never exposed by the API.
docker compose run --rm backend python -m app.cli.create_admin

# 5. Start
docker compose up -d
docker compose ps
```

### Verify before declaring it up

```bash
curl -fsS http://localhost:8000/api/v1/health/live
curl -fsS http://localhost:8000/api/v1/health/ready   # includes the database check
```

`ready` must return 200. If it does not, the database is not reachable and the
instance must not take traffic. With `STORAGE_BACKEND=s3`, startup also verifies
that the bucket exists and enables versioning; the backend refuses to start when
either operation fails. Set `S3_CREATE_BUCKET=true` only when the application is
explicitly allowed to provision the bucket.

Then walk the real flows over HTTP. Pytest passing is not the same as the
application working:

1. Log in as the administrator.
2. Create a client, a lawyer and a case.
3. Upload a document, then download it and compare the SHA-256.
4. Upload an evidence original and a derived view.
5. Open an internal conversation, then confirm the portal does **not** see it.
6. Read the dashboard as an abogado and as a client: the figures must differ.

---

## 4. Routine operations

| Task | Command | Frequency |
| --- | --- | --- |
| Evidence processing | `evidence-worker` Compose service (`--loop`) | continuous |
| Database and objects backup | `scripts/backup.sh` | daily |
| Verify last backup | `python -m app.cli.verify_backup` | daily |
| Verify objects by digest | `python -m app.cli.verify_backup_files --manifest backups/<stamp>/MANIFEST.sha256` | daily |
| Remote backup | `python -m app.cli.remote_backup push` | daily, other host |
| Bucket integrity | `python -m app.cli.verify_integrity` | weekly |
| Retention policy | `python -m app.cli.apply_retention` | monthly |
| Migrate objects to S3 | `python -m app.cli.import_documents_to_s3` | once, then as needed |

`verify_integrity` never repairs and never deletes. It reports orphans and
missing objects; acting on the report is a human decision.

`apply_retention` only moves objects between storage tiers. It archives, it does
not delete. Evidence originals are never removed.

---

## 5. Rollback

Migrations are reversible, but rolling back the schema without rolling back the
code leaves the two disagreeing.

**Safe order after a bad application release:**

```bash
docker compose down
git checkout <previous tag>
docker compose build --pull
docker compose run --rm backend alembic downgrade -1   # only if the release added migrations
docker compose up -d
```

**Before rolling back a migration, check whether data was written under the new
schema.** Downgrading drops tables and columns; rows written since the upgrade
are lost. If any exist, restore from the backup instead:

```bash
docker compose down
scripts/backup.sh --restore <backup>    # see docs/RESTORE.md
docker compose up -d
```

Take a backup before either path. A rollback that cannot itself be undone is
not a rollback.

---

## 6. Quality gates

Every change passes the six gates of `MASTER_PROMPT` section 41 before it is
merged. `.github/workflows/quality-gates.yml` runs them on every push:

| Gate | What runs |
| --- | --- |
| 1. Architecture | `mypy .` in strict mode |
| 2. Database | `alembic upgrade head`, `downgrade -1`, `upgrade head` |
| 3. Security | `ruff` plus `test_only_login_and_refresh_are_public` and the permissionless-user tests |
| 4. Testing | full suite, coverage floor 80% |
| 5. Evidence | MIME, hash, security, audit and original preservation, when files are touched |
| 6. Documentation | `specs/`, `memory/` and `CHANGELOG.md` updated |

Locally, the same commands:

```bash
python -m ruff check .
python -m mypy .
docker compose -f compose.test.yaml run --rm --entrypoint /bin/sh test -c \
  "pip install -q -e '.[dev]' && alembic upgrade head && python -m pytest app/tests/ -q"
```

---

## 7. Incidents

### A file cannot be downloaded

```bash
python -m app.cli.verify_integrity            # find the missing key
```

Compare the recorded `sha256` with the object. If the object is gone, the
original is not recoverable from the database; restore it from the backup.

### Uploads fail after enabling S3

Check `S3_ADDRESSING_STYLE`. MinIO on a single node needs `path`; AWS usually
needs `virtual`. Check that `S3_ARCHIVE_STORAGE_CLASS` is not `GLACIER`: the
constructor rejects it because the object would not be readable immediately.

### Login fails for everyone

`SECRET_KEY` changed. Every issued access and refresh token becomes invalid, and
users must log in again. Rotate it deliberately, not as a troubleshooting step.

### The dashboard shows zeroes

Expected for a client with no cases, and for an abogado with no assignments. If
an administrator sees zeroes, check `resolve_scope`: the caller needs
`cases:read_all` or `is_superuser`.