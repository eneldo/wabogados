# SPEC - ADMINISTRACIÓN

## Estado: base y tres módulos implementados

## Decisión de la firma sobre «eliminar»

La firma pidió el CRUD completo, incluida la eliminación. `PROJECT_RULES.md`
regla 5 dice: *no eliminar registros jurídicos físicamente*. Preguntado, la firma
eligió **desactivar / archivar**. Por tanto:

- **No existe botón de borrar** en ningún módulo, y no hay `DELETE` que destruya
  un expediente.
- El `DELETE /clients/{id}` y `DELETE /lawyers/{id}` del backend **no borran**:
  son desactivaciones lógicas (`is_active = false`) y conservan expedientes,
  documentos, evidencias e historial.
- Un expediente se cierra con `POST /close`; nunca se elimina.
- Un cliente o abogado desactivado desaparece del listado por defecto y solo
  reaparece con «incluir inactivos». Sigue siendo editable y su ficha sigue
  abierta.
- Si en el futuro la firma exige el borrado físico, hay que anular la regla 5 de
  `PROJECT_RULES.md` y `MASTER_PROMPT.md` por escrito, y avisar del riesgo:
  borrando un expediente se pierden sus documentos, evidencias, actuaciones y
  audiencias, y un cliente citado en un expediente cerrado deja una referencia
  rota.

## Lo que se pidió y lo que hay

La firma pidió un portal de administración con menú lateral y CRUD por módulo.
El backend de los doce módulos ya existía en fases anteriores; lo que no existía
era **ninguna** superficie de administración: cero rutas, cero componentes.

| Módulo | API | Interfaz |
| --- | --- | --- |
| Dashboard | completa | **hecha** (reutiliza `/dashboard`) |
| Expedientes | completa | **hecha** |
| Clientes | completa | **hecha** |
| Abogados | completa | **hecha** |
| Agenda y audiencias | completa | pendiente |
| Mensajes | completa | pendiente |
| Documentos y evidencias | completa | pendiente (gestor dentro de cada expediente) |
| Multimedial | no existe | fuera de alcance |
| IA Jurídica | no existe | fuera de alcance |
| Facturación | no existe | fuera de alcance |
| Seguridad | completa | pendiente |
| Configuración | completa | pendiente |

Los tres últimos de la derecha están en `MASTER_PROMPT.md` bajo «Fases futuras,
NO implementar aún». Aparecen en el menú **inactivos y sin enlace**, con una
etiqueta «Pronto» y una nota al pasar el cursor. La razón: el encargo incluye
verlos, y el proyecto los prohíbe; un elemento gris sin destino es un callejón
sin salida y un elemento gris con motivo es una hoja de ruta.

## Borrar: lo que dice la regla y lo que hace el botón

`PROJECT_RULES.md` dice: *no eliminar registros jurídicos físicamente*.

| Módulo | Botón | Qué hace la API |
| --- | --- | --- |
| Clientes | **Desactivar** | marca `is_active = false`; conserva todo |
| Abogados | **Desactivar** | ídem |
| Expedientes | **Cerrar** | `POST /close`, no `DELETE` |

## Qué hay en cada fila

Los tres listados ofrecen **Editar** siempre, y la acción de estado solo cuando
aplica: **Cerrar** en expedientes abiertos y **Desactivar** en clientes y abogados
activos. Un registro ya cerrado o inactivo no ofrece una acción de estado que no
haría nada, solo su edición.

Un expediente cerrado **no se puede reabrir** desde la interfaz. La API tampoco lo
hace. Si el cierre fue un error, el camino es un registro nuevo: reabrir un
expediente cerrado reescribiría su historia, que es justo lo que un expediente
debe impedir.

Las acciones llevan icono **y** verbo. Editar usa lápiz; Cerrar, expediente con
marca; Desactivar, persona retirada. Los SVG comparten caja, trazo y terminaciones,
y llevan `aria-hidden`: no sustituyen al texto ni duplican el nombre que anuncia
el lector de pantalla. El enlace Editar y el botón de estado comparten altura y
ritmo visual, pero la confirmación sigue siendo obligatoria para la consecuencia.

| Documentos, evidencias | (pendiente) | sin `DELETE`; retención por tiers |
| Consultas públicas | **Eliminar** | borrado real, por petición del titular |

El botón se llama «Desactivar» y no «Eliminar» porque eso es lo que ocurre. El
diálogo de confirmación lo dice con las dos frases que importan: *el registro no
se borra* y *sus expedientes siguen intactos*.

## Server Actions, no el proxy del navegador

`app/api/proxy/[...path]` tiene una lista blanca de rutas y existe para que los
componentes interactivos nunca manejen un token. El CRUD de administración es
justo lo que esa lista debe seguir conteniendo, así que **no se amplió**. Las
escrituras van por Server Actions, que se ejecutan en el servidor con la cookie
de sesión.

Consecuencia práctica: la comprobación de permiso **no está en la acción**, está
en la API. Un permiso comprobado en el cliente es un permiso que el llamante
puede saltarse; el único sitio que no se puede saltar es el servidor que posee
los datos.

## Los detalles del formulario que importan

- **`document_type` y `document_number` no se editan.** No están en
  `ClientUpdate` ni en `LawyerUpdate`, y la ficha lo dice. Cambiar el documento
  que identifica a una persona no es editar a alguien: es convertir la fila en
  otra persona, y eso merece una decisión, no un campo de texto.
- **Los errores van al campo, no a un cartel.** `ApiRequestError` descartaba
  `details`, así que un 422 llegaba como una frase que no nombraba ningún campo.
  Ahora la clase conserva el payload, la acción aplana
  `details.errors` a `{campo: mensaje}` y el formulario lo pinta bajo el input
  correspondiente, con `aria-invalid` y `aria-describedby`.
- **El diálogo se cierra solo después del éxito.** Si se cerrara con cualquier
  cambio de estado, un error de validación cerraría el formulario y perdería lo
  medio escrito.
- **Las especialidades son un `textarea`.** La API toma una lista de cadenas y
  no hay un editor de etiquetas que nadie pidió; una especialidad por línea es
  el único control que devuelve una lista.
- **Las áreas jurídicas son el catálogo sembrado.** `GET /lawyers/legal-areas`.
  Escribirlas a mano produciría trece formas de decir «Derecho laboral».

## El shell

- `app/(admin)/admin/layout.tsx` hace el control de sesión **una vez**, para toda
  la superficie. Antes vivía en cada página y una página nueva que lo olvidara
  era una puerta abierta.
- Un cliente que teclee una URL de administración va a su portal, no a un menú
  del que no puede abrir nada.
- El rail es `position: fixed` a partir de `lg`. Como está fuera de flujo, no
  reserva ninguna columna de rejilla: el `main` lleva `lg:pl-[calc(16.5rem+2.5rem)]`
  y ese valor tiene que coincidir con el ancho del rail.
- El shell lleva `overflow-x: clip`. Una tabla de seis columnas no cabe en un
  teléfono y se desplaza dentro de su propia caja, pero esa caja sigue
  sigiendo al *scrollable overflow* del shell y el área de administración entera
  acababa paneando de lado: el lector arrastraba y la página, cabecera incluida,
  se salía de la vista. `clip` y no `hidden`: `hidden` convertiría el shell en un
  contenedor de desplazamiento, que es justo lo que se quiere quitar, y rompería
  cualquier hijo `sticky`. El shell no se desplaza de lado; la tabla sí.

## Un fallo del backend que esta pantalla destapó

`GET /clients` contestaba **500 para todo el mundo**. La causa no era la interfaz:
`ClientResponse.document_type` es un `Literal` cerrado y la base contenía un
cliente con `NIF`, que el esquema no aceptaba. El listado serializa **todas** las
filas, así que un solo registro que no se puede convertir tumbaba el endpoint
entero — y el administrador veía una cartera vacía en lugar de una cartera con un
hueco.

Se añadió `NIF` (y `CC`) a los dos `Literal`, porque son documentos colombianos
reales y el script de siembra ya usaba uno. Con dos pruebas de regresión en
`test_hardening.py`: una que exige que las listas de clientes y abogados sean
idénticas, y otra que comprueba que un documento inusual **no** tumba el listado.

Pendiente de decisión de la firma: `DNI` es el documento argentino; en Colombia la
  cédula de ciudadanía es `CC`. El nombre del campo en pantalla es cosa de ellos.

## Lenguaje visual

La paleta no se inventó para esta revisión: papel, tinta, lacre y latón ya eran la
identidad del portal privado, y el trabajo fue de jerarquía, no de color.

- **Una regla de estado por fila**, en el borde izquierdo, teñida por lo que la
  fila es: `live` verde bosque, `held` latón (suspendido), `urgent` lacre,
  `closed` gris de regla. Es un `background-image`, no un `box-shadow`, porque la
  tabla es `border-collapse: collapse`.
- **Una píldora por fila**: el estado la lleva; la prioridad es un punto de color.
  Dos píldoras en la misma fila son dos gritos.
- **`.row-title` y `.row-meta`** son clases autónomas, no anidadas bajo `.ledger`:
  el mismo par tipográfico se usa en las tablas y en las listas del Dashboard.
- **`.row-actions` y `.row-action-link`** dan a Editar, Cerrar y Desactivar una
  gramática común: icono lineal, verbo visible, 32 px de alto y respuesta de foco
  sin desplazamiento de la fila.
- Las notas de sistema usan `RuleNote`, con filete de latón. Explican por qué no
  hay botón de borrar, y su ausencia parecería un descuido si no se dijera.
- Movimiento: entrada escalonada de filas con tope de ocho, y
  `prefers-reduced-motion` lo desactiva todo.

## El menú en un teléfono

Un ancho estrecho **no** recibe el raíl lateral: recibe una barra con el sello y un
botón hamburguesa. Lo que hay dentro es el mismo `AdminRail` del escritorio, con
los doce módulos y el pie con la persona, su rol y las dos salidas.

Decisiones y por qué:

- **El botón es un `<button>`** con `aria-expanded` y `aria-controls`, y su
  nombre cambia entre «Abrir» y «Cerrar el menú de administración».
- **El panel se desmonta al cerrarse.** Si quedara en el DOM con
  `display: none` seguiría siendo un `nav` más para un lector de pantalla, y sus
  enlaces se saltarían de forma distinta en cada navegador al recorrer el
  tabulador.
- **Escape cierra y el foco vuelve al botón** que lo abrió.
- **Al abrir, el foco entra** al panel y el fondo deja de desplazarse. Sin lo
  segundo, el contenido se desliza por debajo del menú y este acaba flotando
  sobre otra página.
- **Se cierra al navegar**, con el estado ajustado durante el render y no en un
  efecto: cubre también el botón «atrás» del navegador, y `setState` dentro del
  cuerpo de un efecto es la cascada que la regla `react-hooks/set-state-in-effect`
  existe para impedir.
- `AdminRail` acepta `onNavigate`, y el panel se lo pasa para cerrarse antes de
  que se pinte la página nueva.

### El ítem activo, y su excepción

El raíl marca activo por **prefijo**: `/admin/clientes` sigue encendido mientras
se edita `/admin/clientes/8f3c…`, porque una comparación exacta apaga el
resaltado justo en el momento en que más hace falta saber dónde está uno.

La excepción es el dashboard. Su ruta es `/admin` y todas las pantallas empiezan
por `/admin/`, así que la regla de prefijo lo encendía en todas: el menú
mostraba dos ítems encendidos a la vez. **El índice de la superficie se enciende
solo cuando es la superficie.**

## Verificación

- `tsc --noEmit`, `eslint` y `next build` limpios.
- 586 pruebas del backend pasan, 85,68 % de cobertura.
- Cero desbordamiento horizontal en 320, 390, 768 y 1440, en las siete rutas
  construidas, y la página **no** panea de lado al arrastrar.
- Cero errores de consola en las siete pantallas tras la revisión visual.
- La tabla sí se desplaza dentro de su caja en móvil y tablet, y no lo hace en
  escritorio.
- **Cero ids duplicados** en las siete pantallas, verificado en el DOM. Es la
  comprobación que faltaba y que sí detecta un fallo real de accesibilidad: un
  `<label htmlFor>` apuntando a un id repetido enfoca el control equivocado sin
  avisar.
- Ciclo completo de cliente probado contra el despliegue: alta (201 y fila
  creada), edición (teléfono cambiado y cuatro entradas en el historial), y
  desactivación (204, `is_active = false`, la ficha lo refleja).
- Alta de abogado probada: las especialidades se guardan divididas en dos
  registros y el área jurídica llega como identificador.
- **Ciclo completo de expediente** probado contra el despliegue: alta
  (`WA-2026-000005`), edición (prioridad y jurisdicción), incorporación de abogado
  (pasa a colaborador), alta de parte (demandante con cédula) y cierre; el
  botón de cierre desaparece y la ficha lo refleja.
- **Acciones de fila probadas**: cierre de `WA-2026-000003` desde el listado —la
  fila pasó a «Cerrado» y el botón desapareció en el sitio, sin recargar— y
  desactivación de un cliente de humo, que confirmó `Inactivo` con «incluir
  inactivos». La desactivación de abogado se comprobó abriendo el diálogo y
  cancelando, **sin confirmar**: dejaría a la firma con un solo abogado activo.
  El camino de confirmación es el mismo componente que en clientes.
- La ficha oculta el par documento en edición, como debe ser.

## Decisiones que conviene no perder de vista

- **Expedientes no lleva permiso en el menú.** Se autoriza por alcance
  (`cases:read_all`, `cases:read_assigned`, `cases:read_published`) y la API ya
  filtra. Un `cases:read` inventado no restringe: esconde el módulo a todos.
- **Un expediente cerrado se puede corregir.** El backend lo permite y toda
  modificación queda auditada. No se invierte una política que nadie ha escrito:
  lo que se corrige es el texto, que antes prometía «íntegro» mientras ofrecía un
  formulario editable.

## Pendientes

1. **Agenda y audiencias**, **Mensajes**, **Documentos**, **Seguridad** y
   **Configuración**: la API está, las pantallas no. Agenda es el siguiente.
2. El **nombre visible de "Usuario"** en la cabecera del shell dice el correo de
   la persona porque `/auth/me` no devuelve todavía un nombre completo para
   administración.
3. La **salida de sesión** borra las cookies pero no revoca la sesión de refresco
   en el servidor; esa existe en la API y está sin conectar.
