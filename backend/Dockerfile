FROM python:3.12.11-slim AS builder

# PATH must include the virtualenv here: the test service builds this stage and
# Compose must not be relied on to set it, because ${PATH} in a Compose file is
# expanded from the host, which is not a POSIX PATH on Windows.
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN python -m venv /opt/venv && /opt/venv/bin/pip install .

# PostgreSQL client tools for backup and restore verification (MASTER_PROMPT 44).
# The base image already ships client 17, matching the PostgreSQL 17 server; an
# older pg_dump refuses to dump a newer server.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client; \
    pg_dump --version; \
    rm -rf /var/lib/apt/lists/*

FROM python:3.12.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
# Pre-create the storage root so a named volume inherits its ownership
# and the non root application user can persist documents.
RUN mkdir -p /var/lib/wabogados/storage /var/lib/wabogados/backups \
 && chown -R app:app /var/lib/wabogados
# Backup and restore tooling, same reason as the builder stage.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client; \
    pg_dump --version; \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
