# SPEC — INTERFAZ

Desarrollar conforme a `MASTER_PROMPT.md`, secciones 5, 10 y 39.

## Estado: implementado tras el cierre de la Fase 10

## Dirección visual

**Instrumento legal.** Papel cálido, tinta, el oxblood de un sello de lacre y el
latón de un sello notarial. No es un panel de SaaS con degradados: es el
lenguaje visual de un expediente, que es lo que el usuario tiene delante.

Tres-tipografía con una tarea cada una:

| Fuente | Trabajo |
| --- | --- |
| Fraunces | La voz del documento. Títulos y cifras grandes |
| IBM Plex Sans | La interfaz. Institucional, buen soporte del español |
| IBM Plex Mono | Lo que alguien puede tener que leer carácter a carácter: un hash, un número de expediente, un peso |

Las tablas usan **renglones de libro contable**: filete fuerte bajo la cabecera,
hilos finos entre filas y **ningún relleno alterno**. Un zebrado pelea con el
papel y hace que un registro jurídico parezca una hoja de cálculo.

## Arquitectura

```
app/
  login/                     acceso
  portal/                    panel del cliente
    casos/[caseId]/          un expediente visto entero
    mensajes/                conversación con el despacho
    documentos/              documentos publicados
  expedientes/               cartera del personal
    [caseId]/evidencias/     gestor de evidencias
app/api/
  session/                   login y logout, escriben cookies httpOnly
  proxy/[...path]/           llamadas autenticadas desde el navegador
  descarga/[...path]/        descarga binaria en streaming
lib/
  api.ts                     cliente servidor, con errores ya en español
  session.ts                 cookies httpOnly
  session-guard.ts           distingue sesión ausente de servicio caído
  profile.ts                 identidad y permisos
  format.ts                  formatos y etiquetas en español
proxy.ts                     renovación del token antes de renderizar
```

## Decisiones de seguridad

**Los tokens nunca llegan al JavaScript del navegador.** Viven en cookies
`httpOnly`; los componentes cliente hablan con `/api/proxy/*`, que adjunta la
credencial en el servidor. Un token alcanzable desde la página es un token que
un XSS puede llevarse, y esta aplicación guarda la cartera completa de un
despacho.

**Las descargas no llevan el token en la URL.** Un enlace con
`?access_token=…` mete una credencial viva en el historial del navegador, en el
`Referer` de cada petición saliente y en el log de acceso de la API. La ruta
`/api/descarga/*` transmite los bytes con la credencial ya adjunta.

**El proxy es estrecho.** Solo acepta los prefijos que la interfaz usa y cinco
verbos, de modo que no se convierta en un agujero general hacia la API.

## El refresco del token, y por qué vive en `proxy.ts`

El token de acceso dura 30 minutos; el de refresco, 7 días. El primer sitio en
que se intentó cerrar esa distancia fue dentro del render, y **no puede
funcionar**:

- Un Server Component no puede escribir cookies. La cookie nueva no entra en el
  jar del resto de ese render, así que el reintento usa el token que acababa de
  sustituir.
- Peor: el backend **rota** el token de refresco, de modo que el segundo
  intento presenta un token que ya no existe y destruye la sesión que se
  acababa de renovar.

`proxy.ts` se ejecuta antes del render y sus escrituras sí llegan a la
respuesta. Se comprobó con un token caducado a propósito: `POST /auth/refresh
200` seguido de `auth/me 200` y `dashboard 200`, sin expulsar al usuario.

Ante un fallo de red el middleware **conserva** la sesión. Un problema de
conectividad no es motivo para cerrar el expediente de un abogado.

## Ausencia de sesión y caída del servicio

Son dos cosas distintas y el código las mantiene separadas en
`session-guard.ts`. Redirigir al acceso ante *cualquier* error convertía un 429
o un tiempo de espera en un bucle de redirección: la página de acceso veía la
cookie todavía en el jar, devolvía al panel, el panel fallaba otra vez.

Solo redirige cuando no hay sesión. Una caída de la API se muestra como caída,
con `ServiceUnavailable`, porque decir «no tiene expedientes» cuando el
servicio está caído es una falsehood sobre la que el usuario actuaría.

## El gestor de evidencias

Vista de **tarjetas** y vista de **tabla**, porque responden a preguntas
distintas: la tarjeta dice qué es esto y si parece correcto; la tabla dice
comparar estos veinte, y es donde los pesos y la reducción se alinean en
columnas.

Las dos vistas existen con un motivo cada una, y el `MASTER_PROMPT` sección 39
pide las dos.

### Las seis etapas de la subida

`MASTER_PROMPT` pide mostrar seis pasos. La API es síncrona: un `POST` valida,
comprueba seguridad, almacena, optimiza y genera la vista previa, y contesta.
Dos de esos pasos **no son observables por separado**, y fingirlo sería animar
una barra que no informa de nada.

La regla en `components/evidencias/stages.ts`: una etapa avanza solo cuando hay
motivo para creer que ocurrió.

| Etapa | En qué se basa |
| --- | --- |
| Subiendo | El contador de bytes real de `XMLHttpRequest.upload` |
| Validando | Subida completa, respuesta pendiente |
| Verificando seguridad | Llegó la respuesta: validaron y comprobaron seguridad. Un rechazo salta a «Rechazado» con la frase del servidor |
| Optimizando | El servidor encoló trabajo, o hay derivados sin vista previa |
| Generando vista previa | Existe un derivado de tipo `preview` |
| Listo | La evidencia alcanzó el estado listo |

Un pipeline terminado marca su última estación como **completa**, no como
«en curso»: dejarla dibujada como el nodo en marcha con anillo y pulso decía que
el trabajo seguía corriendo después de haber terminado.

### Cifras que no se inventan

`peso optimizado` y `reducción` son dos de las columnas que pide la sección 39, y
el listado **no las trae**: informa de cuántos derivados hay, no de qué pesan.
En vez de una columna de guiones o de un cálculo hecho a medias, el detalle se
pide una vez por evidencia y se cachea.

Una raya significa «sin medir todavía», nunca «cero». Y hay tres desenlaces que
no se confunden:

| Situación | Se muestra |
| --- | --- |
| Detalle no cargado | `—` |
| Sin derivados | `—` |
| El derivado pesa igual | `sin cambio` |
| El derivado pesa **más** | `mayor` |

Recortar un negativo a `0 %` e imprimirlo como ahorro sería una afirmación falsa
en un documento sobre evidencia, y es exactamente lo que hacía la primera
versión.

Lo mismo en la cadena de custodia: una evidencia sin original **no** muestra una
caja verde de «SHA-256 registrado». No hay hash porque el archivo no llegó a
almacenarse, y un panel de integridad no puede afirmar una verificación que no
ocurrió.

### `compression_ratio` es un porcentaje

El backend lo devuelve ya en porcentaje —su docstring decía `0..1` mientras
multiplicaba por 100, y el rastro de custodia lo imprime con `%`—, así que el
frontend lo multiplicaba por 100 otra vez y pintaba «1224 %» de un 12 % de
ahorro. Corregida la docstring, añadido
`test_compression_ratio_is_a_percentage_not_a_fraction`, y el valor **negativo**
se muestra como «más grande que el original» en vez de «compresión».

## Carga perezosa

- Las miniaturas se piden solo al entrar en viewport, con `IntersectionObserver`.
- Los detalles para las columnas de la tabla se piden **en secuencia**, no en
  paralelo: cien filas habrían abierto cien sockets contra la API.
- El contexto de React memoiza la lista derivada para que cambiar el filtro no
  vuelva a recorrer el array entero en cada render.

## Accesibilidad

- `prefers-reduced-motion` desactiva todas las animaciones.
- El anillo de foco es visible y de 2 px en el color de acento.
- La barra de progreso lleva `role="progressbar"` con sus valores.
- Los estados del pipeline se anuncian con `aria-live="polite"`.
- El cajón de custodia es un diálogo con `aria-modal` y cierra con `Escape`.
- Las tablas llevan `caption` descriptivo y las columnas de acción, `sr-only`.

## Verificación

Realizada sobre la aplicación en ejecución, no solo compilada:

- `tsc --noEmit`, `eslint` y `next build` sin avisos.
- Las seis rutas responden 200 y renderizan con datos reales.
- Subida real de un PNG y un PDF: derivados creados y SHA-256 mostrado.
- Un ejecutable renombrado a `.pdf` **rechazado** por el servidor con su propio
  mensaje: «Tipo de archivo no permitido: application/x-dosexec».
- Descarga del original en streaming: 200, `image/png`, 10 541 bytes, idénticos
  al archivo subido.
- Refresco con token caducado a propósito: la sesión se renueva sola.
- **Aislamiento**: un cliente ve su expediente y ninguno de los otros tres; la
  URL de un expediente ajeno responde 404, no 403.

## Pendiente

- El `MASTER_PROMPT` sección 39 pide la **usuario** en la ficha de evidencia. Se
  muestra la IP en la cadena de custodia; el nombre del usuario requiere resolver
  cada `actor_id`, y la API no lo expone en ese endpoint.
- El panel del cliente no tiene todavía las series temporales ni el
  comparativo de expedientes.
- Sin pruebas unitarias de frontend: no hay runner configurado. La verificación
  es manual sobre HTTP real y la puerta de calidad es el triple
  `typecheck` / `lint` / `build`.