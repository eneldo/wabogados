# Revisión de la web corporativa y los portales

Fecha: 2026-10-22. Alcance: rutas, navegación, identidad visual, acceso por perfil,
inventario de módulos y comprobación de pantallas sobre el stack local.

> Actualización posterior de la misma fecha: el destino administrativo tras
> login, la reentrada con sesión y «Mi panel» administrativo ya se corrigieron
> y verificaron. Resultados actuales en
> `docs/VERIFICACION_PORTAL_ADMIN_2026-10-22.md`. La identidad de la web pública
> también se actualizó (`docs/IDENTIDAD_WEB_PUBLICA.md`). Los hallazgos de abajo
> describen el diagnóstico original; los pendientes de contenido legal,
> actuaciones y despliegue público no se consideran resueltos por estos cambios.

## Conclusión

Las tres superficies existen, pero **la navegación no las separa correctamente**.
El inicio de sesión administrativo no dirige al portal administrativo. Esto
explica que una cuenta con permisos correctos termine viendo una interfaz
limitada y, en ciertos recorridos, el título «Portal del cliente».

| Superficie | Dirección local | Implementación |
| --- | --- | --- |
| Web corporativa | `http://localhost:3000/` | `frontend/app/(public)/page.tsx` |
| Portal administrativo | `http://localhost:3000/admin` | `frontend/app/(admin)/admin/` |
| Portal del cliente | `http://localhost:3000/portal` | `frontend/app/portal/` |
| Acceso compartido | `http://localhost:3000/login` | `frontend/app/login/page.tsx` |
| Listado previo del personal | `http://localhost:3000/expedientes` | `frontend/app/expedientes/page.tsx` |

Esto confirma existencia, no que todas las operaciones de cada módulo estén
completas ni que el sitio esté publicado en Internet.

## Hallazgos prioritarios

### 1. Alta: el administrador no entra a su portal después de autenticarse

`frontend/lib/landing.ts:19-33` solo devuelve `/portal` para un cliente puro y
`/expedientes` para todos los demás. Nunca devuelve `/admin`.
`frontend/app/api/session/route.ts:95-96` utiliza esa función para responder al
formulario real.

Diagnóstico ejecutado sobre la función TypeScript vigente:

| Perfil | Destino actual | Resultado requerido |
| --- | --- | --- |
| Administrador | `/expedientes` | `/admin` |
| Cliente | `/portal` | `/portal` |
| Abogado | `/expedientes` | Conservar o acordar su espacio de trabajo |
| Cliente + administrador | `/expedientes` | `/admin` con sus permisos efectivos |

No es una contraseña incorrecta ni una pérdida del rol administrativo.

### 2. Alta: volver al acceso con sesión envía siempre al portal del cliente

`frontend/app/login/page.tsx:8` hace `redirect("/portal")` al detectar una cookie
de acceso, sin resolver el perfil. El título en
`frontend/app/portal/page.tsx:58-65` es incondicionalmente «Portal del cliente».
Sus páginas de documentos, mensajes y ficha de expediente repiten ese título.

Así, entrar desde el botón «Portal privado» de la web con una sesión
administrativa ya abierta lleva a una pantalla que se identifica como cliente.

### 3. Alta: el portal administrativo está fuera del recorrido de navegación

- La web enlaza a `/login`, no ofrece una entrada explícita al área de personal:
  `frontend/components/public/site-header.tsx:183-185`.
- El destino `/expedientes` solo enlaza a panel, expedientes y mensajes; no al
  administrador: `frontend/app/expedientes/page.tsx:42-50`.
- El portal del cliente tampoco ofrece regreso a administración a quien tiene
  permisos administrativos: `frontend/components/masthead.tsx`.
- «Mi panel» dentro del propio administrador enlaza a `/portal`, en escritorio y
  móvil: `frontend/app/(admin)/admin/layout.tsx:119-124` y
  `frontend/components/admin/admin-mobile-menu.tsx:187-192`.

El usuario necesita conocer `/admin` o retroceder por el historial. El problema
es de descubrimiento y continuidad entre superficies, no de ausencia de páginas.

### 4. Alta: no existe una pantalla de gestión de actuaciones

El núcleo del proyecto incluye actuaciones. El backend dispone de creación,
listado y cronología en `backend/app/api/v1/actions.py:53-148`.

En el frontend no hay ruta de actuaciones ni llamadas a esos endpoints. La
ficha administrativa solo construye contadores en
`frontend/app/(admin)/admin/expedientes/[caseId]/page.tsx:104-110` y los muestra
como texto en `:310-327`; no permite abrir ni registrar una actuación. El
dashboard también muestra métricas, no una gestión de actuaciones.

Por tanto, «13 módulos con pantalla» **no equivale a todo el núcleo funcional
administrable desde la interfaz**. Esta ausencia requiere implementación, no
solo corregir un enlace.

### 5. Media: evidencias rompe la continuidad del portal administrativo

La ficha de expediente abre el gestor en
`/expedientes/{id}/evidencias`, fuera del layout administrativo:
`frontend/app/(admin)/admin/expedientes/[caseId]/page.tsx:143-148,349-354`.
El gestor usa el encabezado anterior y enlaces a `/portal` y `/expedientes`,
sin regreso directo al expediente administrativo:
`frontend/app/expedientes/[caseId]/evidencias/page.tsx:68-80`.

Evidencias existe y está vinculada al expediente, como exige el dominio; lo que
falta es conservar el contexto y la navegación del administrador.

### 6. Media: la web corporativa sigue presentada como propuesta

La página contiene servicios, firma, equipo, aliados, teléfono, dirección,
formulario de consulta y acceso privado. No es únicamente un portal de clientes.
Pero no debe presentarse como una web oficial terminada todavía:

- El pie dice «Propuesta de diseño»:
  `frontend/components/public/site-header.tsx:235-238`.
- Las tres noticias son contenido de ejemplo pendiente de aprobación:
  `frontend/components/public/news-section.tsx:24-45,93-99`.
- El aviso de privacidad declara pendientes el responsable y el canal para
  ejercer derechos, y exige revisión antes de producción:
  `frontend/components/public/contact-form.tsx:252-257,287-293`.
- El título y la descripción globales identifican el ERP, no una portada
  corporativa específica: `frontend/app/layout.tsx:35-38`.

El formulario **sí tiene integración real** con `/api/consultas` y
`/api/v1/consultations`; el comentario antiguo de la portada que dice que no
envía nada está desactualizado. No se envió una solicitud real durante esta
revisión para no introducir consultas ficticias en los datos de la firma.

### 7. Media: el dominio público no está sirviendo esta aplicación

La consulta realizada a `https://wabogados.co` durante la revisión devolvió el
aviso **«Account Suspended»**. Esto es distinto del sitio local operativo.
No se determinó la causa de la suspensión ni se accedió al proveedor de hosting.

El Compose vigente publica puertos locales, sin servicio de proxy inverso,
dominio ni certificados; `infra/` solo contiene `.gitkeep`. La existencia de la
página local no acredita un despliegue público. Resolver el hosting y publicar
la aplicación requiere un trabajo de despliegue separado y acceso autorizado.

### 8. Media: decisiones de perfil y pruebas incompletas

- `frontend/lib/profile.ts:56-72` considera cliente a quien tenga `cliente` como
  primer rol; `landingFor` considera cliente únicamente a quien no tenga ningún
  otro rol. Con roles combinados, ambas decisiones pueden discrepar. Hallazgo
  estático; no se modificaron roles de usuarios para provocarlo.
- El login tiene textos exclusivamente orientados al cliente, aunque es
  compartido: `frontend/app/login/page.tsx:24-40`.
- `frontend/e2e/auth.setup.ts:29-35` solo exige abandonar `/login`, por lo que
  permite una llegada incorrecta a `/expedientes` o `/portal`.
- La lista de la puerta de maquetación no incluye Facturación ni IA Jurídica:
  `frontend/e2e/layout.spec.ts:21-33`.

## Inventario administrativo

`frontend/lib/admin-nav.ts:59-180` define 13 entradas, todas con estado `ready`:

1. Dashboard: `/admin`.
2. Expedientes: `/admin/expedientes`.
3. Clientes: `/admin/clientes`.
4. Abogados: `/admin/abogados`.
5. Agenda y audiencias: `/admin/agenda`.
6. Mensajes: `/admin/mensajes`.
7. Solicitudes de la web: `/admin/solicitudes`.
8. Documentos: `/admin/documentos`.
9. Centro multimedia: `/admin/multimedia`.
10. IA Jurídica: `/admin/ia-juridica`.
11. Facturación: `/admin/facturacion`.
12. Seguridad, usuarios, roles y auditoría: `/admin/seguridad`.
13. Configuración: `/admin/configuracion`.

IA Jurídica implementa búsqueda literal y resumen extractivo, no un asistente
generativo. Multimedia conserva las limitaciones de vídeo ya documentadas.

## Validación y límites

- Lectura del flujo completo: portada → login → resolución de perfil → destino
  → layout administrativo → módulos y salida.
- Diagnóstico ejecutado de `landingFor`, con los resultados anteriores.
- Comprobación externa del aviso del dominio público.
- Prueba real Chromium del stack vigente, terminada:
  - Portada HTTP 200, secciones corporativas presentes; menú móvil y diálogos
    de privacidad y noticias operativos. Sin ids repetidos ni desbordamiento
    horizontal a 320, 390, 768 y 1440 px.
  - Sin sesión, `/admin`, `/portal` y `/expedientes` redirigen a `/login`.
  - Con la cuenta administrativa: login HTTP 200 → `/expedientes`; después,
    abrir `/login` → `/portal`, mostrando «Portal del cliente». Ambas pantallas
    carecen de enlaces hacia `/admin` en el DOM inspeccionado.
  - Acceso directo a `/admin`: Dashboard y las 13 entradas del menú presentes;
    también 13 enlaces de módulos visibles al abrir el menú móvil.
  - Los 13 módulos anteriores respondieron HTTP 200 y mostraron sus títulos,
    sin los mensajes de indisponibilidad o acceso denegado comprobados.
  - 52 inspecciones de maquetación administrativa (13 páginas × 4 anchos),
    sin ids duplicados ni desbordamiento horizontal de página.
  - Sin errores JavaScript capturados durante el recorrido. Cierre de la
    sesión de prueba completado.
- Resultados técnicos sin credenciales y capturas locales en
  `.tmp/surface-review-2026-10-22/`; esta carpeta es regenerable y no se versiona.
- Límites: no se probaron altas, cambios, borrados, pagos ni envíos del
  formulario público. Tampoco se inició sesión como un cliente real ni se
  modificaron sus credenciales; no es un pentest ni una certificación de todas
  las operaciones del ERP. El acceso de cada módulo se comprobó en lectura.
- Las 844 pruebas backend y los gates frontend aprobados en la tarea anterior
  no se presentan como una prueba de que el recorrido de acceso sea correcto.
- No se modificaron páginas, permisos, contraseñas, datos jurídicos ni
  configuración de producción durante esta revisión. Los accesos de prueba
  generan sesiones y sus registros de auditoría normales.

## Orden recomendado de corrección

1. Centralizar un destino por perfil: administrador → `/admin`, cliente →
   `/portal`; reutilizarlo tras login y al abrir login con sesión existente.
2. Identificar claramente en el acceso las entradas de clientes y personal,
   conservando autenticación real y autorización del backend.
3. Dar una navegación coherente entre web, administración y evidencias, sin
   presentar el panel del cliente como destino administrativo.
4. Añadir regresiones que exijan la URL correcta por perfil y cubran los 13
   módulos, incluidos Facturación e IA Jurídica.
5. Implementar la interfaz de actuaciones sobre la API existente.
6. Aprobar los contenidos y el aviso legal corporativo; luego resolver hosting,
   dominio, HTTPS y despliegue público. No inventar los datos legales pendientes.
