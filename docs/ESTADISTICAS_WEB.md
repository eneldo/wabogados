# Estadísticas privadas de la web pública

## Acceso y métricas

En `/admin/estadisticas-web`, o **Administración → Estadísticas web**.
Requiere `website_analytics:read`, asignado por migración solo al rol
`administrador`. El backend también aplica el permiso: ocultar el menú no es
la barrera de seguridad.

El panel muestra páginas vistas, navegaciones estimadas, clics en teléfono,
solicitudes realmente registradas, áreas jurídicas más vistas y evolución diaria
y mensual. Permite rangos de hasta 366 días, en `America/Bogota`.

**No es un contador de personas exactas.** El navegador genera un UUID aleatorio
en memoria, compartido durante la navegación cliente. No se almacena en cookies,
`localStorage` ni `sessionStorage`. Una recarga, pestaña nueva o reinicio del
navegador puede contar de nuevo. El servidor deduplica por día; los totales de
varios días suman estimaciones diarias, **no únicos mensuales**. Una página vista
no equivale a una sesión ni a una consulta. Un clic no acredita una llamada.

Los datos comienzan con la activación: no se reconstruyen visitas antiguas ni se
inventan datos históricos. Las solicitudes solo incrementan el agregado cuando
se crean en la transacción del backend; los errores y clics de envío no cuentan.
Eliminar una solicitud personal no elimina el total agregado anónimo.

## Privacidad y límites

- Sin proveedor externo, fingerprint, cookies de analítica ni identificación de
  cuentas. La página pública informa de estas estadísticas en el pie y aviso de
  privacidad; el aviso legal general sigue pendiente de aprobación de la firma.
- Solo `/`, áreas publicadas de `/servicios/…` y análisis publicados de
  `/analisis/…`. No se montan colectores en login, portal, expedientes, documentos,
  administración, páginas inexistentes o estados de servicio.
- Se excluyen búsquedas, fragmentos, URL de origen, IP, user agent, nombres,
  teléfonos, correos y contenido de formularios de los datos analíticos. Esto no
  sustituye las políticas de logs técnicos, autenticación y auditoría del resto
  de la aplicación.
- Do Not Track y Global Privacy Control impiden medir la navegación. El servidor
  también los respeta. Navegadores sin JavaScript, bloqueadores y bots filtrados
  no cuentan. El total de solicitudes aceptadas es un agregado de actividad del
  despacho, independiente del seguimiento del navegador.
- El colector Next exige mismo origen, cuerpo de hasta 1024 bytes y cuatro
  campos cerrados. No reenvía cookies, autorización, IP o user agent del visitante.
  El backend verifica que la página existe y tiene un presupuesto de peticiones
  separado de autenticación, consultas y API general. No es un sistema antifraude:
  un cliente programado puede simular visitas; las cifras son orientativas.
- Se persisten solo agregados diarios y por página, más digests temporales de
  UUID aleatorios para idempotencia/deduplicación, sin asociarlos a rutas.
  Caducan a las 48 horas; una tarea horaria los elimina incluso sin tráfico
  (hasta una hora adicional antes de la purga física). Los agregados se conservan
  400 días. También se limpia al recibir eventos.
- El intake anónimo exacto está excluido del middleware de auditoría para no
  duplicar IP/user agent por visita. Las operaciones legales conservan su auditoría.

## Contratos y archivos

- `POST /api/estadisticas`: proxy público first-party en Next, sin responder cifras.
- `POST /api/v1/public/analytics/events`: `{event_id, visitor_id, kind, path}`;
  tipos permitidos `page_view` y `phone_click`, UUID v4; devuelve 204.
- `GET /api/v1/admin/metrics/website?start=YYYY-MM-DD&end=YYYY-MM-DD`: resumen
  autorizado con totales, días, meses, páginas y áreas. Sin token: 401; perfil sin
  permiso: 403. No se expone un contador agregado público.
- Migración `fd4e5f607182`: tres tablas `website_analytics_*` y semilla de permiso.
- Backend: `app/services/website_analytics.py`, `app/api/v1/website_analytics.py`,
  `app/schemas/website_analytics.py`; el conteo de consultas se integra en
  `app/services/consultations.py` sin copiar sus campos personales.
- Frontend: `components/public/public-analytics.tsx`, `app/api/estadisticas/route.ts`
  y `app/(admin)/admin/estadisticas-web/`.

## Operación

`WEBSITE_ANALYTICS_ENABLED=true` en Compose habilita el registro. Para pausarlo,
ponerlo en `false` y recrear backend/frontend; el histórico sigue disponible para
el administrador y la limpieza continúa. No se necesita una clave de terceros.
Detrás de un proxy se debe conservar el `Host` público para comprobar `Origin`.

Antes de actualizar una instalación: respaldo de PostgreSQL, migración a
`fd4e5f607182`, recreación del backend y después frontend, comprobando salud.
No ejecutar downgrade en una base real para «probar»: eliminaría los agregados.
Para recuperar la aplicación se puede volver a la imagen previa conservando las
tablas adicionales.

### Publicación local aislada de los cambios pendientes

Esta sesión conserva trabajo previo sin validar en Dockerfile/multimedia/IA.
**No se incluyó ese trabajo en la imagen nueva.**
`execution/prepare_scoped_backend.py` prepara un snapshot de Git HEAD más una
lista explícita de archivos revisados, sin stash, reset ni cambios al árbol real.
El contexto, revisión base y hashes quedan en `.tmp/scoped-backend-*/manifest.json`;
la ruta vigente se registra en `.tmp/website-analytics-context.txt`.

La imagen de esta funcionalidad es `wabogados-website-analytics:local`, que se
puede etiquetar con el nombre que utiliza Compose tras validarla. No reconstruir
el backend desde el árbol completo hasta revisar los pendientes anteriores.

## Verificación

Los tests de API usan PostgreSQL de pruebas y transacciones revertidas.
Playwright usa el proyecto `website-analytics`; los tests generales envían DNT
para no alterar cifras reales. Los escenarios de escritura y administrador se
ejecutan **solo contra la instalación efímera de revisión** con
`WEBSITE_ANALYTICS_TEST_API` y `WEBSITE_ANALYTICS_TEST_AUTH` (sesión temporal fuera
de Git); sin ese entorno se omiten expresamente. No utilizar credenciales ni
formularios reales para generar datos de demostración.

Validación de la release local: **881 tests backend**, cobertura **85,77 %**,
ruff/mypy y migración reversible correctos; **25 tests de navegador** pasan en
la instalación aislada. TypeScript/build frontend correctos; ESLint mantiene
solo el aviso previo de variable sin usar en el portal privado.
