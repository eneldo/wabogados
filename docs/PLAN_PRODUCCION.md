# PLAN PARA DEJAR WABOGADOS LISTO PARA PRODUCCIÓN

Fecha: 2026-11-17
Estado: **entregado, pendiente de aprobación por fases**
Base: `docs/INFORME_PRODUCCION_2026-11-17.md` (evidencia), `docs/DEPLOY.md`
(runbook), `docs/RESTORE.md` (respaldos), `memory/NEXT_STEPS.md`.

## Reglas del plan

1. **Ninguna fase se declara cerrada sin sus criterios de aceptación en verde.**
2. Las tareas marcadas **[FIRMA]** requieren datos o una decisión de la firma;
   el agente no puede sustituirlas. Las **[AGENTE]** las ejecuta el agente.
3. **No se descarta trabajo existente**: los cambios pendientes de multimedia,
   Dockerfile e IA que fallan gates se *completan* o se *apartan a rama*, nunca
   se borran.
4. Se trabaja por orden de fases; las fases 0–2 son secuenciales, la 3
   (decisiones) corre en paralelo desde el inicio.

---

## Fase 0 — Restaurar los gates del árbol [AGENTE]

**Objetivo:** que `ruff`, `mypy`, `pytest`, `docker build` y los gates de
frontend pasen sobre el árbol de trabajo.

### 0.1 Decisión previa: destino del refactor multimedia

Dos opciones; recomendación: **intentar primero el arreglo mínimo** (media.py
está a un cambio de distancia) y, si `test_media.py` no queda en verde en esa
sesión, **apartar a rama** `feature/media-streaming` sin descartar nada.

- **Opción A — Completar:** arreglo mínimo + correr los 17 tests.
- **Opción B — Apartar:** crear la rama con `backend/app/api/v1/media.py` y
  `backend/app/services/media.py`, y restaurar esos dos archivos a `HEAD` en
  `main`. El resto del árbol (recuperación de contraseña) queda intacto.

### 0.2 Arreglo mínimo de `backend/app/api/v1/media.py` (Opción A)

Evidencia del fallo (4 errores ruff + 4 mypy + 17 tests `NameError`):

1. **Importar desde `app.services.media`** los tres nombres que el servicio ya
   define y exporta (`HEADER_BYTES`, `MediaValidationError`,
   `detect_media_type`) — hoy el bloque de import (líneas 52–57) no los trae.
2. **Quitar el `import asyncio` de la línea 11** si queda sin uso (y el
   `import asyncio` interno de la línea 258, que es redundante).
3. **Quitar el kwarg `mime_type=` de la llamada `attach_file_stream`**
   (línea 270): la firma del servicio es
   `attach_file_stream(item, content, filename)` y **el servicio ya detecta el
   tipo por sí solo** leyendo el prefijo del stream (líneas 420–425 de
   `services/media.py`). Con eso desaparece también la detección duplicada del
   route (líneas 246–255) — o se conserva sin pasar el kwarg, si se prefiere
   fallar antes de consumir el stream.
4. Verificar que `StorageBackend.write_stream` y el `try/except` con
   `MediaError` cubren el caso de error a mitad de escritura (el docstring del
   route promete «sin objeto parcial»; si el servicio no lo garantiza, es
   hallazgo nuevo y se registra en `KNOWN_ISSUES.md`).

**Criterio de aceptación:**
`pytest app/tests/test_media.py -q` → 17/17 en verde.

### 0.3 Arreglo del `backend/Dockerfile`

Línea 35: `apt-get install -y --no-install-recommends postgresql-client; `
**sin `\` de continuación** → Docker interpreta `pg_dump` como instrucción
(`parse error on line 36`). Añadir la `\` final.

**Criterio:** `docker build -f backend/Dockerfile --check backend` sin errores
y `docker compose build backend` completo OK.

### 0.4 Decisión sobre el parche de IA (`backend/app/services/legal_ai.py`)

El diff añade `AI_CONFIDENTIALITY` (`NONE`/`ANONYMIZED`/`FULL`) con saneado
`ANONYMIZED`. **[FIRMA]** decidir la política. Hasta entonces: o se **aparta a
rama** igual que media, o se **incluye** con default `NONE` documentado (que
equivale al comportamiento actual). No incluirlo «de paso» sin decidir.

### 0.5 Gates completos sobre el árbol

```bash
python -m ruff check .            # 0 errores
python -m mypy .                  # 0 errores
python -m pytest app/tests/ -q --cov=app   # ≥80 % y 0 fallos
cd frontend && npm run typecheck && npx eslint . && npm run build
docker build -f backend/Dockerfile --check backend
```

**Criterio global de fase:** seis gates verdes (los seis de `MASTER_PROMPT`
§41, tal como los lista `docs/DEPLOY.md` §6).

---

## Fase 1 — Versionar y publicar [AGENTE, con autorización]

**Objetivo:** que todo el trabajo validado esté en `origin/main` y en CI verde;
nada de producción se construye desde árbol sin publicar.

1. **[FIRMA]** Autorizar commit/push de la entrega actual (30 modificados +
   21 nuevos: recuperación de contraseña, informe, plan, memoria).
2. Commit por unidad lógica sugerida:
   - `feat(auth): recuperación de contraseña` (backend + frontend + migración
     `ff60718293a4` + pruebas E2E + docs);
   - `fix(media)` o `chore(media): apartar streaming a rama` (según 0.1);
   - `docs: informe y plan de producción + memoria`.
   **Excluir** `.env`, `.tmp/`, respaldos, credenciales y snapshots.
3. Push y **esperar CI verde** (`.github/workflows/quality-gates.yml`).
4. **Etiquetar la release candidata** (p. ej. `v1.0.0-rc1`) — el rollback de
   `docs/DEPLOY.md` §5 asume `git checkout <previous tag>`; sin tags no hay
   rollback trazable.

**Criterio:** `origin/main` en verde y tag `v1.0.0-rc1` creada.

---

## Fase 2 — Base de datos y stack local de referencia [AGENTE]

**Objetivo:** la base local principal y el stack local quedan en el mismo
estado que la release candidata (hoy divergen: migración `ff60718293a4` sin
aplicar y stack caído ~46 h).

1. Respaldo previo de PostgreSQL (patrón ya usado):
   `pg_dump` a `.tmp/` con modo 0600 y `pg_restore --list` de verificación.
2. Levantar servicios base: `docker compose up -d postgres redis clamav`.
3. `docker compose run --rm backend alembic upgrade head` → aplica
   `ff60718293a4` (verificar con `alembic current`).
4. Build desde el árbol ya gateado: `docker compose build --pull` y
   `docker compose up -d --wait`.
5. Smoke: `/api/v1/health/live` y `/api/v1/health/ready` en 200; login
   administrativo; las 17 pruebas `test_media` contra el contenedor; Playwright
   `--project=public` (19) contra el stack local.
6. Diagnosticar el **`evidence-worker` en crash loop** (hoy falla por DNS de
   postgres porque el stack estaba caído; debe quedar `Up (healthy)` con el
   stack completo).

**Criterio:** stack local completo sano, migración aplicada, smoke + 19 pruebas
públicas en verde.

---

## Fase 3 — Decisiones de la firma [FIRMA] — paralela desde hoy

Ninguna bloquea las fases 0–2, pero **todas bloquean el go-live**. Cada una
cierra con un registro en `memory/DECISIONS.md`.

| # | Decisión | Qué implica | Referencia |
| --- | --- | --- | --- |
| 1 | **Dominio y hosting** | Nombre de dominio, proveedor del host, DNS | `docs/DEPLOY.md` |
| 2 | **TLS y proxy inverso** | Cómo se termina HTTPS: nginx como servicio en `compose.prod.yaml` (recomendado) o proxy del proveedor. Certificados y renovación automática | nuevo ADR |
| 3 | **Bucket S3 externo** | Cuenta, bucket con versionado, credencial dedicada en **otro proveedor**, y **Object Lock sí/no** | `docs/RESTORE.md`, KNOWN_ISSUES |
| 4 | **Destino del respaldo remoto** | Mismo bucket S3 u otro; retención; quién tiene las credenciales | `docs/RESTORE.md` |
| 5 | **SMTP** | Proveedor, remitente autorizado, `PASSWORD_RECOVERY_PUBLIC_URL` (HTTPS), aprobación de elegibilidad/límites | `docs/RECUPERACION_CONTRASENA.md` fase 6 |
| 6 | **Política IA** | `AI_CONFIDENTIALITY=NONE|ANONYMIZED|FULL` y saneado mínimo en `generate_draft` | fase 0.4 |
| 7 | **Aviso de privacidad** | Aprobar el texto vigente (ya con responsable/canal/derechos) y decidir si se publica página `/privacidad` con enlace en el pie | `NEXT_STEPS` web pública |
| 8 | **Contenido editorial** | Aprobor/rechazar las noticias marcadas «Pendiente» | portada |
| 9 | **Zona horaria** | Confirmar `America/Bogota` (hoy fijada en código) | `NEXT_STEPS` |
| 10 | **Confirmación por correo de solicitudes** | Si el formulario público debe enviar correo de confirmación (hoy solo registra) | `NEXT_STEPS` |

---

## Fase 4 — Infraestructura de producción [AGENTE + FIRMA]

**Objetivo:** un despliegue real detrás de HTTPS, con configuración de
producción y sin servicios expuestos.

1. **Host:** Docker + Compose + `bash` (requerido por `scripts/backup.sh`),
   disco para `storage_data` + `backups/`, firewall: solo 80/443; PostgreSQL,
   Redis y MinIO **nunca** publicados.
2. **`.env` de producción** (partiendo de `.env.example` y `docs/DEPLOY.md` §2):
   - `APP_ENVIRONMENT=production` (activa `assert_production_is_safe` y HSTS);
   - `SECRET_KEY` nueva, aleatoria, ≥32 bytes (invalida todos los JWT previos:
     hacerlo antes de cargar usuarios);
   - `DATABASE_URL` con `POSTGRES_PASSWORD` fuerte;
   - `CORS_ORIGINS`/hosts del dominio real, **sin `*`**;
   - `STORAGE_BACKEND=s3` + credenciales del bucket de la decisión 3,
     `S3_CREATE_BUCKET=false`;
   - `BACKUP_REMOTE_ENABLED=true` + endpoint de la decisión 4;
   - `REDIS_URL` (rate limiting compartido);
   - `ANTIVIRUS_HOST=clamav` (si `ANTIVIRUS_HOST` queda vacío el escaneo se
     deshabilita **sin aviso**);
   - `PASSWORD_RECOVERY_*` según fase 5.
3. **Proxy/TLS** según la decisión 2 (recomendación: overlay
   `compose.prod.yaml` con `nginx` + certificados del proveedor; HSTS ya lo
   emite el backend cuando `APP_ENVIRONMENT=production`).
4. **Despliegue** (orden de `docs/DEPLOY.md` §3, sin improvisar):

   ```bash
   docker compose build --pull          # siempre --build: si no, se reutiliza la imagen vieja
   docker compose run --rm backend alembic upgrade head
   docker compose run --rm backend python -m app.cli.create_admin   # interactivo
   docker compose up -d && docker compose ps
   curl -fsS https://<dominio>/api/v1/health/ready   # debe ser 200
   ```

5. **Recorrido de aceptación manual** (§3 de DEPLOY, seis pasos): login admin;
   crear cliente/abogado/expediente; subir y descargar documento comparando
   SHA-256; subir evidencia original + derivada; conversación interna **invisible
   en el portal**; dashboard como abogado y como cliente con cifras distintas.

**Criterio:** sitio en HTTPS responde, `ready` 200, recorrido completo
completado y anotado.

---

## Fase 5 — Respaldos y restauración [AGENTE + FIRMA]

**Objetivo:** un respaldo que sobreviva a fuego, disco robado y ransomware, y
que se sepa restaurar.

1. `BACKUP_REMOTE_ENABLED=true` con el destino de la decisión 4 (otro host).
2. **Automatizar** `scripts/backup.sh` diario (cron/systemd timer en el host)
   con `verify_backup` + `verify_backup_files` (digest) antes de la copia
   externa — hoy el último respaldo local es de **2026-10-22**.
3. **Repetir el ensayo de restauración** (`docs/RESTORE.md` §9) con **una
   persona distinta del autor**, aplicando las dos correcciones abiertas:
   - el procedimiento debe detener también `evidence-worker` (hoy dice parar
     solo backend/frontend y el worker escribe sobre la base que se repone);
   - `scripts/backup.sh --restore` está documentado como «no restaura»: o se
     arregla el script o la doc deja de prometerlo (discrepancias de
     `NEXT_STEPS` hallazgo 9).
4. Object Lock según decisión 3 (si no, documentar el riesgo aceptado como ADR).

**Criterio:** ≥1 respaldo remoto automático verificado por digest + ensayo de
restauración firmado por segunda persona.

---

## Fase 6 — Correo: recuperación de contraseña y avisos [AGENTE + FIRMA]

**Objetivo:** activar la fase 6 de `docs/RECUPERACION_CONTRASENA.md`.

1. **[FIRMA]** Datos SMTP (decisión 5).
2. Configurar en `.env` de producción: `PASSWORD_RECOVERY_SMTP_*`,
   `PASSWORD_RECOVERY_MAIL_FROM`, `PASSWORD_RECOVERY_PUBLIC_URL=https://<dominio>`,
   claves de cifrado/outbox (`PASSWORD_RECOVERY_ENCRYPTION_KEY`,
   `PASSWORD_RECOVERY_PROXY_KEY`) generadas con `openssl rand -hex 32`.
3. **[FIRMA]** Aprobar elegibilidad y límites
   (`REQUEST_IP_LIMIT`, `GLOBAL_LIMIT`, `RECIPIENT_LIMIT`, `COOLDOWN`).
4. `PASSWORD_RECOVERY_ENABLED=true` + worker (`perfil compose recovery`).
5. Prueba real de extremo a extremo: solicitud → correo → enlace de un uso →
   reset → login → sesiones previas revocadas. Verificar límites 411/413/429.
6. **[FIRMA, decisión 10]** Si aplica: correo de confirmación de solicitudes.

**Criterio:** recuperación activada con envío real probado y límites aprobados;
o explícitamente apagada y documentada como limitación conocida.

---

## Fase 7 — Ensayo de aceptación del despliegue [AGENTE]

**Objetivo:** validar el artefacto que quedará sirviendo tráfico, no el árbol.

1. Playwright contra el despliegue (o staging idéntico):
   `public` (19), `layout`, `password-recovery`, `password-reset`, `private`,
   `admin-portal` — credenciales por variables de entorno, nunca en el repo.
2. Revisión visual 390/1440 + sin overflow en 320–1440.
3. Seguridad básica: sin stack traces en errores; rate limiting en login
   (429); sin UUIDs sin permiso (tests contractuales); HSTS presente;
   `gitleaks` limpio.
4. Carga mínima: subida de un archivo grande hasta el tope (413 en el tope) y
   descarga con `Range` de un vídeo.
5. Anotar el resultado en `docs/` como informe de aceptación (plantilla del
   informe del 2026-11-17).

**Criterio:** checklist de aceptación completo, sin pendientes nuevos
sin registrar.

---

## Fase 8 — Operación continua [AGENTE + FIRMA]

**Objetivo:** que la producción se mantenga, no solo que arranque.

| Tarea | Frecuencia | Referencia |
| --- | --- | --- |
| `backup.sh` + verificación digest | diaria | `DEPLOY.md` §4 |
| `verify_backup` | diaria | §4 |
| `verify_integrity` | semanal | §4 |
| `apply_retention` | mensual | §4 |
| Actualizar imágenes/parches de seguridad | mensual | — |
| Revisar `memory/KNOWN_ISSUES.md` y este plan | mensual | — |
| CI verde en cada push | continua | `quality-gates.yml` |
| Rotación de `SECRET_KEY` | solo deliberada | `DEPLOY.md` §7 |

Deudas técnicas a incluir en la primera ventana de mantenimiento (no bloquean
go-live): poda de `refresh_tokens` caducados, verificación criptográfica de
firmas PDF, derivación de PDF a imagen, notificación al cliente al publicar
evidencia, y `total_unread` con alcance de expediente.

---

## Orden resumido y dependencias

```
Fase 0 (gates) ──► Fase 1 (commit/tag/CI) ──► Fase 2 (BD + stack) ──► Fase 4 (despliegue) ──► Fase 7 (aceptación) ──► Fase 8
                                                                        ▲
Fase 3 (decisiones de la firma) ────────────────────────────────────────┤
Fase 5 (respaldos remotos) ─────────────────────────────────────────────┤
Fase 6 (SMTP) ──────────────────────────────────────────────────────────┘
```

- **Camino crítico:** 0 → 1 → 2 → 4 → 7.
- **Lo único que impide arrancar la fase 4 hoy:** decisiones 1–4 (dominio, TLS,
  S3, respaldo remoto). El resto del plan es ejecutable de inmediato.

## Criterios globales de salida (definición de «listo para producción»)

- [ ] Seis gates verdes sobre el árbol publicado y CI verde en `origin/main`
- [ ] Release etiquetada (`v1.0.0-rc1` o superior) y rollback ensayado una vez
- [ ] `docker compose build --pull` completo funciona desde cero
- [ ] Migraciones al día (`alembic current` = `head`) con respaldo previo
- [ ] Sitio en HTTPS con `APP_ENVIRONMENT=production`, `ready` 200
- [ ] Recorrido manual de `DEPLOY.md` §3 anotado en verde
- [ ] Respaldo automático diario con verificación por digest hacia **otro host**
- [ ] Ensayo de restauración ejecutado por segunda persona
- [ ] SMTP configurado y recuperación de contraseña activa con envío probado
      (o apagada y documentada como limitación aceptada)
- [ ] Aviso de privacidad aprobado y publicado; contenido editorial aprobado
- [ ] Playwright de aceptación en verde contra el despliegue
- [ ] `KNOWN_ISSUES.md` y este plan actualizados; ADRs de las decisiones 2, 3 y
      6 escritos
