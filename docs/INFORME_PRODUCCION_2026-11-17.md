# Informe de preparación para producción — 2026-11-17

**Veredicto: NO LISTO para producción.**

El producto funcional está maduro y la base de calidad es sólida, pero hay
bloqueantes duros en tres frentes: (1) el árbol de trabajo actual **no pasa sus
propios gates** (roto en multimedia y Dockerfile), (2) la infraestructura de
producción (HTTPS/dominio, respaldo externo, SMTP) no existe todavía, y (3) el
último respaldo local tiene 26 días.

---

## 1. Evidencia de gates (ejecutada el 2026-11-17)

| Gate | Ámbito | Resultado |
| --- | --- | --- |
| CI `quality-gates` (GitHub) | `origin/main` = `de6d18a` | **VERDE** — corrida #7, 2026-11-15 |
| `ruff check` | árbol de trabajo | **ROJO** — 4 errores en `backend/app/api/v1/media.py` (F821 `HEADER_BYTES`, `detect_media_type`, `MediaValidationError`; import `asyncio` sin usar) |
| `mypy` estricto | árbol de trabajo (194 archivos) | **ROJO** — 4 errores en `media.py`: los 3 anteriores + `mime_type` como kwarg inexistente en `MediaService.attach_file_stream` |
| `pytest` + cobertura | árbol de trabajo | **ROJO** — 919 pasan, **17 fallan** (todas `test_media.py`, `NameError`); 936 en total, cobertura **84,74 %** (suelo 80 % se cumple) |
| Frontend `tsc --noEmit` | árbol de trabajo | **VERDE** |
| Frontend ESLint | árbol de trabajo | **VERDE** — 0 errores, 1 warning preexistente (`portal/casos/[caseId]/page.tsx:288`) |
| Frontend `next build` | árbol de trabajo | **VERDE** |
| `docker build --check backend/Dockerfile` | árbol de trabajo | **ROJO** — `parse error on line 36: unknown instruction: pg_dump` (continuación `RUN` rota) |
| Secretos | archivos nuevos de recuperación de contraseña | Sin hallazgos en revisión dirigida; gitleaks completo sobre el árbol no terminó por tamaño (los tests están exentos en `.gitleaks.toml`) |

**Lectura:** los 936 tests pasaron hace dos días sobre el snapshot aislado
`wabogados-password-recovery:local` (HEAD + recuperación, excluyendo los
cambios pendientes de multimedia). El fallo actual es del trabajo **pendiente y
no validado** de multimedia que sigue en el árbol: `app/api/v1/media.py` quedó
a medias (importa desde `app.services.media` tres nombres que el servicio sí
exporta pero el router no importa, y llama a `attach_file_stream` con un
argumento que la firma no acepta). **Ninguna release publicada contiene este
cambio**, pero el árbol tal como está no se puede compilar ni publicar.

## 2. Bloqueantes de producción (ordenados por lo que cuestan)

### Pierden datos
1. **Respaldo externo no existe.** `BACKUP_REMOTE_ENABLED=false`; el único
   destino es el propio host. Último respaldo local: **2026-10-22** (26 días).
   `scripts/backup.sh` no se ha ejecutado de principio a fin en este host (no
   tiene `bash`). Decisión de firma pendiente: cuenta, bucket S3 con versionado,
   credencial dedicada y Object Lock.
2. **Ensayo de restauración:** hecho una vez (2026-10-05, `docs/RESTORE.md` §9)
   pero por su autor; falta repetirlo con otra persona y con `backup.sh` entero.
3. **La migración `ff60718293a4` (recuperación de contraseña) no está aplicada
   en la base local principal** — y su entrega va **sin commit/push**.

### Exponen datos o impiden operar
4. **Sin HTTPS ni dominio.** No hay nginx ni reverse proxy en `compose.yaml`;
   no se ha hecho ningún despliegue al dominio público. El `.env` local corre
   con defaults de desarrollo (`APP_ENVIRONMENT` no está fijado).
5. **El árbol no pasa gates ni construye imagen** (apartado 1): hasta
   restaurar `ruff`/`mypy`/`pytest` y arreglar el `Dockerfile`, un
   `docker compose build --pull` de producción fallaría o mezclaría trabajo sin
   validar.
6. **Sin SMTP.** La recuperación «Olvidé mi contraseña» está implementada pero
   **apagada por defecto** (`PASSWORD_RECOVERY_ENABLED=false`); tampoco se
   envía confirmación de las solicitudes públicas. Fase 6: proveedor, remitente,
   origen HTTPS y aprobación de límites.
7. **Entrega sin publicar:** 30 archivos modificados + 21 nuevos sin commit
   (recuperación de contraseña, memoria y ajustes menores). El HEAD publicado
   (`de6d18a`) está en verde en CI, pero el trabajo de recuperación no está
   versionado.

### Defensa en profundidad / alcance
8. **Biblioteca multimedia sin escaneo antivirus** (vídeo hasta 500 MB);
   ClamAV está integrado solo en evidencias y documentos.
9. **Multimedia sin procesar:** sin ffmpeg en la imagen desplegada, sin
   transcodificación ni worker de cola; `integrity`/`retention`/`backup_manifest`
   no conocen `media_items`.
10. **IA jurídica:** generación asistida apagada (falta política de
    confidencialidad y proveedor). Búsqueda/resumen funcionan.
11. **Aviso de privacidad:** el diálogo del formulario ya incluye responsable,
    canal y derechos (datos aprobados por la firma en el plan P0), pero
    `NEXT_STEPS.md` aún lo lista pendiente de aprobación formal y no hay página
    `/privacidad` propia ni enlace en el pie. Confirmar con la firma antes de
    publicar.
12. **Contenido editorial** (noticias) marcado «Pendiente de aprobación» en la
    portada.

## 3. Lo que sí está listo

- **Backend:** fases 0A–10 completas; RBAC por endpoint, Argon2, sesiones con
  rotación/revocación, `token_version`, auditoría saneada, rate limiting en
  Redis, cabeceras de seguridad, `assert_production_is_safe`.
- **Antivirus:** ClamAV 1.5.4 integrado en evidencias y documentos con política
  de cuarentena y fallo cerrado.
- **Calidad:** CI verde en HEAD; cobertura >80 %; los gates pasan sobre el
  snapshot validado; ceilings fijados en `pyproject.toml` (ADR-063).
- **Frontend:** typecheck/lint/build verdes; web pública con 19–25 regresiones
  Playwright; portal, administración (16 módulos) y gestor de evidencias.
- **Respaldos locales:** verificación por digest antes de copiar (ADR-062) y
  ensayo de restauración previo documentado.
- **Runbook:** `docs/DEPLOY.md`, `docs/RESTORE.md` y guías de las últimas
  entregas.

## 4. Plan mínimo de salida (en orden)

1. **Restaurar los gates del árbol:** decidir el destino de los cambios de
   multimedia en `app/api/v1/media.py` + `app/services/media.py` (completar el
   refactor o apartarlos). Mínimo: importar `HEADER_BYTES`,
   `detect_media_type`, `MediaValidationError`, quitar `asyncio` y alinear el
   kwarg de `attach_file_stream`. Verificar `ruff` + `mypy` + `pytest`.
2. **Arreglar la continuación `RUN` de `backend/Dockerfile`** (línea 35: falta
   `\`) y validar con `docker build --check` / build real.
3. **Commit/push de la recuperación de contraseña** (con autorización) y
   confirmar CI verde; aplicar `ff60718293a4` a la base local con respaldo previo.
4. **Infraestructura:** host de producción, dominio + HTTPS/reverse proxy,
   `.env` de producción (`APP_ENVIRONMENT`, `SECRET_KEY`, `CORS_ORIGINS`
   sin comodines), S3 externo con versionado, reanudar `scripts/backup.sh`
   diario y repetir el ensayo de restauración con otra persona.
5. **SMTP + fase 6** para activar la recuperación de contraseña y las
   confirmaciones por correo.
6. **Aprobaciones de la firma:** aviso de privacidad (página/enlace) y
   contenido editorial.

---

*Evidencia: corrida CI #7 (`de6d18a`), ejecución local de gates el 2026-11-17,
`docker build --check`, inspección de `compose.yaml`, `.env.example`, `backups/`
y memoria del proyecto (`CURRENT_STATE.md`, `KNOWN_ISSUES.md`, `NEXT_STEPS.md`).*
