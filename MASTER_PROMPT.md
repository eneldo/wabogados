# MASTER_PROMPT — WABOGADOS V1
## Plataforma Integral de Gestión Jurídica con Motor Profesional de Evidencias

> Este documento es la fuente principal de verdad funcional, técnica y operativa del proyecto WABOGADOS.
> Toda IA, agente, desarrollador o herramienta que trabaje sobre el repositorio debe leer este archivo antes de modificar el sistema.

---

# 1. IDENTIDAD DEL PROYECTO

**Nombre:** WABOGADOS  
**Versión:** V1 — Núcleo Operativo  
**Tipo:** Plataforma web integral de gestión jurídica  
**Objetivo:** Centralizar la operación de la firma en una plataforma tipo ERP jurídico, segura, auditable, modular y escalable.

## Núcleo V1

1. Dashboard
2. Clientes
3. Expedientes
4. Abogados
5. Actuaciones
6. Agenda y Audiencias
7. Documentos
8. Motor de Evidencias
9. Mensajería
10. Seguridad
11. Auditoría
12. Notificaciones

## Fases futuras, NO implementar aún

- CRM
- Facturación
- Centro multimedia
- Inteligencia Artificial jurídica

La arquitectura debe quedar preparada para integrarlos posteriormente.

---

# 2. VISIÓN DEL SISTEMA

WABOGADOS debe funcionar como el núcleo digital operativo de la firma.

Debe reemplazar progresivamente:

- Hojas de cálculo
- Carpetas dispersas
- Archivos físicos
- Mensajería informal
- Seguimiento manual
- Copias duplicadas de documentos
- Evidencias sin trazabilidad

por un ecosistema centralizado con:

- Expedientes 360°
- Gestión documental
- Evidencias protegidas
- Agenda
- Actuaciones
- Clientes
- Abogados
- Mensajería
- Auditoría
- Trazabilidad completa

---

# 3. PRINCIPIOS OBLIGATORIOS

La plataforma debe ser:

- Modular
- Multiusuario
- Basada en roles y permisos
- Auditable
- Segura por diseño
- Escalable
- Responsive
- Mantenible
- Tipada
- Preparada para alta disponibilidad
- Preparada para almacenamiento de objetos S3/MinIO
- Preparada para IA jurídica futura
- Preparada para múltiples sedes
- Preparada para evolucionar a SaaS si se decide

Nunca implementar una solución que rompa estas posibilidades.

---

# 4. STACK TECNOLÓGICO

## Backend

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- Alembic
- PostgreSQL 16/17
- JWT
- Refresh Tokens
- Argon2
- Redis opcional
- Celery/RQ/Arq opcional para tareas pesadas

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide Icons
- React Hook Form
- Zod
- TanStack Query
- TanStack Table
- Recharts

## Evidencias y documentos

- pikepdf
- qpdf
- Pillow
- img2pdf
- PyMuPDF cuando aplique
- Ghostscript solo si el proceso es controlado y necesario
- ClamAV opcional/recomendado para producción
- python-magic/libmagic para MIME real
- hashlib SHA-256
- MinIO o S3 compatible

## Infraestructura

- Docker
- Docker Compose
- Nginx
- HTTPS
- Coolify compatible
- Oracle Cloud / VPS
- PostgreSQL
- MinIO/S3

---

# 5. ESTRUCTURA OBLIGATORIA DEL REPOSITORIO

Crear y mantener:

```text
wabogados/
│
├── README.md
├── MASTER_PROMPT.md
├── AGENTS.md
├── PROJECT_RULES.md
├── ROADMAP.md
├── CHANGELOG.md
├── ARCHITECTURE.md
├── SECURITY.md
├── .env.example
├── .gitignore
│
├── memory/
│   ├── PROJECT_MEMORY.md
│   ├── CURRENT_STATE.md
│   ├── DECISIONS.md
│   ├── KNOWN_ISSUES.md
│   ├── IMPLEMENTED_FEATURES.md
│   └── NEXT_STEPS.md
│
├── agents/
│   ├── backend_agent.md
│   ├── frontend_agent.md
│   ├── database_agent.md
│   ├── security_agent.md
│   ├── evidence_engine_agent.md
│   ├── qa_agent.md
│   ├── ux_agent.md
│   └── devops_agent.md
│
├── context/
│   ├── business_context.md
│   ├── legal_domain.md
│   ├── architecture_context.md
│   ├── security_context.md
│   ├── evidence_context.md
│   └── glossary.md
│
├── orchestration/
│   ├── ORCHESTRATOR.md
│   ├── implementation_plan.md
│   ├── task_flow.md
│   ├── dependencies.md
│   ├── quality_gates.md
│   └── handoff_protocol.md
│
├── roles/
│   ├── administrador.md
│   ├── abogado.md
│   ├── asistente.md
│   └── cliente.md
│
├── specs/
│   ├── dashboard.md
│   ├── clientes.md
│   ├── expedientes.md
│   ├── abogados.md
│   ├── actuaciones.md
│   ├── agenda.md
│   ├── documentos.md
│   ├── evidencias.md
│   ├── mensajeria.md
│   ├── seguridad.md
│   └── auditoria.md
│
├── backend/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── db/
│       ├── models/
│       ├── schemas/
│       ├── services/
│       ├── repositories/
│       ├── security/
│       ├── middleware/
│       ├── workers/
│       ├── evidence_engine/
│       └── tests/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── hooks/
│   ├── lib/
│   ├── services/
│   ├── types/
│   └── styles/
│
├── migrations/
├── tests/
├── scripts/
├── infra/
└── security/
```

---

# 6. MEMORIA DEL PROYECTO

La IA debe trabajar con memoria explícita basada en archivos.

## PROJECT_MEMORY.md

Debe resumir:

- Propósito del sistema
- Arquitectura
- Módulos
- Decisiones vigentes
- Restricciones
- Convenciones
- Dependencias críticas

## CURRENT_STATE.md

Debe indicar:

- Qué está funcionando
- Qué está en desarrollo
- Qué está pendiente
- Migración actual
- Endpoints activos
- Módulos frontend terminados
- Problemas abiertos

## DECISIONS.md

Toda decisión arquitectónica importante debe registrarse con:

- Fecha
- Decisión
- Motivo
- Alternativas descartadas
- Impacto

## IMPLEMENTED_FEATURES.md

Inventario de funcionalidades terminadas.

## KNOWN_ISSUES.md

Errores y deuda técnica conocida.

## NEXT_STEPS.md

Próximas tareas priorizadas.

### Regla obligatoria de continuidad

Antes de comenzar cualquier tarea, el agente debe leer:

1. MASTER_PROMPT.md
2. PROJECT_RULES.md
3. memory/PROJECT_MEMORY.md
4. memory/CURRENT_STATE.md
5. memory/DECISIONS.md
6. CHANGELOG.md

Al terminar una tarea significativa debe actualizar:

- CURRENT_STATE.md
- IMPLEMENTED_FEATURES.md
- NEXT_STEPS.md
- CHANGELOG.md
- DECISIONS.md si hubo decisión arquitectónica

---

# 7. ORQUESTADOR

`orchestration/ORCHESTRATOR.md` gobierna el trabajo multiagente.

El orquestador debe:

1. Leer el estado actual.
2. Clasificar la tarea.
3. Detectar módulos afectados.
4. Identificar dependencias.
5. Asignar agentes.
6. Definir orden de ejecución.
7. Exigir pruebas.
8. Exigir revisión de seguridad.
9. Ejecutar quality gates.
10. Actualizar memoria del proyecto.

## Orden recomendado

```text
Análisis
→ Arquitectura
→ Base de datos
→ Backend
→ Seguridad
→ Frontend
→ QA
→ DevOps
→ Documentación
→ Memoria
```

Ningún agente debe trabajar ignorando cambios paralelos documentados.

---

# 8. AGENTES ESPECIALIZADOS

## backend_agent

Responsable de:

- FastAPI
- Servicios
- Repositorios
- Schemas
- Validaciones
- API REST
- Manejo de errores

## frontend_agent

Responsable de:

- Next.js
- UX
- Componentes
- Formularios
- Tablas
- Dashboards
- Estados de carga/error

## database_agent

Responsable de:

- PostgreSQL
- Modelado
- Constraints
- Índices
- Alembic
- Integridad referencial

## security_agent

Responsable de:

- Autenticación
- RBAC
- Sesiones
- CORS
- Rate limiting
- Headers
- Validación uploads
- IDOR
- Auditoría
- Hardening

## evidence_engine_agent

Responsable exclusivo del Motor de Evidencias:

- Validación de archivos
- MIME real
- Hash
- Optimización
- Compresión
- Metadatos
- Cadena de custodia
- Versiones
- Miniaturas
- Preservación original
- Almacenamiento
- Auditoría

## qa_agent

Responsable de:

- Unit tests
- Integration tests
- API tests
- E2E
- Seguridad funcional
- Regresiones

## ux_agent

Responsable de:

- Consistencia visual
- Diseño responsive
- Flujos
- Accesibilidad
- Experiencia jurídica empresarial

## devops_agent

Responsable de:

- Docker
- Nginx
- PostgreSQL
- MinIO
- Backups
- Deploy
- Observabilidad

---

# 9. ROLES

## Administrador

Acceso general con permisos explícitos.

## Abogado

Acceso a expedientes asignados o autorizados.

## Asistente jurídico

Acceso operativo limitado según permisos.

## Cliente

Acceso únicamente a información publicada y vinculada a su identidad.

Nunca confiar solo en restricciones frontend.

---

# 10. DASHBOARD

Crear dashboards por rol.

## Administrador

KPIs:

- Clientes activos
- Expedientes activos
- Expedientes cerrados
- Audiencias próximas
- Actuaciones del mes
- Evidencias cargadas
- Documentos recientes
- Abogados activos
- Mensajes pendientes

## Abogado

- Mis expedientes
- Próximos vencimientos
- Audiencias
- Tareas
- Mensajes
- Actuaciones recientes

## Cliente

- Mis procesos
- Estado
- Próxima audiencia
- Documentos publicados
- Evidencias visibles
- Mensajes

---

# 11. CLIENTES

Soportar:

- Persona natural
- Persona jurídica

No eliminar físicamente registros vinculados.

Registrar historial de modificaciones.

---

# 12. ABOGADOS

Datos mínimos:

- Documento
- Nombre
- Tarjeta profesional
- Especialidades
- Áreas jurídicas
- Contacto
- Estado
- Fotografía

Permitir:

- Asignación de expedientes
- Carga de trabajo
- Agenda
- Historial de actuaciones

---

# 13. EXPEDIENTES

El expediente es el núcleo funcional.

Formato sugerido:

`WA-AAAA-000001`

Debe incluir:

- Cliente
- Abogado responsable
- Colaboradores
- Área
- Tipo proceso
- Jurisdicción
- Juzgado
- Radicado
- Estado
- Prioridad
- Fechas
- Partes
- Contraparte
- Descripción
- Cuantía
- Observaciones

## Ficha 360°

Pestañas:

1. Resumen
2. Actuaciones
3. Evidencias
4. Documentos
5. Agenda
6. Audiencias
7. Tareas
8. Mensajes
9. Partes
10. Historial
11. Auditoría restringida

---

# 14. ACTUACIONES

Toda actuación debe pertenecer a un expediente.

Campos:

- Tipo
- Fecha/hora
- Descripción
- Resultado
- Responsable
- Visibilidad
- Próxima acción
- Fecha próxima acción

Debe alimentar automáticamente la timeline.

---

# 15. AGENDA Y AUDIENCIAS

Vistas:

- Día
- Semana
- Mes
- Abogado
- Expediente

Eventos:

- Audiencia
- Reunión
- Vencimiento
- Llamada
- Cita
- Recordatorio

Audiencias deben incluir lógica especializada.

---

# 16. DOCUMENTOS

El gestor documental debe manejar:

- Contratos
- Poderes
- Demandas
- Contestaciones
- Memoriales
- Autos
- Sentencias
- Pruebas
- Identificación
- Comunicaciones
- Otros

Características:

- Versionado
- Hash
- MIME
- Visibilidad
- Confidencialidad
- Historial
- Descargas auditadas

Nunca sobrescribir el original.

---

# 17. MOTOR PROFESIONAL DE EVIDENCIAS

Este componente es OBLIGATORIO desde V1.

Su objetivo es recibir evidencias en:

- PDF
- PNG
- JPG
- JPEG

y procesarlas de forma segura, eficiente y jurídicamente trazable.

## 17.1 Principio fundamental

**Nunca destruir ni reemplazar el archivo original recibido.**

Cada evidencia debe conservar:

1. Archivo original inmutable.
2. Archivo optimizado para consulta web.
3. Miniatura/previsualización cuando aplique.
4. Metadatos.
5. Hash de integridad.
6. Historial de procesamiento.
7. Auditoría.

---

# 18. FLUJO DEL MOTOR DE EVIDENCIAS

Pipeline obligatorio:

```text
UPLOAD
  ↓
VALIDACIÓN EXTENSIÓN
  ↓
DETECCIÓN MIME REAL
  ↓
VALIDACIÓN TAMAÑO
  ↓
ESCANEO SEGURIDAD/ANTIVIRUS
  ↓
GENERAR SHA-256 ORIGINAL
  ↓
EXTRAER METADATOS
  ↓
GUARDAR ORIGINAL INMUTABLE
  ↓
NORMALIZAR
  ↓
OPTIMIZAR / COMPRIMIR
  ↓
GENERAR SHA-256 OPTIMIZADO
  ↓
GENERAR PREVIEW / THUMBNAIL
  ↓
REGISTRAR RESULTADOS
  ↓
VINCULAR A EXPEDIENTE / ACTUACIÓN
  ↓
AUDITORÍA
```

---

# 19. COMPRESIÓN DE IMÁGENES

Para PNG, JPG y JPEG:

## Reglas

- Preservar proporción.
- No deformar.
- No eliminar contenido visible.
- Preservar legibilidad de textos.
- Aplicar auto-rotate según EXIF antes de optimizar.
- Eliminar metadatos sensibles opcionalmente en la COPIA optimizada.
- Nunca alterar original.

## Perfiles

### Evidencia documental

Ideal para:

- Cédulas
- Contratos fotografiados
- Recibos
- Capturas de pantalla
- Fotografías de documentos

Objetivo:

- 1600–2200 px máximo por lado según archivo.
- JPEG 80–88 de calidad como punto inicial.
- Optimización progresiva.
- Mantener texto claramente legible.

### Evidencia fotográfica

Ideal para:

- Daños
- Lugares
- Vehículos
- Objetos
- Escenas

Objetivo:

- Máximo aproximado 2560 px en lado mayor para consulta estándar.
- Calidad 82–90 según análisis.
- Crear miniatura adicional.

## PNG

Si la imagen no requiere transparencia:

- Se puede generar derivado JPEG/WebP para visualización.
- El original PNG se conserva.

Si requiere transparencia:

- Optimizar PNG sin pérdida o generar WebP derivado compatible.

---

# 20. COMPRESIÓN PDF

PDF debe optimizarse con extrema precaución.

## Reglas

- Nunca modificar el original.
- No rasterizar un PDF textual si no es necesario.
- Preservar texto seleccionable.
- Preservar marcadores cuando sea posible.
- Preservar estructura.
- Detectar PDF firmado digitalmente.

### PDFs firmados

Si contiene firma digital:

- El original se conserva íntegro.
- No modificarlo.
- La versión optimizada debe considerarse DERIVADO DE CONSULTA.
- Registrar claramente que no reemplaza al original firmado.

## Estrategias

1. Optimización estructural con pikepdf/qpdf.
2. Compresión de objetos internos.
3. Eliminación segura de objetos redundantes.
4. Compresión de imágenes embebidas cuando sea apropiado.
5. No reducir por debajo de umbrales que afecten lectura.

---

# 21. POLÍTICA DE CALIDAD

El motor no debe buscar simplemente "el archivo más pequeño".

Debe buscar:

> menor peso razonable conservando valor probatorio y legibilidad.

Crear perfiles:

- `lossless`
- `legal_standard`
- `web_preview`

### lossless

Para documentos sensibles.

### legal_standard

Perfil recomendado.

### web_preview

Solo para navegación rápida.

---

# 22. VALIDACIÓN DE EVIDENCIA

No confiar en extensión.

Validar:

- Extensión
- MIME declarado
- MIME real
- Magic bytes
- Tamaño
- Integridad
- Archivo corrupto

Rechazar:

- Ejecutables camuflados
- Archivos corruptos
- MIME inconsistente
- Formatos prohibidos

---

# 23. HASH E INTEGRIDAD

Generar SHA-256:

- original_sha256
- optimized_sha256

Campos:

```text
original_sha256
optimized_sha256
original_size
optimized_size
compression_ratio
```

Ejemplo:

```text
Original: 12.4 MB
Optimizado: 2.8 MB
Reducción: 77.4%
```

---

# 24. CADENA DE CUSTODIA DIGITAL

Cada evidencia debe registrar:

- ID UUID
- Expediente
- Actuación relacionada
- Usuario que cargó
- Fecha/hora
- IP
- Nombre original
- MIME
- Tamaño
- SHA-256
- Estado
- Procesamiento
- Descargas
- Visualizaciones
- Cambio de visibilidad
- Versiones derivadas

Nunca permitir que el usuario modifique directamente:

- hash original
- fecha original de carga
- archivo original almacenado

---

# 25. MODELO DE DATOS DE EVIDENCIAS

Tablas sugeridas:

```text
evidences
evidence_files
evidence_derivatives
evidence_processing_jobs
evidence_access_logs
evidence_events
```

## evidences

- id
- case_id
- action_id opcional
- title
- description
- evidence_type
- visibility
- confidentiality
- created_by
- created_at

## evidence_files

- id
- evidence_id
- storage_key
- original_filename
- mime_type
- file_size
- sha256
- width
- height
- page_count
- is_original
- is_signed_pdf
- created_at

## evidence_derivatives

- id
- evidence_id
- source_file_id
- derivative_type
- storage_key
- mime_type
- size
- sha256
- compression_ratio
- profile
- created_at

## evidence_processing_jobs

- id
- evidence_id
- job_type
- status
- started_at
- finished_at
- error
- worker

---

# 26. ESTADOS DEL PROCESAMIENTO

```text
uploaded
validating
scanning
processing
optimized
ready
failed
quarantined
```

El frontend debe mostrar el estado.

---

# 27. PROCESAMIENTO ASÍNCRONO

Archivos pequeños pueden procesarse inmediatamente.

Archivos grandes deben ir a worker.

Flujo:

```text
FastAPI
 → Queue
 → Evidence Worker
 → MinIO/S3
 → PostgreSQL
 → Notification
```

No bloquear solicitudes HTTP pesadas.

---

# 28. ALMACENAMIENTO

Nunca guardar archivos con el nombre proporcionado por usuario como ruta física principal.

Usar UUID.

Ejemplo:

```text
evidences/
  case_uuid/
    evidence_uuid/
      original/
        file_uuid.pdf
      optimized/
        file_uuid.pdf
      previews/
        page_001.webp
        thumb.webp
```

Guardar nombre original solo como metadato.

---

# 29. CONTROL DE DUPLICADOS

Comparar SHA-256.

Si un archivo idéntico ya existe:

- Informar.
- Evitar duplicación física cuando la arquitectura lo permita.
- Mantener relación lógica independiente si corresponde.

Nunca asumir que dos evidencias son jurídicamente iguales solo porque comparten archivo.

---

# 30. PREVISUALIZACIÓN

Generar:

- Thumbnail
- Preview web
- Primera página PDF
- Cantidad de páginas
- Dimensiones imagen

No exponer storage keys reales al cliente.

Usar URLs firmadas temporales.

---

# 31. DESCARGAS

Permitir:

- Original, según permiso.
- Optimizado.
- Preview.

Toda descarga debe registrar:

- Usuario
- Evidencia
- Archivo
- Fecha/hora
- IP
- Tipo de versión descargada

---

# 32. PERMISOS DE EVIDENCIAS

Ejemplo:

```text
evidencias.view
evidencias.create
evidencias.upload
evidencias.download_original
evidencias.download_optimized
evidencias.publish_to_client
evidencias.classify
evidencias.archive
evidencias.audit
```

---

# 33. MENSAJERÍA

Mensajería interna segura vinculable a:

- Cliente
- Expediente

Debe registrar estado leído y auditoría básica.

---

# 34. SEGURIDAD

Submódulos:

- Usuarios
- Roles
- Permisos
- Sesiones
- Auditoría
- Configuración

Implementar:

- JWT
- Refresh token
- RBAC
- Rate limiting
- CORS
- Trusted hosts
- Headers
- Upload validation
- Protección IDOR
- Logs
- Auditoría

---

# 35. AUDITORÍA

Registrar:

- Login
- Logout
- Clientes
- Expedientes
- Actuaciones
- Evidencias
- Documentos
- Descargas
- Mensajes relevantes
- Permisos
- Cambios de estado

Campos:

- Usuario
- Acción
- Entidad
- Entity ID
- Fecha
- IP
- User agent
- Antes
- Después
- Resultado

---

# 36. SOFT DELETE

No eliminar físicamente información jurídica relevante.

Aplicar:

```text
is_active
deleted_at
deleted_by
```

cuando corresponda.

Los archivos originales de evidencia deben tratarse como inmutables.

---

# 37. ENTIDADES BASE

```text
users
roles
permissions
role_permissions
user_roles

clients
lawyers
legal_areas

cases
case_lawyers
case_parties

actions

calendar_events
hearings

documents
document_versions

evidences
evidence_files
evidence_derivatives
evidence_processing_jobs
evidence_access_logs
evidence_events

conversations
conversation_participants
messages
message_attachments

notifications
audit_logs
system_settings
```

---

# 38. API

Ejemplos:

```text
/api/v1/auth
/api/v1/users
/api/v1/clients
/api/v1/lawyers
/api/v1/cases
/api/v1/actions
/api/v1/calendar
/api/v1/hearings
/api/v1/documents

/api/v1/evidences
/api/v1/evidences/{id}
/api/v1/evidences/{id}/files
/api/v1/evidences/{id}/download
/api/v1/evidences/{id}/preview
/api/v1/evidences/{id}/processing
/api/v1/evidences/{id}/audit

/api/v1/conversations
/api/v1/messages
/api/v1/notifications
/api/v1/audit
```

---

# 39. UI DEL MOTOR DE EVIDENCIAS

Dentro del expediente:

```text
EVIDENCIAS
```

Mostrar:

- Vista tarjetas
- Vista tabla
- Miniaturas
- Tipo
- Fecha
- Peso original
- Peso optimizado
- Reducción
- Estado
- Integridad
- Usuario
- Visibilidad

Al cargar:

```text
Arrastra archivos aquí
PDF, PNG, JPG, JPEG
```

Mostrar progreso:

```text
Subiendo
Validando
Verificando seguridad
Optimizando
Generando vista previa
Listo
```

---

# 40. REGLAS DE NEGOCIO CRÍTICAS

1. Cada expediente tiene cliente.
2. Un expediente puede tener varios abogados.
3. Debe existir abogado responsable.
4. Toda actuación pertenece a expediente.
5. Toda evidencia pertenece como mínimo a expediente.
6. Una evidencia puede vincularse a actuación.
7. Nunca sobrescribir original.
8. Toda evidencia debe tener SHA-256.
9. Toda descarga de original debe auditarse.
10. Cliente solo ve evidencia publicada.
11. No exponer evidencia interna.
12. No permitir acceso cruzado entre clientes.
13. No confiar en nombre o extensión del archivo.
14. Un derivado optimizado nunca sustituye jurídicamente al original.
15. Un PDF firmado nunca se modifica como original.

---

# 41. QUALITY GATES

Una tarea no se considera terminada hasta pasar:

## Gate 1 — Arquitectura
No rompe diseño existente.

## Gate 2 — Base de datos
Migraciones correctas y reversibles.

## Gate 3 — Seguridad
Permisos backend y protección IDOR.

## Gate 4 — Testing
Tests relevantes pasan.

## Gate 5 — Evidencias
Si afecta archivos:
- MIME validado
- Hash
- Seguridad
- Auditoría
- Original preservado

## Gate 6 — Documentación
Docs y memoria actualizadas.

---

# 42. TESTING MOTOR DE EVIDENCIAS

Crear pruebas para:

- JPG válido.
- PNG válido.
- PDF válido.
- PDF firmado.
- Archivo corrupto.
- EXE renombrado .pdf.
- MIME inconsistente.
- Imagen muy grande.
- PDF pesado.
- Hash correcto.
- Optimización.
- Reducción de tamaño.
- Original intacto.
- Permisos.
- Acceso cruzado.
- URLs expiradas.

---

# 43. OBSERVABILIDAD

Medir:

- Cantidad de evidencias
- MB subidos
- MB ahorrados
- Ratio compresión
- Tiempo procesamiento
- Fallos
- Archivos cuarentena
- Uso almacenamiento

Dashboard administrativo futuro:

```text
Peso original acumulado: 124 GB
Peso optimizado: 38 GB
Ahorro: 86 GB
Reducción: 69%
```

---

# 44. BACKUPS

Respaldar:

- PostgreSQL
- Originals
- Derivados críticos
- Configuración

La restauración debe documentarse y probarse.

---

# 45. FASES V1

## Fase 0
Arquitectura y repositorio.

## Fase 1
Seguridad, usuarios, roles y auditoría.

## Fase 2
Clientes y abogados.

## Fase 3
Expedientes.

## Fase 4
Actuaciones.

## Fase 5
Agenda y audiencias.

## Fase 6
Documentos.

## Fase 7
Motor de Evidencias.

## Fase 8
Mensajería.

## Fase 9
Dashboards.

## Fase 10
QA, hardening y despliegue.

---

# 46. FUTURO

## V2 CRM
Prospectos, leads, oportunidades.

## V3 Facturación
Honorarios, pagos y cuentas.

## V4 Multimedia
Videos y biblioteca.

## V5 IA jurídica
RAG, resumen, análisis y generación asistida.

---

# 47. PROTOCOLO DE TRABAJO PARA IA

Antes de modificar código:

1. Leer memoria.
2. Leer arquitectura.
3. Identificar fase.
4. Analizar impacto.
5. Revisar migraciones.
6. Revisar permisos.
7. Revisar riesgos.

Después:

1. Implementar.
2. Probar.
3. Revisar seguridad.
4. Actualizar documentación.
5. Actualizar memoria.
6. Actualizar CHANGELOG.

---

# 48. PROHIBICIONES

No:

- Hardcodear secretos.
- Saltarse RBAC.
- Confiar en frontend.
- Sobrescribir originales.
- Eliminar evidencia original.
- Modificar PDF firmado original.
- Guardar uploads sin validar MIME.
- Usar nombres enviados por usuario como ruta segura.
- Omitir auditoría.
- Crear endpoints sin permisos.
- Exponer storage keys.
- Crear lógica crítica sin tests.

---

# 49. INSTRUCCIÓN MAESTRA

Actúa como un equipo senior compuesto por:

- Arquitecto de software
- Backend engineer
- Frontend engineer
- DBA PostgreSQL
- Security engineer
- Evidence Processing Engineer
- DevOps engineer
- UX/UI designer
- QA engineer

Tu misión es construir WABOGADOS como una plataforma jurídica profesional lista para producción.

Cada funcionalidad debe considerar:

- Modelo
- Migración
- Schema
- Servicio
- Repositorio
- Endpoint
- Permiso
- Auditoría
- Validación
- UI
- Errores
- Tests
- Documentación
- Actualización de memoria

Para cualquier función de evidencias debes aplicar obligatoriamente:

> preservar original + validar + hash + procesar derivado + auditar + controlar acceso.

Nunca sacrifiques integridad jurídica, seguridad, mantenibilidad ni trazabilidad por velocidad.
