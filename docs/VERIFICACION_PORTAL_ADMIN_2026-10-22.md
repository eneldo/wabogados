# Verificación del acceso privado y portal administrativo

## Resultado comprobado

- **4 pruebas privadas aprobadas**, sobre el frontend Docker actualizado.
- Login real desde la web → `/admin`; reabrir `/login` con sesión → `/admin`
  HTTP 200 (antes respondía 500).
- Los 13 módulos cargan HTTP 200 con su título y sin los avisos de acceso
  denegado o fallo de carga comprobados: Dashboard, Expedientes, Clientes,
  Abogados, Agenda, Mensajes, Solicitudes, Documentos, Multimedia, IA Jurídica,
  Facturación, Seguridad y Configuración.
- 52 inspecciones de maquetación (13 módulos × 320/390/768/1440 px), sin
  desbordamiento horizontal ni ids repetidos. Menú móvil con 13 entradas.
- Salida → `/login`, cookies eliminadas; intentar renovar con el refresco
  revocado devuelve HTTP 401. `/admin` vuelve a exigir autenticación.
- 5 escenarios aislados de la guarda aprobados y 11 regresiones de la web
  pública aprobadas. ESLint, TypeScript y build Docker correctos.
- Capturas de Dashboard y menú móvil inspeccionadas; sin errores JavaScript
  en el recorrido administrativo aprobado. Servicios locales saludables.

## Fallo reproducido

La entrada desde «Portal privado» con una cuenta administrativa autentica y
dirige a `/admin`. Sin embargo, abrir de nuevo ese acceso con una sesión activa
producía **HTTP 500 en `/login`**, reproducido con Chromium sobre Compose.

La página de acceso usaba `NEXT_PUBLIC_API_URL` con respaldo a `localhost:8000`;
dentro del frontend Docker esa dirección apunta al propio frontend, no al
backend. El cliente servidor existente ya resuelve `API_INTERNAL_URL`.

## Corrección

- `/login` usa el mismo `requireSession` que las páginas privadas y `landingFor`
  para elegir el destino. No hace peticiones duplicadas con una URL distinta.
- Un HTTP 401 se convierte en `ApiNotAuthenticated`, tal como esperan las
  guardas; una cookie presente pero inválida no acredita identidad.
- La consulta obligatoria `/auth/me` no usa un perfil vacío como respaldo ante
  errores. Fallas de conexión o del servicio muestran indisponibilidad, no una
  identidad vacía ni una redirección por defecto.
- La clasificación de cliente puro se comparte entre perfil y destino. Una
  cuenta con roles cliente + administrador no depende del orden de esos roles.
- «Mi panel» en los menús administrativo de escritorio y móvil vuelve a
  `/admin`, no al portal de clientes.
- El formulario lee los valores de `FormData` al enviar, no de un estado React
  que puede quedar desincronizado con el autocompletado o la entrada rápida.
  Un envío con campos visibles llenos había respondido 422; se añadió una
  regresión con valores DOM sin eventos de cambio y respuesta de error simulada
  (esa prueba no se presenta como una autenticación real).

No se modifican usuarios, contraseñas, permisos ni datos jurídicos. El acceso
de prueba genera la sesión y las entradas de auditoría normales.

## Regresión reproducible

Desde `frontend/`, proporcionar las credenciales de una cuenta administradora
por variables de entorno `E2E_EMAIL` y `E2E_PASSWORD` y ejecutar:

```sh
npm run test:e2e -- --project=private
```

Pruebas aisladas de la guarda (sin red ni credenciales), desde la raíz:

```sh
node frontend/scripts/test-session-guard.mjs
```

Cubren ausencia de cookie, HTTP 401, HTTP 503, fallo de conexión e identidad
administrativa con roles combinados. Verifican también que se utilice la URL
interna configurada; no se detiene el backend real para simular indisponibilidad.

Las pruebas no escriben credenciales, cookies ni tokens en archivos. Las sesiones
se revocan al cerrar la prueba, incluso si falla. El recorrido se limita a
lectura: no crea expedientes, no envía mensajes, no registra pagos ni consultas.

Cobertura: destino por perfil, entrada anónima y cookie inválida, login real
desde la web, regreso con sesión existente, trece módulos, cuatro anchos por
módulo, menú móvil y salida con rechazo de reutilización del refresco revocado.

Se respeta el rate limit existente, espaciando visitas en vez de desactivarlo.
Capturas locales en `.tmp/admin-portal-review/` (no versionadas).

Límites: no se prueba la creación/edición/borrado de registros ni se certifican
todas las operaciones del ERP. La clasificación de cliente se prueba como
función; no se alteran ni se utilizan cuentas de clientes reales.
