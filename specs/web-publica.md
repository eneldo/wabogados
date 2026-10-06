# SPEC — WEB PÚBLICA

Desarrollar conforme a `MASTER_PROMPT.md` y a la referencia visual
`WABOGADOS_web.html`, cuyo enunciado instructivo está en `wabogados.html.md`.

## Estado: implementado

## Referencia visual

`WABOGADOS_web.html` es la referencia y se respeta su **composición, proporciones,
jerarquía y adaptación a celular**. El orden de secciones se conserva:

```
inicio (hero) → banda de confianza → servicios → firma → portal → equipo
→ actualidad → contacto → pie
```

No se sustituye por una plantilla genérica.

### Paleta corporativa

Los colores se toman literalmente del HTML de referencia:

| Token | Valor | Uso |
| --- | --- | --- |
| `--color-petrol` | `#132c35` | Botones principales, banda de confianza |
| `--color-petrol-soft` | `#20363c` | Títulos |
| `--color-gold` | `#b28b55` | Énfasis, precio, acción secundaria |
| `--color-ivory` | `#f7f5f0` | Fondo marfil |
| `--color-slate` | `#66767a` | Texto de apoyo |
| `--color-ivory-line` | `#ddd9cf` | Filetes |

La escala vive **aparte** de la del portal privado. La superficie autenticada es
un documento en el que un abogado trabaja —papel, tinta, lacre— y la web pública
es una declaración de la firma hacia alguien que aún no ha decidido fiarse. Son
dos voces de la misma firma; aplanarlas perdería las dos.

Esa separación tiene una consecuencia práctica que hay que resolver de forma
explícita: el `body` es uno solo y lo comparten todas las rutas, con el papel
`#f2eee4` del portal. Sobre ese papel, el marfil de la web pública se veía como
una hoja colocada sobre un escritorio, con una franja más oscura en los laterales
en cuanto la ventana pasaba de ~1440 px. La web pública no es una hoja: es la
página. Por eso monta `.site-canvas`, una capa fija que pinta el marfil de
principio a fin del viewport y va por detrás del contenido.

El lienzo se monta **solo** en la portada pública. `/login`, `/estado` y el portal
privado conservan el papel del documento: allí el papel es precisamente la señal
de que no se está en la web pública, y aplanar las dos superficies para que
casen en una captura sería mentir sobre una de las dos.

### Tipografía

La referencia usa Georgia para títulos y Arial para texto. Aquí se emplean
**Fraunces** e **IBM Plex Sans**, que la aplicación ya carga. Motivo: la
instrucción pide reutilizar estilos compartidos y evitar dependencias
innecesarias, y no hace falta una descarga de fuente para cubrir el mismo papel.

### Ilustración

El SVG de columnas y balanza se conserva íntegro mientras no exista un recurso
institucional aprobado. Va en línea, no en fichero, porque los degradados se
referencian por `id` y porque en línea evita una petición y un cuadro vacío en
la pantalla más importante del sitio. Los `id` llevan prefijo para no colisionar.

## Ritmo y escala tipográfica

**El diseño de referencia salta entre tamaños fijos de `font-size`.** Eso es lo
que hace que su versión estrecha se vea apretada: a 320 px un titular de 65 px se
queda sin sitio. Aquí la escala es **continua**, con `clamp()`:

| Elemento | Escala |
| --- | --- |
| Titular del hero | `clamp(2.45rem, 1.15rem + 5.6vw, 4.05rem)` |
| Títulos de sección | `clamp(1.95rem, 1.2rem + 3.1vw, 3rem)` |
| Texto | `clamp(0.95rem, 0.9rem + 0.2vw, 1.05rem)` |
| Padding de sección | `clamp(64px, 7.5vw, 118px)` |

Comido: el titular mide **39,2 px a 320** y **64,8 px a 1440**. La página está
compuesta a cada ancho, no tolerada en los pequeños.

El resultado medido en cinco anchos —1440, 1024, 768, 390 y 320— es **cero
desbordamiento horizontal** en todos.

## Movimiento

`Reveal` y `DrawRule` hacen que cada bloque llegue al entrar en pantalla, con un
escalonado de 60–90 ms entre hermanos, y que cada sección se abra con un filete
dorado que se dibuja. Las tarjetas de prácticas responden al ratón y al teclado:
el filete se engrana en dorado, el glifo se rellena y el enlace subrayado se
traza.

### El error que hizo que todo esto no funcionara

La primera versión llevaba el estado en `useState`:

```tsx
const [shown, setShown] = useState(() => typeof IntersectionObserver === "undefined");
```

Parece correcto y **no hace nada**. El inicializador lee `undefined` en el
servidor y una función en el cliente; React adopta el valor del servidor durante
la hidratación, así que los 50 bloques salían visibles desde el primer pintado
y el efecto quedaba muerto. Se detectó midiendo cuántos elementos seguían
esperando tras un desplazamiento completo: cero de cincuenta.

La corrección mueve el estado oculto al CSS y lo condiciona a `html.js`, una
clase que añade un `<script>` en línea antes del primer pintado:

```css
.js .site-reveal { opacity: 0; }
.js .site-reveal.is-in { animation: site-reveal …; }
```

El componente solo **añade** `is-in`. Así:

- el `className` es constante, así que no hay desajuste de hidratación;
- **sin JavaScript la clase `js` no existe**, la regla que oculta no casa con
  nada y la página entera está simplemente ahí, sin animación;
- con `prefers-reduced-motion` nada espera: se comprueba en la verificación.

Comprobado: al quitar la marca `js` quedan **0 elementos invisibles de 50**; con
movimiento reducido, **0 de 50**; tras un desplazamiento progresivo, **0
ocultos de 50**.

## Refinamientos

- La ilustración lleva una sombra amplia y difusa para leerse como un objeto
  colocado y no como un rectángulo de color.
- El hueco reservado del equipo se **limita a 300 px de alto** en pantallas
  estrechas. Sin tope, a 320 px son 280 px de vacío apilados tres veces, que
  empujan el resto de la sección fuera de la pantalla.
- El tinte del hueco llega por `--portrait-tint` en lugar de `background` en línea,
  porque el atajo en línea **reemplaza todas las capas** y se llevaba por
  delante la trama diagonal.
- «Pendiente» se lee sobre una placa, no suelto sobre el tinte.
- `scroll-behavior: smooth` y `scroll-padding-top: 100px`, para que la
  navegación por anclas no esconda el título de sección bajo la cabecera fija.
- Los botones del hero se apilan en columna por debajo de `sm`, donde la fila se
  parte en dos mitades desiguales.

## Tres cosas que NO se copiaron del diseño de referencia

1. **«Portal privado» enlaza al acceso real**, no a un diálogo de maqueta. La
   plataforma existe; una puerta falsa hacia el propio producto sería peor
   primera impresión que abrirla.
2. **No se inventa nada.** Ni un abogado, ni una fotografía, ni una dirección,
   ni un teléfono, ni una credencial, ni una trayectoria. Los huecos están
   marcados como pendientes.
3. **El formulario declara que no envía.** No existe endpoint de contacto en el
   backend, y la instrucción es explícita: mostrar éxito solo cuando el backend
   confirme la recepción.

## La identidad real de la firma

La web se había construido con la identidad entera marcada como pendiente. Eso
era correcto mientras no existiera el material, y dejó de serlo cuando apareció:
`WABOGADOS_recursos` traía las URL de los recursos originales y el sitio de la
firma los publica.

**Lo que ahora es real y verificable:**

| Dato | Procedencia |
| --- | --- |
| William Ruiz Villegas · Abogado fundador | `wabogados.co/team` |
| Faiber Andrés López Ruiz · Abogado junior | `wabogados.co/team` |
| Geraldine López Ruiz · Asesora de negocios | `wabogados.co/team` |
| Las tres fotografías | `WABOGADOS_recursos/03_equipo`, recuperadas |
| Siete áreas de práctica y su redacción | `wabogados.co` |
| Dirección, teléfono y horario | `wabogados.co` |
| Cita de Francisco de Paula Santander | `wabogados.co` |
| Rojas & Ríos Abogados · Wolfgang Ramírez | `WABOGADOS_recursos/04_aliados`, recuperadas |

Las áreas son **siete**, no las cuatro de la maqueta. La referencia es una
referencia de composición: recortar tres áreas que la firma ejerce para que
cuadren en cuatro columnas sería amputar la oferta para que case con el diseño.

### Lo que se dejó fuera, y por qué

- **Correo electrónico.** `wabogados.co` lo publica detrás de la protección de
  correo de Cloudflare, así que no está en el código fuente. Se dice
  explícitamente en la página en lugar de escribir un `@` plausible.
- **Los tres testimonios** del sitio (`Brian Rogers`, `Jessica Lee`,
  `John Summers`). Son relleno de demostración del tema: hablan de proyectos de
  diseño web y de derechos de autor de libros. No son clientes, y publicarlos
  como opinions de clientes sería inventar respaldo.
- **Formación, años de ejercicio, cartera y distinciones.** No están publicados
  en ninguna parte.
- **El precio de la consulta** que el sitio sí publica. Es un compromiso
  comercial y no va en una maqueta sin aprobación de la firma.

### Los retratos

Las tres fotos vienen en formas distintas: 480×480, 480×602 y 480×784. El
recorte 3:4 con `object-fit: cover` es lo que hace que tres personas distintas
se lean como una fila.

Van **en escala de grises hasta que llega el puntero o el teclado**, y entonces
recuperan el color. No es un capricho: tres fotografías en color seguidas
tiran de la página hacia otra firma que no es la que describe la paleta. Y una
firma que quiere parecer compuesta despacio debería decidir qué fotografías
llevan el color.

### Un fallo de la placa de aliados

`.ally-mark` llevaba `aspect-ratio: 3 / 2`. Con `aspect-ratio`, la altura de la
caja no es una longitud resuelta, así que el `max-height: 100%` de la imagen no
tiene contra qué resolverse y **el logotipo cuadrado se salía de su placa**,
dejando las dos cajas a distinta altura y el texto de una marca pegado al lado de
la otra. Se resolvió con una altura definida
(`height: clamp(200px, 22vw, 250px)`). Las dos placas miden lo mismo y ninguna
marca se recorta.

## El lienzo a ancho completo

Hay dos problemas distintos que se confunden y conviene separarlos:

1. **El tono equivocado a los lados.** El `body` es único y lo comparten todas las
   rutas con el papel `#f2eee4` del portal, más oscuro que el marfil `#f7f5f0`
   público. Se resuelve con `.site-canvas`, una capa fija que pinta el marfil de
   principio a fin del viewport. Va **solo** en la portada: en `/login`,
   `/estado` y el portal el papel es precisamente la señal de superficie privada.
2. **El contenido no llegaba a llenar la ventana.** El lienzo lo resuelve, pero el
   contenedor se quedó en un máximo fijo de 1200 px. A 1900 de ventana eso son
   345 px de marfil vacío a cada lado y la página se lee como una hoja estrecha en
   un escritorio vacío, aunque nada se desborde.

La solución es **una línea**: `width: 100%; max-width: 1560px`. El contenedor
crece con la ventana y se detiene; los párrafos conservan su límite en `ch`, así
que lo que gana espacio son las rejillas y no la medida de lectura.

Hubo un intento anterior con cinco tramos (1200 / 1380 / 1560 / 2000 / 2360) y un
segundo juego de overrides que agrandaba el texto por encima de 2200 px. **Se
revirtió porque empeoraba la página**: el texto dejaba de pertenecer a la
composición y el diseño se convertía en una serie de saltos. Menos escalones, no
más escalones: los tramos se reservan para cambios de composición, que sí son
discretos por naturaleza.

La lección: «no desborda» y «se ve bien» son dos preguntas distintas, y la segunda
no la responde ninguna medida de `scrollWidth`.

### Dos trampas que dejó el intento

- **El BOM.** Al reescribir el archivo como UTF-8 **con BOM**, el analizador leyó
  `BOM + primer comentario + primer selector` como un único selector: la regla
  `.wrap` desapareció entera y el minificador emitió un `?` suelto delante. Sin
  error ni aviso; la página simplemente dejó de estar contenida. `CSS.supports`
  decía `true` para la declaración, porque la declaración era válida: lo que
  estaba mal era el selector. Se detecta midiendo, no mirando.
- **La resta en móvil.** `min(1560px, 100% - 4rem)` quita 64 px de una pantalla
  de 320 px además del relleno y deja 206 px de contenido. El aire ya lo dan
  `margin-inline: auto` y el `padding`.

## Barrido de responsividad

| Dispositivo | Ancho | Contenedor | Útil | Titular | Desbordamiento |
| --- | --- | --- | --- | --- | --- |
| iPhone SE | 320 | 310 | 270 | 39 px | 0 |
| iPhone 13 | 390 | 380 | 340 | 40 px | 0 |
| iPad vertical | 768 | 758 | 694 | 61 px | 0 |
| iPad horizontal | 1180 | 1170 | 1106 | 65 px | 0 |
| Portátil | 1366 | 1356 | 1292 | 65 px | 0 |
| Portátil | 1440 | 1430 | 1366 | 65 px | 0 |
| Escritorio | 1920 | 1560 | 1496 | 65 px | 0 |
| Monitor | 2560 | 1560 | 1496 | 65 px | 0 |
| TV 4K | 3840 | 1560 | 1496 | 65 px | 0 |

En los nueve: el lienzo mide el viewport, las siete tarjetas cierran la rejilla
cuadrada y nada se sale. El tamaño del título es un dato medido, no una suposición.

## Ritmo que responde a la ventana

### La primera tarjeta abre la composición

Siete áreas en cuatro columnas son `4 + 3`, y la celda vacía al final de la
segunda fila se lee como un descuido. En dos columnas son `2+2+2+1`, peor. La
primera área ocupa la fila completa desde `sm` y se pone en petróleo: los siete
elementos cierran en dos filas y, de paso, el área por la que la firma encabeza
aparece con más peso y es la única que no mide igual que sus vecinas, que es lo
que impide que una fila de cajas idénticas parezca una tabla.

### La cabecera devuelve espacio

Pasa de 90 px a 66 px al superada la primera pantalla, marca en dorado la sección
en lectura y lleva una barra de avance de 2 px. Los tres valores se calculan en
un **único `requestAnimationFrame`** sobre un listener pasivo: tres listeners
harían tres lecturas de maquetación por cada frame de scroll.

El paralaje escribe una propiedad personalizada, no estado de React. Son sesenta
actualizaciones por segundo, y un `setState` por frame volvería a renderizar el
subárbol del hero entero para mover una caja catorce píxeles.

### Un `backdrop-filter` crea un bloque contenedor

El velo del menú móvil estaba dentro de la cabecera, que lleva `backdrop-filter`.
Un elemento con filtro se convierte en bloque contenedor de sus descendientes
`position: fixed`, así que el `inset: 0` del velo se resolvía contra los 91 px de
la cabecera y no contra el viewport: cubría una banda, quedaba detrás y no
recibía el toque. Por eso ahora es **hermano** de la cabecera.

### El orden del menú sigue a la página

`La firma` antes que `Servicios`, como en la maqueta de referencia. Con el
marcador de sección activa eso hace que el resaltado camine hacia atrás mientras
se lee. El orden del menú ahora sigue el orden de las secciones.

## Nada inventado: dónde está cada hueco

Lo que la página afirma sobre la firma se ha verificado en su propio sitio. Lo
que sigue sin estar, se dice en la propia página:

| Hueco | Cómo se señala |
| --- | --- |
| Correo electrónico | «por confirmar», con la razón: lo publica protegido y no se puede leer del código |
| Formación, años de ejercicio, cartera, distinciones | Nota bajo el equipo: se publican nombres, cargos y fotos, **no** el resto |
| Artículos | «Contenido de ejemplo» en la tarjeta, en el diálogo y en la nota; con etiqueta «Pendiente de aprobación» |
| Aviso de privacidad | «Pendiente de revisión»: faltan la razón social completa y el canal para ejercer los derechos |
| Portal ilustrado | Cifras ficticias con la etiqueta «Vista de ejemplo» y una nota que lo dice |

Un mensaje de éxito que miente sobre un formulario que pide el nombre, el
teléfono y el correo de una persona con un problema legal sería lo más dañino
que pudiera llevar esta página. Por eso el formulario envía de verdad y solo
confirma con un 201, y por eso el aviso legal se declara pendiente en la propia
página en vez de enlazar a un texto vacío.

## Formulario de contacto

`ContactForm` es un **cliente** porque gestiona estado, y ahora **envía de
verdad**: `POST /api/consultas` en el frontend, que reenvía a
`POST /api/v1/consultations` en el backend.

El éxito se muestra **solo** con un 201. Ese es el contrato entero del
componente: se dice a la persona que su solicitud quedó registrada porque
existe una fila, nunca porque se pulsó el botón.

### Por qué una ruta propia y no el proxy existente

`app/api/proxy/[...path]` exige sesión, y este formulario lo usa alguien que no
tiene cuenta: es justo para eso. Además el proxy permite cualquier verbo y
cualquier ruta bajo una lista de prefijos; `app/api/consultas/route.ts` es una
ruta fija, un verbo y un cuerpo **reconstruido campo por campo**. Una ruta que
reenvía lo que le llegue es un agujero con un limitador delante.

### Lo que decide el backend, no la página

El texto de confirmación lo devuelve la API, no el componente. Una página que
escribe su propio mensaje de éxito puede prometer más de lo que el servidor
prometió, y esa es exactamente la promesa que aquí importa.

### El formulario no vacía nada antes de saber

Cuando la API responde 429 o falla la red, el formulario **conserva lo escrito**.
Alguien que escribió la descripción de su problema legal y fue limitado no puede
volver a perderla.

### Rampas y fricción deliberadas

- **Trampa anti-bot.** Un campo invisible (`website`) que una persona no puede
  ver. Llenarlo produce un 422 como cualquier campo inválido y **no** guarda
  nada. Devolver «recibido» sería mentira; nombrar el campo no le aporta nada al
  que ya lo llenó.
- **Consentimiento como columna.** `consent_at` y `privacy_notice_version` se
  guardan en la fila. Una afirmación de consentimiento que no se puede
  reconstruir después no es consentimiento.
- **Sin IP ni user agent.** Ya están en `audit_logs`, que registra la petición
  sin leer su cuerpo. Copiarlos aquí duplicaría datos personales en una segunda
  tabla sin ganar nada.
- **Sin `change_logs`.** El resto de la aplicación deja un historial por campo.
  Hacerlo aquí escribiría el nombre, el teléfono, el correo y el problema legal
  en una segunda tabla, y quien pidiera su eliminación tendría que ser borrado de
  dos sitios o la promesa sería falsa.
- **Borrado real.** `PROJECT_RULES.md` prohíbe borrar físicamente registros
  jurídicos. Una solicitud que nunca llegó a ser expediente no es un registro
  jurídico, y la persona tiene derecho a que desaparezca. Un borrado lógico
  cumpliría la letra y anularía el propósito: el problema legal seguiría en la
  tabla. `ConsultationService.erase` borra de verdad, y la auditoría deja rastro
  del borrado sin guardar lo que contenía.
- **Presupuesto más bajo de la aplicación:** tres envíos por IP y por hora,
  porque es la única escritura sin credenciales y lo que acepta es el problema
  legal de alguien.

### Aviso de privacidad

Recogiendo nombre, teléfono, correo y descripción de un problema jurídico, el
formulario **debe** llevar aviso. Está redactado con lo que la firma publica
—razón social, dirección y teléfono— y marcado en la propia página como
**pendiente de revisión por el despacho**: faltan la razón social completa y el
canal para ejercer los derechos.

## Encabezado y navegación

Cabecera fija con desenfoque, 90 px, marca con la inicial en dorado y el
rótulo «ESTRATEGIA JURÍDICA» espaciado. Navegación a 13 px que vira a dorado al
pulsar.

### Un bug de especificidad que hizo el botón invisible

`.site-nav-links > a` tiene especificidad (0,1,1) y gana a `.site-btn` (0,1,0).
El botón «Portal privado» heredó **texto petróleo sobre fondo petróleo**: un
botón sin etiqueta legible. En la referencia ese elemento era un `<button>`, que
nunca casa con esa regla.

La corrección va en la regla —`a:not(.site-btn)`— y no en el botón, porque el
defecto es de la regla, no del botón.

### Menú móvil

Por debajo de 900 px la navegación pasa a un panel desplegable con
`aria-expanded` y `aria-controls`. Cierra al navegar y con `Escape`.

## Diálogo

`<dialog>` nativo, que aporta trampa de foco, fondo inerte y cierre con
`Escape`. Lo que **no** hace por su cuenta es devolver el foco al elemento que
lo abrió, y eso se añade: quien cierra con el teclado debe volver al enlace que
pulsó, no al principio del documento.

## Destino tras autenticarse

La web promete un portal para cada rol, así que el acceso lo cumple. La ruta se
decide en el servidor a partir de los roles y permisos que la API acaba de
devolver, nunca por el nombre del rol suelto:

| Quién entra | Destino |
| --- | --- |
| Cliente | `/portal` |
| Personal (abogado, asistente, administración) | `/expedientes` |

Comprobado sobre la aplicación en ejecución: un cliente aterriza en su
expediente y la administración en la cartera.

## Página de estado

La página de estado del sistema pasa a `/estado` y sigue enlazada desde el pie
público. La raíz `/` es ahora la web pública, que es lo que corresponde a la
portada de un dominio.

## Accesibilidad

- El primer tabulador alcanza la marca, que es un enlace real.
- Foco visible de 2 px en el color de acento.
- `aria-label` en la ilustración y en los espacios reservados del equipo.
- El diálogo declara `aria-label` y devuelve el foco al cerrarse.
- El estado del formulario es `role="status"` con `aria-live="polite"`.
- El `404` está redactado para no revelar si un expediente existe, que es
  justamente lo que el `404` del backend esconde.

## Verificación

Realizada con medición, no con impresión, en nueve tamaños reales —iPhone SE
320, iPhone 13 390, iPad vertical 768, iPad horizontal 1180, portátil 1440,
escritorio 1920, monitor 2560, monitor 3440 y TV 4K 3840—, contra la aplicación
en ejecución:

- `tsc --noEmit`, `eslint` y `next build` sin avisos.
- `/`, `/login`, `/estado` responden 200; `/portal` y `/expedientes` redirigen a
  307 sin sesión; una ruta inexistente da 404.
- **Cero desbordamiento horizontal en los nueve tamaños.**
- `.site-canvas` mide exactamente el ancho del viewport en los nueve.
- El contenedor de contenido sube de 310 px a 2360 px y la escala tipográfica de
  39 px a 114 px de titular: 39/31/15 en móvil, 61/43/16 en tablet, 65/48/17 en
  portátil, 90/67/18 a 2560 y 114/86/21 a 3440 y 3840.
- Las siete tarjetas cierran la rejilla cuadrada en los nueve tamaños.
- El título de la tarjeta principal se renderiza en marfil sobre petróleo.
- Cabecera: se condensa, marca la sección en lectura y la barra de avance crece
  con el scroll.
- El menú móvil abre visible, el velo cubre el viewport y el toque fuera lo cierra;
  `Escape` también. El velo no existe como objetivo por encima de 900 px.
- Con `prefers-reduced-motion: reduce`: sin paralaje (la propiedad ni se escribe),
  sin flotado, `transform: none` y transiciones a 0.001 s.
- `:focus-visible` pinta el anillo en dorado `rgb(178,139,85)`.
- Formulario: envío real con 201, referencia devuelta y formulario vaciado solo
  después de la confirmación; 429 en el cuarto envío dentro de la ventana.

Cola de entrada, contra el contenedor desplegado:

- Lectura sin credenciales → 401. El rol cliente → 403.
- `PATCH` a `en_revision` deja `handled_by` y `handled_at` escritos.
- `DELETE` → 204 y la fila **desaparece**; un `GET` posterior da 404.
- `audit_logs` registra el `POST` anónimo y los cambios del equipo, con método y
  ruta, **sin** ningún dato personal del cuerpo.

## Pendientes reales

1. **Aviso de privacidad aprobado por el despacho.** El texto existe y se
   declara pendiente en la propia página; faltan la razón social completa y el
   canal para ejercer los derechos.
2. **Interfaz de la cola en el portal.** El backend expone lectura, cambio de
   estado y borrado; no hay pantalla para el personal. Sin ella, las solicitudes
   solo se ven por API.
3. **Correo electrónico de la firma**, protegido tras Cloudflare.
4. **Términos y textos legales** adicionales.
5. **Contenido editorial** de actualidad, pendiente de aprobación de la firma.
6. **Confirmación a la persona.** La API registra la solicitud y la confirma en
   pantalla, pero no envía correo: no hay servicio de correo configurado ni
   dirección de la firma.
7. Los **testimonios** no se usan: los del sitio de la firma son relleno de
   demostración del tema.