# Última sesión

## 2026-11-17 — Plan de producción: fases 0 y 1 ejecutadas

- Autorización del usuario: iniciar fase 0 y **commitear/pushear cada fase
  terminada**. Decisión [FIRMA] registrada: el parche `AI_CONFIDENTIALITY`
  (`legal_ai.py` + `config.py`) se **aparta a rama**
  `feature/ai-confidentiality` (`e640e3d`, ya en el remoto); nada descartado,
  `main` queda sin él.
- **Fase 0 (gates) completada — commit `4bfbaf0` en `main`:**
  - `PUT /media/{id}/content`: cap restaurado midiendo con `seek/tell`
    **antes** de llamar al servicio (un 413 no puede tocar el objeto
    reemplazado; el test exige `has_file is False`), detección duplicada
    rota eliminada, kwarg `mime_type` inexistente fuera,
    `get_running_loop()`.
  - `attach_file_stream`: el peek del tipo **truncaba el objeto en el
    primer chunk** (los bytes consumidos no se devolvían) — resuelto con
    `_with_prefix()`; el poster de imágenes se genera releyendo el objeto
    recién escrito (antes ambas ramas hacían `_drop_thumbnail`: la
    biblioteca habría perdido todas las miniaturas).
  - `backend/Dockerfile`: continuación `RUN` reparada (faltaba `\`;
    `unknown instruction: pg_dump` rompía cualquier build completo).
  - **Gates en verde sobre el árbol completo:** `ruff` limpio, `mypy`
    limpio (194 archivos), **936/936 pruebas, cobertura 85,87 %**,
    `docker build --check` sin errores; frontend sin cambios desde su
    `tsc`/ESLint/`next build` verdes. `docker compose build backend`
    completo lanzado para validar la imagen.
- **Fase 1 (versionado):** tres commits — `feat(auth)` recuperación de
  contraseña (backend+frontend+migración+docs+CHANGELOG), `test(e2e)`
  `admin-portal.spec.ts` y `docs` (informe, plan, memoria) — push conjunto a
  `origin/main`.
- **Incidente CI en fase 1 (resuelto):** el run #10 falló en *Secrets scan*
  con `ERROR: Unexpected exit code [1]` (los demás gates quedaron saltados).
  Causa raíz reproducida: la acción usa gitleaks **8.24.3** y en pushes
  multi-commit escanea `commits[0]^..commits[last]`; el checkout shallow
  (depth 1) no tiene ese revision → `git log` falla → exit 1. Los pushes de
  un solo commit usan `--log-opts=-1` y por eso pasaban. Corrección:
  `fetch-depth: 0` en el checkout del job de backend (con comentario en el
  workflow). Aprendizaje registrado en `learnings.md`. El run se repite con
  el push del fix (multi-commit, ejercitando la corrección) y **tag
  `v1.0.0-rc1` tras CI verde**.

## 2026-11-17 — Plan completo para producción entregado

- Solicitud: «Entrega un plan completo para dejar listo para Producción».
- Entregado `docs/PLAN_PRODUCCION.md`: 8 fases (0 gates del árbol → 1
  versionado/tag → 2 BD+stack → 3 decisiones de la firma en paralelo →
  4 infraestructura/HTTPS → 5 respaldos → 6 SMTP/recuperación → 7 aceptación →
  8 operación), con tareas marcadas **[FIRMA]**/**[AGENTE]**, criterios de
  aceptación por fase, orden de dependencias y checklist global de salida.
- Decisiones clave que quedan para la firma (10 en la fase 3): dominio,
  TLS/proxy, bucket S3 externo + Object Lock, destino del respaldo remoto,
  SMTP, `AI_CONFIDENTIALITY`, aviso de privacidad, editorial, zona horaria y
  confirmación por correo de solicitudes.
- Recomendación para el punto 0.1: intentar el arreglo mínimo de
  `media.py` (importar los tres nombres, quitar `mime_type=` — el servicio ya
  detecta el tipo — y quitar `asyncio` sin uso); si `test_media.py` no queda
  en verde en esa sesión, apartar `media.py`/`services/media.py` a rama
  `feature/media-streaming` **sin descartar**. Igual criterio para el parche
  `legal_ai.py` (`AI_CONFIDENTIALITY`).
- Sin ejecución de fases todavía: el plan queda pendiente de aprobación.

## 2026-11-17 — Informe de preparación para producción

- Solicitud: «Entrega un informe para ver si ya está listo para producción».
- Entregado `docs/INFORME_PRODUCCION_2026-11-17.md`: **veredicto NO LISTO**.
- Evidencia ejecutada hoy: CI verde (#7 sobre `de6d18a`); `ruff` y `mypy`
  **rojos** con 4 errores cada uno y `pytest` con **17 fallos (todas
  `test_media.py`, `NameError`) sobre 936** — árbol de trabajo, no la release
  validada; cobertura 84,74 %. Frontend `tsc`/ESLint/`next build` verdes.
  `docker build --check` confirma el `Dockerfile` roto (línea 36,
  `unknown instruction: pg_dump`: falta `\` en la línea 35).
- Causa raíz: el refactor pendiente de multimedia dejó `app/api/v1/media.py`
  sin importar `HEADER_BYTES`/`detect_media_type`/`MediaValidationError` (el
  servicio sí los exporta) y llama `attach_file_stream(..., mime_type=...)`,
  kwarg que la firma no tiene. Trabajo sin validar y fuera de las releases
  desplegadas; **no descartarlo**, decidir su destino con el usuario.
- Otros hallazgos: stack local principal caído (~46 h; `evidence-worker` en
  crash loop por DNS de postgres), último respaldo local **2026-10-22**,
  `BACKUP_REMOTE_ENABLED=false`, sin nginx/HTTPS/dominio, SMTP sin configurar
  (recuperación apagada), migración `ff60718293a4` sin aplicar en la base
  local, entrega de recuperación **sin commit/push** (30 modificados + 21
  nuevos). Aviso de privacidad ya con responsable/canal/derechos en el
  diálogo, pero `NEXT_STEPS` aún lo lista pendiente de aprobación formal.
- Sin cambios de código de producto; solo este informe y la memoria.

## 2026-11-15 — «Olvidé mi contraseña» implementado y validado (sin activar)

- Solicitud: «Autorizado ejecutalo» + «hola, continua» → implementar el plan
  `docs/PLAN_OLVIDE_CONTRASENA.md` con cuentas/correo sintéticos y buzón SMTP
  aislado; **el envío real queda apagado** hasta configurar SMTP, remitente y
  origen HTTPS.
- Implementación completa: permiso/recovery `token_version`, migración
  `ff60718293a4` (tokens + outbox cifrada + `users.recovery_invalidated_at`,
  reversible), endpoint anónimo `/auth/forgot-password` con respuesta genérica,
  outbox cifrado + worker `app.cli.recovery_worker` (perfil compose `recovery`),
  consumo atómico con Argon2 y revocación, límites por IP/global/destino en
  middleware **antes** de validar JSON (411/413/429), flujo `/olvide-contrasena`
  y `/restablecer-contrasena`, enlace de login y `PASSWORD_RECOVERY_*` apagados
  por defecto en `compose.yaml`/`.env.example`.
- **Verificado:** **936 pruebas backend, 85,82 %** cobertura, Ruff/mypy limpios
  (153 archivos), migración downgrade/upgrade en base efímera; typecheck frontend
  limpio, lint con el único warning preexistente del portal, build OK.
- **E2E en verde contra el artefacto final** (stack aislado con base tmpfs,
  imagen `wabogados-password-recovery:local` + frontend reconstruido):
  `password-recovery` 3, `public` 19, `layout` 66 + 1 skip, `password-reset` 2 y
  `private` 4 (para `private` hizo falta sembrar `Client` + `Case` por API: sin
  expedientes el recorrido falla por datos, no por código). Siembras efímeras en
  `.tmp/*-auth.json` (0600); nada desplegado al stack local principal.
- **Fallo preexistente corregido:** `frontend/e2e/admin-portal.spec.ts` quedó
  desactualizado en `de6d18a` (esperaba «Usuarios» en `/admin/seguridad`, que
  ahora es «Auditoría»; no listaba los módulos nuevos; contaba 13 enlaces fijos
  en el menú móvil). Se actualizó el listado con los headings verificados y el
  contador se deriva de `ADMIN_MODULES`. Sin relación con la recuperación.
- Documentación: `docs/RECUPERACION_CONTRASENA.md`, cabecera del plan en
  «implementada», entrada en `CHANGELOG.md`. **Sin commit/push** (pendiente de
  autorización); pendientes ajenos intactos y fuera del alcance.
- **Fase 6 pendiente:** proveedor SMTP, remitente autorizado, origen público
  HTTPS y aprobación de elegibilidad/límites antes de activar envíos reales.
- Decisión del usuario al cerrar: **esperar a los datos de correo**; la entrega
  queda sin commit/push y sin despliegue al stack local. El stack aislado de
  revisión sigue levantado para inspección (`http://127.0.0.1:3013`, credenciales
  en `.tmp/e2e-layout-credentials.json`, 0600) y se retira con
  `docker compose -p wabogados-recovery-review -f .tmp/recovery-review.yaml down`.

## 2026-11-15 — Plan de «Olvidé mi contraseña» entregado

- Solicitud: entregar plan, **sin implementar ni activar**. Documento:
  `docs/PLAN_OLVIDE_CONTRASENA.md`, fases 0–6, requisitos y aceptación.
- Propuesta: correo verificado/cuenta activa, token opaco de 20 minutos y un uso,
  respuesta genérica, límites, outbox cifrada/worker, consumo atómico con Argon2,
  `token_version` y revocación; pantallas accesibles y pruebas aisladas/concurrencia.
- Pendientes de aprobación: proveedor/remitente/URL HTTPS, elegibilidad y límites;
  después implementación, pruebas y autorización de activación. No se envió correo,
  no se tocaron cuentas, migraciones ni código. Sin commit/push de este plan.
- Publicación anterior confirmada: `de6d18a` en `origin/main`. Pendientes ajenos
  de multimedia/IA/Dockerfile y auditoría siguen intactos y fuera del commit.

## 2026-11-15 — Publicación autorizada de Usuarios/Roles y contraseñas

- El usuario solicita commit y push de la entrega nueva y explicación del flujo
  «Olvidé mi contraseña». Esta solicitud no autoriza todavía su implementación.
- Se publican Usuarios/Roles, restablecimiento administrativo, migración,
  pruebas, guía y memoria. Se excluyen Dockerfile, media/API/servicio, configuración
  IA, servicio IA y auditoría anterior sin validar; no se descartan esos pendientes.
- Destino `origin/main` (`github.com/eneldo/wabogados`); resultado e identificador
  definitivos consultables en Git. La nota «sin commit/push» de la entrega de abajo
  describe su cierre previo a esta autorización.
- Typecheck/lint frontend repetidos antes de publicar: correctos, con warning
  previo del portal. Resultados backend/build/E2E anteriores conservados abajo.
- Recuperación propuesta: correo con enlace aleatorio de un solo uso y caducidad,
  respuesta sin enumerar cuentas, nueva clave confirmada y revocación de sesiones.
  Pendiente definir/configurar servicio de correo y remitente; no enviar claves.

## 2026-11-15 — Restablecimiento administrativo implementado y activo

- Usuario autorizó continuar el cambio desde administrador; recuperación por
  «Olvidé mi contraseña» queda para después. No se cambiaron claves reales.
- `/admin/usuarios`: acción separada **Restablecer contraseña**, cuenta visible,
  confirmación, mostrar/ocultar, 8–128 caracteres sin recortar espacios, limpieza
  al cerrar/responder, foco/Escape y prevención de doble envío. Excluye cuenta
  propia, inactivos y superusuarios cuando el actor no lo es.
- API `POST /api/v1/admin/users/{user_id}/reset-password`, permiso sembrado
  `users:reset_password`; hash Argon2, incremento de `token_version`, revocación
  de refrescos y auditoría `admin_password_reset` atómicos. JWT previos rechazados;
  tokens heredados sin versión se aceptan solo mientras el usuario tenga versión 0.
- Login/emisión/refresh/reset serializan por bloqueo de usuario y releen tras
  esperar. PATCH/alta impiden eludir protección mediante cambios de superusuario.
  422 ya no devuelve `input`/`ctx`; presupuesto sensible separado para reset.
- **Verificado:** 895 tests backend, **85,56 %** cobertura; Ruff/mypy limpios;
  migración upgrade/downgrade/upgrade en base efímera. Typecheck/build frontend
  OK; lint 0 errores, warning previo del portal. 2 E2E reales de reset y 19
  públicos pasan; los 19 públicos repetidos sobre la instalación local desplegada.
  Revisión visual 390/1440 y controles internos/overflow 320/390/768/1440.
- La primera corrida amplia falló por entorno: backups esperan el hostname y
  base canónicos `postgres-test/wabogados_test`. Separados gates y E2E, con
  PostgreSQL/Redis propios; última corrida completa verde. No se ocultaron tests.
- **Activo localmente:** migración `fe5f60718293`, imagen reproducible
  `wabogados-password-reset:local` también etiquetada como backend de Compose.
  Snapshot `.tmp/scoped-backend-ys8oavur/backend`, manifest con lista y hashes.
  Incluye los tres archivos previos de Usuarios/Roles ya activos, excluye los
  pendientes ajenos de Dockerfile/multimedia/IA. Backend/frontend saludables;
  portada/ready HTTP 200 y contrato nuevo presente en OpenAPI.
- Respaldo previo PostgreSQL `.tmp/password-reset-predeploy-20261115.dump`,
  modo 0600, catálogo `pg_restore --list` verificado; imagen previa conservada
  `wabogados-backend-before-password-reset:local` (no captura el hot-patch antiguo
  de Roles). Tras resets no volver al código viejo ni bajar versión sin planificar
  invalidación general: reintroduciría aceptación de JWT antiguos (ADR-065).
- Guía: `docs/RESTABLECIMIENTO_CONTRASENAS.md`. Plan original actualizado,
  CHANGELOG y contexto registrados. Sin commit/push. Temporal de autenticación y
  contenedores de revisión se retiran al cierre; capturas/logs quedan en `.tmp/`.

## 2026-11-15 — Diagnóstico y plan de restablecimiento en Usuarios

- Solicitud del usuario: verificar `/admin/usuarios` y entregar plan; no implementar.
- Navegador autenticado: HTTP 200; «Nuevo usuario» sí permite clave inicial
  (8–128 caracteres), pero «Editar» no tiene contraseña y no hay botón de reset.
  OpenAPI desplegado confirma que `UserUpdateAdmin` no recibe contraseña y que
  falta endpoint de restablecimiento. Formularios no enviados; sesión cerrada.
- Plan guardado en `docs/PLAN_RESTABLECIMIENTO_CONTRASENAS.md`: acción separada,
  permiso dedicado sembrado, validación/Argon2, invalidación de refrescos y JWT
  de acceso, auditoría sin secretos, pruebas aisladas y despliegue reproducible.
- Riesgos a cubrir: el esquema impide aprovechar las ramas antiguas de password
  de los servicios; revocar refrescos no invalida JWT de acceso; errores 422
  conservan `input` y deben sanearse para secretos. Usuarios/Roles y pendientes
  anteriores del backend siguen sin commit; evitar build completo a ciegas.
- Sin cambios de código/cuentas, sin ejecutar reset, sin commit/push. Pendiente
  autorización para implementar; cambio propio y recuperación por correo se
  distinguen como fases opcionales.

## 2026-11-15 — Restablecimiento de acceso administrador autorizado

- Restablecida la contraseña de la cuenta administradora existente a petición
  expresa del usuario. El acceso sigue usando correo electrónico, no el alias
  literal «admin»; no se modificó el contrato de autenticación ni los roles.
- Contraseña almacenada solo como hash Argon2 en PostgreSQL; no se guarda aquí
  ni en archivos del repositorio. Operación registrada en auditoría como
  `password_reset_authorized_local`, sin secretos.
- Revocadas 4 sesiones de refresco previas. Verificados login e identidad
  administradora por HTTP 200; sesión temporal de comprobación cerrada.
- Sin cambios de código ni commit/push para esta operación.

## 2026-11-15 — Imagen de la Justicia en la portada

- Sustituido solo el SVG de columnas/balanza a la derecha del titular por la
  imagen aportada `Logo de Justicia.png`. Cabecera, pie, marco y textos conservados.
- `execution/prepare_public_justice.py` genera
  `frontend/public/marca/logo-justicia.webp` sin pérdida ni recorte (1219 × 1290;
  1.126.684 bytes). Original intacto; píxeles RGBA idénticos comprobados.
  SHA-256 original: `6ba26e029d239f8500295747c1ef8646af821ba0a6be2cabaa0b7e669f3f9a7a`.
- Modificados `frontend/app/(public)/page.tsx`, `frontend/app/public-site.css`,
  `frontend/e2e/public-site.spec.ts` y `docs/IDENTIDAD_WEB_PUBLICA.md`.
  Imagen completa y proporcionada, fondo claro para que se lean las letras negras.
- Typecheck OK; lint 0 errores y warning previo del portal; build Docker OK.
  Solo frontend reconstruido/recreado, saludable en `http://localhost:3000`.
  **19 pruebas públicas pasan**, con nuevas verificaciones de descarga real,
  MIME, proporción y límites del marco en 320–2560 px. Capturas revisadas:
  `.tmp/public-brand-review/justice-{390,1920}.png`.
- Commit y push de esta entrega autorizados por el usuario; consultar Git para
  el hash y resultado final de publicación en `origin/main`. Se incluyen el PNG
  original, derivado WebP, generador, frontend, pruebas y esta documentación.
  No se tocó backend ni se descartó trabajo previo; sus pendientes quedan fuera.
  La entrega P0–P3 anterior sí se publicó en `fd581df`; las notas «sin commit»
  de sus apartados inferiores son históricas.

## 2026-11-15 — Ejecución Plan P0 mejora web pública (autorizado)

- **Aplicación ejecutada localmente:** stack levantado con contenedores/imágenes existentes (`docker compose up -d postgres redis backend frontend clamav`, sin rebuild). Frontend `http://localhost:3000` y backend `/api/v1/health/ready` en **HTTP 200**; postgres/redis/clamav saludables. `evidence-worker` en reinicio (no bloquea la web pública; pendiente de revisión operativa).
- **Plan P0 (1–3) en curso**, con registro en memoria antes de cada paso siguiente.
  - **Paso 1 (confianza/legal/contacto): COMPLETADO** con datos aprobados por la firma (correo `amiabogado@hotmail.com`, razón social WABOGADOS, responsable William Andres Ruiz, canal Edificio Berna Carrera 9 No. 16-20 Oficina 206, Bogotá; confirmación explícita de retirar notas pendientes). Actualizados `frontend/app/(public)/page.tsx`, `frontend/components/public/contact-form.tsx`, `frontend/components/public/site-header.tsx`. Frontend validado (`typecheck` OK, `lint` 0 errores + warning previo portal) y **reconstruido/re desplegado**; verificado en portada sin "por confirmar"/"Pendiente de revisión" y con correo visible. Detalle en `memory/P0_PUBLIC_SITE_PLAN.md`.
  - **Paso 2 (claridad/conversión del formulario): COMPLETADO** en `frontend/components/public/contact-form.tsx` (expectativa de respuesta y alternativa telefónica visibles, microcopia de privacidad, validaciones accesibles por campo con `aria-invalid`/`aria-describedby`, foco en primer error; contrato 201/sin borrado en fallo preservado). Frontend validado, reconstruido y redesplegado.
  - **Paso 3 (prueba social sin inventar): COMPLETADO** en `frontend/app/(public)/page.tsx` (copy de equipo ajustado para confianza/cercanía sin inventar credenciales, años, casos ni reconocimientos; retirada nota "Pendiente" del equipo). Frontend validado, reconstruido y redesplegado.
- Ajuste colateral mínimo: `frontend/components/admin/roles/role-form.tsx` para corregir error de lint `set-state-in-effect` (sin cambio funcional previsto). Cambios en árbol sin commit/push. **P0 (1–3) completado.**

## 2026-11-15 (continuación) — Ejecución Plan P1, P2 y P3 mejora web pública (autorizado)

- **P1 (4–7) completado:** jerarquía/CTA y orientación "cuándo acudir" en servicios, estado del sistema con enlace a `/estado`, CTA móvil discreto Llamar/Consultar, y estado vacío de Criterio Legal más claro.
- **P2 (8–10) completado:** `frontend/lib/site.ts`, metadatos/OG/Twitter/canonical y JSON-LD verificado, `robots.ts`/`sitemap.ts`, optimización segura de imágenes no críticas y accesibilidad básica (skip link, `main#contenido-principal`).
- **P3 (11–13) completado:**
  - **Paso 11:** embudo estimado en `/admin/estadisticas-web` (portada → áreas → clics teléfono → solicitudes registradas) con interpretación agregada; `docs/ESTADISTICAS_WEB.md` actualizado.
  - **Paso 12:** NAP unificado con `SITE_CONTACT` en footer público y enlace "Cómo llegar" en contacto.
  - **Paso 13:** prueba pública ajustada al copy vigente y documentación actualizada (`docs/IDENTIDAD_WEB_PUBLICA.md`); **Playwright `--project=public` 19/19 aprobadas**.
- Cada paso registrado en memoria antes de continuar. Frontend validado (`typecheck` OK, `lint` 0 errores + warning previo portal), reconstruido y redesplegado según pasos. **P0–P3 completados.** Cambios en árbol sin commit/push. Detalle en `memory/P0_PUBLIC_SITE_PLAN.md`.

## 2026-11-11 (continuación) — Módulos Usuarios y Roles separados (opción B)

- Separados en el administrador los módulos **Usuarios** (`/admin/usuarios`,
  `users:read`) y **Roles** (`/admin/roles`, `roles:read`). **Seguridad**
  (`/admin/seguridad`, `audit_logs:read`) queda enfocada en auditoría y redirige
  `?vista=usuarios|roles` a los nuevos módulos.
- **Usuarios**: crear, editar, desactivar/reactivar cuentas y asignar/revocar roles
  (reutiliza componentes y acciones de seguridad, con revalidación en
  `/admin/usuarios`). Permite asignar roles como administrador, abogado, cliente,
  asistente u otros existentes.
- **Roles (CRUD completo)**: crear, editar (nombre, descripción, permisos) y
  eliminar roles; asignación de permisos agrupados por recurso. Eliminación solo si
  el rol no está asignado a usuarios. Gestión protegida por `roles:manage` y
  `permissions:read`.
- Backend: `RoleCreate`/`RoleUpdate` en `backend/app/schemas/identity.py`; métodos
  `get_role`, `create_role`, `update_role`, `delete_role`, validación de permisos
  y permisos en `backend/app/services/identity.py`; endpoints
  `POST/PATCH/DELETE /api/v1/admin/roles` en `backend/app/api/v1/admin.py`.
- Frontend: navegación e iconos (`frontend/lib/admin-nav.ts`,
  `frontend/components/admin/icons.tsx`), páginas `admin/usuarios` y `admin/roles`,
  acciones/componentes de roles (`frontend/features/roles/*`,
  `frontend/components/admin/roles/*`), auditoría simplificada en
  `frontend/app/(admin)/admin/seguridad/page.tsx`.
- **Verificación**: `npm run typecheck` frontend OK; `py_compile` de archivos
  backend modificados OK. Pruebas funcionales API (token admin local): roles listados
  (abogado, administrador, asistente, cliente), permisos disponibles,
  `POST/PATCH/DELETE /api/v1/admin/roles` probados con rol de prueba (201/200/204)
  y `GET /api/v1/admin/users` OK. Frontend reconstruido; rutas `/admin/usuarios`,
  `/admin/roles`, `/admin/seguridad` presentes y protegidas (307 a login sin sesión).
- **Despliegue local aplicado sin rebuild completo de backend**: se copiaron los 3
  archivos backend modificados al contenedor `backend` en ejecución y se reinició
  (saludable). No se reconstruyó la imagen completa porque el `backend/Dockerfile`
  del árbol tiene cambios previos no validados/rotos (multimedia/IA); el build
  completo fallaría o mezclaría pendientes. Frontend sí reconstruido con
  `docker compose up -d --build --no-deps frontend`. Para persistir en imagen,
  usar build revisado/scoped que incluya estos cambios.
- Cambios sin commit ni push. Pendientes previos de multimedia/IA/Dockerfile/S3
  siguen sin resolver.

## Publicación autorizada por el usuario — 2026-11-11

- El usuario solicitó commit y push de la entrega verificada: portada, servicios,
  iconos, analítica privada, pruebas, documentación y memoria.
- Destino: rama `main` de `origin` (`github.com/eneldo/wabogados`). El identificador
  y estado final de publicación deben consultarse en Git, no deducirse de las
  notas históricas «sin commit/push» de los cierres anteriores.
- Se excluyen los cambios previos sin validar de Dockerfile/multimedia/IA y la
  revisión anterior de auditoría. El historial versionado de aprendizajes se
  conserva; se incorporan los nuevos aprendizajes sin publicar su truncado previo.
- No se incluyen `.env`, respaldos, sesiones, capturas ni artefactos `.tmp/`.

## Cierre y relevo guardados por solicitud del usuario

- Estado consolidado actualizado en `memory/CURRENT_STATE.md`; contexto,
  funcionalidades, siguientes pasos, decisiones y aprendizajes enlazados desde
  `memory/README.md`. Las secciones anteriores se conservan como antecedentes.
- Backend y frontend siguen activos y saludables. La instalación de revisión se
  eliminó al terminar y también su credencial temporal; no se guardan secretos
  en esta memoria. El respaldo previo permanece disponible.
- Al guardar la memoria todavía no se había hecho commit/push. La autorización
  posterior se registra arriba; nunca autoriza a descartar los pendientes previos.

## 2026-11-11 — Analítica privada de la web pública implementada y activa

- Panel `/admin/estadisticas-web`, en el menú **Estadísticas web**, protegido por
  `website_analytics:read` (administrador por defecto y autorización en backend).
  Muestra vistas, navegaciones estimadas acumuladas por día, clics telefónicos,
  solicitudes realmente registradas, áreas/páginas y evolución diaria/mensual.
- Sin cookies, storage de navegador, IP, fingerprint ni datos de formularios en
  la analítica. UUID aleatorio solo en memoria; dedup por día e idempotencia por
  evento con digests de 48 h, purga horaria y agregados de 400 días. Se respetan
  DNT/GPC; no se montan colectores en superficies privadas. Una recarga/pestaña
  puede contar otro visitante: no son personas exactas ni únicos mensuales.
- Migración `fd4e5f607182` aplicada localmente: tres tablas y permiso sembrado.
  Flag `WEBSITE_ANALYTICS_ENABLED=true` en Compose backend/frontend.
- Archivos: backend `models`, `schemas/services/api/v1/website_analytics.py`,
  `services/consultations.py`, permisos, auditoría y presupuesto independiente;
  frontend `components/public/public-analytics.tsx`, `app/api/estadisticas/route.ts`,
  panel, navegación y aviso público. Documentación: `docs/ESTADISTICAS_WEB.md` y
  ADR-064 en `memory/DECISIONS.md`.
- **Verificación real:** release aislada basada en Git HEAD `0d91b47` + archivos
  de analítica: **881 tests backend, 85,77 % cobertura**, ruff/mypy limpios y
  migración upgrade/downgrade/upgrade correcta. **25 tests Playwright** pasan en
  una instalación efímera separada, incluido ingreso real de eventos, dedup,
  permisos, panel admin, filtros, vacíos y layout 320–1440. No se usaron visitas,
  credenciales ni solicitudes reales para llenar demostraciones.
- Frontend build y TypeScript correctos. Lint sin errores, con el warning previo
  del portal en `portal/casos/[caseId]/page.tsx:288`. Captura sintética revisada:
  `.tmp/website-analytics-review/dashboard-1440.png`.
- **Despliegue selectivo:** `execution/prepare_scoped_backend.py` conserva el
  árbol de trabajo y prepara HEAD + lista explícita revisada. No se desplegaron
  los cambios anteriores incompletos de multimedia/IA/Dockerfile. Contexto en
  `.tmp/website-analytics-context.txt`, con manifest/hashes dentro del snapshot.
  Imagen `wabogados-website-analytics:local`, etiquetada además como
  `wabogados_v1_master-backend:latest` para Compose. Respaldo de la imagen anterior:
  `wabogados-backend-before-website-analytics:local`.
- Respaldo PostgreSQL previo verificado (pg_restore --list), permisos 0600:
  `.tmp/website-analytics-predeploy-20261111T233549Z.dump`. No se eliminaron datos.
  Backend/frontend saludables y raíz/ready 200; resumen público sin token 401.
  Los contadores locales empiezan al activarse, sin datos sintéticos importados.
- **Pendiente ajeno a esta tarea:** el Dockerfile y streaming/IA anteriores siguen
  sin validar en el árbol real; no reconstruir ese backend completo sin revisarlos.
  Los 881 tests corresponden al snapshot publicado, no a esos cambios pendientes.
  No se hicieron commit ni push.

## 2026-11-11 — Iconos semánticos de servicios

- Sustituidos los símbolos Unicode por SVG uniformes en las tarjetas públicas.
  Laboral: maletín; Penal: escudo; Familia: personas; Inmobiliario: casa, y un
  icono específico para cada una de las demás áreas del catálogo actual.
- `frontend/lib/public-services.ts` asigna el icono por nombre normalizado y
  contempla las etiquetas de respaldo; el orden de las tarjetas no lo cambia.
  Componente: `frontend/components/public/service-icon.tsx`. Sin dependencias
  nuevas, cambios del backend ni alteraciones de los enlaces de consulta.
- Frontend reconstruido y publicado en `http://localhost:3000`.
  Build y TypeScript correctos; lint sin errores (warning previo del portal).
  **19 pruebas públicas pasan**, incluidas semántica, reordenamiento, respaldo,
  SVG decorativos y navegación existente. Captura revisada en
  `.tmp/public-brand-review/services-1920.png`. Cambios sin commit/push.

## 2026-11-11 — Servicios públicos con páginas propias

- «Consultar esta área» abre ahora `/servicios/<slug>` en vez de `#contacto`.
  Se verificaron las doce tarjetas actuales, su descripción, el área
  preseleccionada y el regreso a la portada. Las rutas inexistentes y la caída
  del catálogo tienen estados diferenciados.
- Archivos principales: `frontend/app/servicios/[slug]/page.tsx`,
  `frontend/lib/public-services{,.server}.ts`,
  `frontend/lib/consultation-areas.ts`, `frontend/app/api/consultas/route.ts`,
  `frontend/components/public/{contact-form,site-header}.tsx` y pruebas públicas.
- El formulario general y el de detalle usan el catálogo vigente. El adaptador
  de Next conserva el área exacta en el mensaje al normalizar al contrato antiguo
  de consultas; áreas sin equivalente van a «Otra consulta». Se rechazan nombres
  no publicados y mensajes que excedan el límite con el prefijo. No se reconstruyó
  ni modificó el backend para esta tarea.
- Catálogo público con revalidación de 30 segundos y sin precarga de todas las
  tarjetas para evitar agotar el límite compartido de API. No se cachean datos
  privados. El formulario solo confirma con HTTP 201 y conserva datos si falla.
- Validaciones: build Docker y TypeScript correctos, lint sin errores (persiste
  el warning previo del portal), **17 pruebas públicas pasan**. Se validaron en
  memoria los 12 payloads contra `ConsultationCreate` del backend desplegado,
  sin escribir registros ni consumir el presupuesto de envíos de consultas.
  El rechazo del formulario se prueba con respuesta simulada; no se hizo un
  envío real de extremo a extremo. Capturas desktop/móvil en
  `.tmp/public-brand-review/service-administrativo-*.png`.
- Frontend reconstruido y activo en `http://localhost:3000`; ejemplo:
  `http://localhost:3000/servicios/administrativo`. Cambios sin commit/push.

## 2026-11-11 — Arranque local y rediseño de la página principal

- Backend y frontend activos en Docker: `http://localhost:8000/docs` y
  `http://localhost:3000`. Se recrearon contenedores sin eliminar volúmenes.
- Portada rediseñada en `frontend/app/(public)/page.tsx` y
  `frontend/app/public-site.css`: hero editorial, contacto telefónico, ilustración
  enmarcada, servicios numerados y refinamiento de equipo, principios y portal.
  Estilos limitados a `.public-home`; se conservan marca, formularios y permisos.
- Se reconstruyó y publicó **solo el frontend**, con `docker compose build
  frontend` y `docker compose up -d --no-deps --wait --wait-timeout 90 frontend`.
- Verificado: build Docker y TypeScript correctos; ESLint sin errores y con un
  warning previo en `frontend/app/portal/casos/[caseId]/page.tsx:288`.
  **13 pruebas públicas Playwright pasan** entre 320 y 2560 px, incluyendo menú,
  teclado, privacidad, enlaces y ausencia de overflow. Revisión visual de capturas
  en `.tmp/public-brand-review/`; portada también visible sin JavaScript.
- Se eliminó del test de layout el supuesto obsoleto de siete servicios: el
  catálogo activo publica doce. Documentación: `docs/IDENTIDAD_WEB_PUBLICA.md`.
- Los cambios previos del backend siguen sin resolver y no se desplegaron.
  El Dockerfile local tiene una continuación RUN rota y la implementación de
  streaming/IA anterior no está validada; **no declarar esos cambios terminados ni
  reconstruir backend sin revisarlos**. Tampoco se confirmó ni empujó este trabajo.
- Siguiente paso: revisión del aspecto de la portada por el usuario.

## Resumen anterior (conservado como antecedente)

Fecha: 2026-11-11 — auditoría del proyecto (ver `AUDIT_2026-11-11.md`)

## Resumen
Auditoría cruzando memoria con el estado real. Las 11 fases de producto
(0A–10) y los módulos V3/V4/V5 están construidos y cubiertos con suite de tests,
ruff y mypy estrictos en verde (857 passing). Riesgo principal: el ciclo del
2026-11-08 (portal, solicitudes, hitos, análisis IA, endurecimiento de
mensajería) fue cerrado, commitado y empujado al remote (`0d91b47`).

## Pendientes por decisión de la firma (código ya listo)

### 1. Multimedia: transcodificación y worker
**Código:** `ffmpeg` falta en `Dockerfile`, `write_stream` existe en Storage/LocalStorage/S3 pero no se llama desde la ruta `PUT /media/{id}/content`, y el worker de `media_processing_jobs` no está implementado (patrón a copiar: `evidence_worker` con `SKIP LOCKED`). El modelo tiene `duration_seconds` y el schema `MediaUpdate` aún rechaza el campo.

**Qué decidir la firma:** Presupuesto/tiempo para instalar `ffmpeg`, implementar `write_stream` en la ruta y crear el worker de Compose.

### 2. S3: destino externo y inmutabilidad
**Código:** CLI `import_documents_to_s3.py` corregido (`--rekey`, `--offset`), migración `document_versions` lista, `.env.example` con `STORAGE_BACKEND=s3`. Faltan `evidence_files`, `evidence_derivatives`, `message_attachments`, `media_items` en el CLI. Object Lock/inmutabilidad sin decidir.

**Qué decidir la firma:** Crear cuenta, bucket con versionado y credencial dedicada en otro proveedor S3; política Object Lock sí/no.

### 3. IA Jurídica: confidencialidad del proveedor
**Código:** `POST /ai/generate` con OpenAI/Anthropic y `generate_draft` ya codeado, `provider_configured()` declara ausencias, `IaGenerate` renderizado, `.env.example` con `AI_*` documentados, docstrings corregidos. **Falta:** decisión de confidencialidad de datos de clientes hacia el proveedor externo.

**Qué decidir la firma:** Política `AI_CONFIDENTIALITY` (`NONE`/`ANONYMIZED`/`FULL`), saneado mínimo en `generate_draft`, y documentarlo en la pantalla.

## Gates verificados
- `ruff check .` — 0 errores.
- `mypy app` — 0 errores.
- `pytest app/tests/ -q` — 857 passing, 85.57% cobertura.

---

# Sesión anterior (2026-11-08 continuada)
- Configurar proveedor de IA para activar generación.
- Probar CRUD de análisis y sincronización de notificaciones con cuenta admin.
- Añadir CRUD admin para noticias si se requiere editor visual.

## Mejoras visuales (esta continuación)
- Portada: hero con degradado, botones con gradiente/sombra, tarjetas con glow.
- Portales privados y login: fondo con degradados sutiles, tarjetas con elevación, panel login con degradado.
- Iconos de áreas de práctica diferenciados.
- Equipo público restaura las 3 personas originales.
