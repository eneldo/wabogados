<!-- Nuevos aprendizajes debajo de esta línea -->

- **2026-10-22 — Unificar un tema oscuro exige separar texto, fondos y estados:**
  **Contexto:** Al extender la marca de la portada a los portales, las clases
  antiguas reutilizaban `ink` como texto y fondo, y `paper` como fondo y texto
  inverso. Cambiar solo sus valores habría creado botones/overlays claros con
  texto blanco o estados ilegibles.
  **Aprendizaje:** Usar tokens por función (`canvas`, `surface`, `shell`,
  `overlay`, `action`, `on-action`) y un logo compartido, no invertir colores
  mediante filtros ni reescribir valores por cada rol. Mantener éxito/advertencia
  distintos de la marca. Las rejillas privadas necesitan `min-width: 0` para
  que textos largos no ensanchen toda la página en móvil.
  **Aplicación futura:** `BrandLogo` y `globals.css` como fuentes únicas;
  `e2e/brand-assertions.ts` comprueba imagen descargada, proporción, colores
  calculados y pares de contraste, además de probar shell móvil y diálogos.

- **2026-10-22 — La URL interna y el autocompletado también forman parte del acceso:**
  **Contexto:** El administrador podía iniciar sesión, pero reabrir `/login`
  producía HTTP 500: esa página consultaba `localhost:8000` desde el contenedor,
  ignorando `API_INTERNAL_URL`. En el formulario, campos DOM llenos podían enviar
  valores React vacíos (422).
  **Aprendizaje:** Una comprobación de login no basta: hay que reabrir el acceso
  con sesión vigente y distinguir 401 de indisponibilidad. La identidad no puede
  usar un objeto vacío como respaldo. El autocompletado no garantiza eventos de
  cambio React; leer `FormData` al enviar evita desincronización de los valores.
  **Aplicación futura:** Reutilizar cliente servidor/guarda existentes y una
  clasificación de roles compartida. Regresiones en `e2e/admin-portal.spec.ts`
  para cookies inválidas, roles combinados, autocompletado y recorrido real.

- **2026-10-22 — Verificar recursos servidos y CSS calculado, no solo cadenas en fuente:**
  **Contexto:** El logo estaba referenciado en el HTML pero su URL respondía 404;
  los colores nuevos figuraban únicamente en un comentario CSS. Varias pruebas
  anteriores declararon éxito leyendo fuente o artefactos locales distintos de
  la imagen Docker que atendía el puerto 3000.
  **Aprendizaje:** Un nombre en HTML/CSS no prueba una imagen cargada ni una
  variable válida. Compose empaqueta el frontend: reiniciarlo no copia cambios
  del host, y borrar `.next` local no modifica el contenedor.
  **Aplicación futura:** Copiar recursos al contexto `frontend/public`, definir
  tokens en reglas reales, reconstruir imagen y recrear solo frontend. Afirmar
  HTTP 200 y MIME de `currentSrc`, `naturalWidth`, proporción y colores calculados
  en navegador sobre la URL desplegada. Regresión: `e2e/public-site.spec.ts`.

- **2026-10-22 — Probar una página por URL directa no verifica cómo llega el usuario:**
  **Contexto:** El administrador autenticaba correctamente y las 13 páginas
  administrativas abrían por URL directa, pero el login lo enviaba al listado
  anterior sin menú administrativo; reabrir login con sesión lo mandaba a una
  pantalla titulada «Portal del cliente». La prueba de acceso previa navegó
  manualmente a `/admin` y no comprobó el destino inicial.
  **Aprendizaje:** Exigir únicamente un HTTP 200 o abandonar `/login` deja pasar
  una redirección al portal equivocado. El camino de entrada y el regreso con
  sesión existente son comportamientos distintos de la autorización de destino.
  **Aplicación futura:** Para cada perfil, afirmar la URL y la navegación visibles
  tras autenticación, al reabrir el acceso con sesión y al entrar desde la web;
  después comprobar páginas internas y cierre de sesión por separado.

- **2026-10-22 — Un pin de imagen no es un archivo: los registries pueden retirar lo que se fija:**
  **Contexto:** Al levantar el stack restaurado, `minio/minio` dio «pull access
  denied» en Docker Hub y en Quay a pesar de pulls de control correctos con
  otras imágenes. No era rate limit ni red: MinIO retiró sus imágenes oficiales
  de ambos registries en 2026 y el comunitario quedó «solo código fuente».
  **Aprendizaje:** Un pin por etiqueta es una referencia a un objeto que un
  tercero puede destruir; la dependencia real es «la imagen que yo tengo en el
  host». Para una imagen crítica: fijar por **digest** (`image@sha256:...`),
  conservar una copia propia (`docker save`) o construir desde código propio —
  y no celebrar que «las pruebas pasan» en un entorno por derecho de haber
  descargado entonces, porque el reproducibilidad se mide desde cero.
  **Aplicación futura:** Si el stack vuelve a necesitar un objeto-S3 local para
  probar el camino `STORAGE_BACKEND=s3`, no depender de un registry vivo:
  guardar una copia de la imagen en `infra/images/` o sustituirla por un
  contenedor propio que hable S3. El destino del respaldo externo, mientras
  tanto, ya no es MinIO: es un proveedor S3 de la firma.

- **2026-10-21 — Migrar un proyecto de Windows a Linux deja dos capas de CRLF, no una:**
  **Contexto:** Al auditar tras cambiar de Windows a Fedora había 24 ficheros
  tracked con CRLF en el árbol de trabajo, ~6.500 líneas de diff "modificado",
  y el fix de seguridad de mensajería enterrado bajo ese ruido. Añadir
  `* text=auto eol=lf` + `git add --renormalize .` limpió la mitad: los ficheros
  EOL-only desaparecieron del diff, pero tras convertir el árbol físicamente a
  LF apareció un estado "modificado con diff vacío" — el índice ya estaba en LF
  y el `M` era solo caché de stat, que `git add -u` refrescó.
  **Aprendizaje:** Un cambio de plataforma se ve en tres capas que se resuelven
  en distinto momento y con distinta herramienta: (1) el diff cruel del
  navegador, que `.gitattributes` abstrae; (2) los blobs almacenados, que
  normaliza `--renormalize`; (3) la caché de stat, que refresca `git add -u`.
  Y `git status` puede mentir en ambas direcciones cuando cambia la
  configuración de atributos: verificar con diff antes de creerlo.
  **Aplicación futura:** Antes de confirmar trabajo real sobre un diff masivo,
  aislar siempre `git diff -w`; si solo cambian líneas, el commit de
  normalización debe ir separado para que el cambio de contenido quede leíble y
  reversible.

- **2026-10-05 — Un argumento obligatorio convierte un olvido en un error de compilación:**
  **Contexto:** El IDOR de documentos venía de que `get_visible_document` comprobaba
  visibilidad y **no** alcance de expediente, mientras el listado sí lo hacía. La
  corrección obvia era añadir `scope_clause=None`, copiando la firma de
  `get_visible_evidence`. Con ese valor por defecto, un endpoint nuevo compila,
  pasa todas las pruebas y **reintroduce la fuga sin delatar nada**.
  Se hizo obligatorio y sin valor por defecto: `mypy` falla en cualquier llamador
  que no decida qué expedientes alcanza, y una ruta nueva tiene que pensarlo.
  **Aprendizaje:** Un defence opcional no es una defensa. Además centralicé la
  comprobación en un único `_visible_document()` del router, porque cinco
  llamadores que construyen la cláusula son cinco sitios donde el siguiente
  endpoint se olvidará. Y la prueba que importa no es la que falla: es la que
  **comprueba que el llamante legítimo sigue entrando**, porque un filtro
  demasiado estrecho también es un fallo.
  **Aplicación futura:** Al añadir una condición de seguridad a un método que ya
  tenía un valor por defecto, preguntarse si ese valor por defecto es el
  seguro. Si no lo es, quitarlo y dejar que el comprobador lo exija.

- **2026-10-05 — Una nota repetida en tres sitios se vuelve más creíble, no más cierta:**
  **Contexto:** Se pidió «desbloquear» Facturación e IA Jurídica porque la memoria
  decía que eran «los dos módulos que el brief todavía prohíbe, inertes con su
  motivo». Se verificó en el navegador antes de tocar nada: **los dos funcionan**,
  con backend, permisos sembrados, migraciones y pantalla. La afirmación obsoleta
  llevaba varias sesiones propagándose por `NEXT_STEPS` y `project_context` sin
  que nadie la comprobara.
  **Aprendizaje:** Es el mismo caso que `objects.count` o el `retry_after` de la
  cola de solicitudes, pero aplicado a la **memoria**: un dato que nadie lee se
  vuelve una afirmación, y repetirla en tres ficheros la convierte en consenso
  sin añadir evidencia. La asimetría es real: verificarla cuesta un minuto una
  vez; darla por buena cuesta todo lo que se construya sobre ella después.
  **Aplicación futura:** Antes de «desbloquear», «arreglar» o «completar» algo que
  la memoria declara pendiente, **comprobar que sigue siéndolo**. Y cuando una
  nota resulté falsa, corregirla en **todos** los sitios donde aparece, no solo en
  el que se leyó: la copia es la que mantiene viva la mentira.

- **2026-10-05 — Una puerta que nunca falla es una puerta que no mira:**
  **Contexto:** Se automatizó la comprobación de desbordamiento horizontal y dio
  tres fallos de 320 y 390 px. Al mirar el DOM, `scrollWidth` era **igual** al
  viewport: la página no se desplazaba. La detección enumeraba elementos que
  sobresalen del ancho y eso no es desbordamiento, es una tarjeta con hijos anchos
  dentro de una maqueta que aguanta.
  **Aprendizaje:** El síntoma que siente una persona es «puedo arrastrar la página
  hacia los lados», y su medida es `scrollWidth > clientWidth`. Enumerar culpables
  es útil como **explicación** de un fallo ya existente y es una fuente de falsos
  positivos como **veredicto**. Y el proyecto ya lo tenía escrito: *no basta
  comprobar atributos ARIA: hay que comprobar que el elemento sea visible y
  operable*. Lo mismo con el ancho.
  **La parte que más importó:** una puerta nueva no se da por buena porque pase.
  Se inyectó `body { min-width: 200vw }`, se comprobó que la puerta **fallaba**,
  y se revirtió. Una comprobación que nunca ha fallado no ha sido probada.
  **Aplicación futura:** Ante una comprobación automática de una propiedad visual,
  elegir la medida del síntoma, no la de un correlato, y **provocarla a propósito**
  para demostrar que la puerta detecta.

- **2026-10-05 — Contar con el reloj como identidad colapsa lo que se quiere medir:**
  **Contexto:** El limitador compartido usa un *sorted set* de Redis y añadía el
  `timestamp` como miembro. Dos peticiones dentro del **mismo milisegundo** se
  reemplazaban y `ZCARD` devolvía 1: el presupuestocrecía de uno en uno pero el
  tamaño del conjunto no, así que una ráfaga quedaba **ilimitada**.
  **Aprendizaje:** En un conjunto ordenado la identidad del miembro es lo que
  cuenta, y un reloj tiene una resolución. El defecto era invisible en lectura:
  `ZCARD` nunca pasaba de 1, lo que en un test parece más de lo debido y no lo
  suficiente. Lo cazó una sola prueba: **comparar el almacén nuevo con el
  anterior sobre una ráfaga**. La equivalencia entre dos implementaciones es un
  detector de defectos que ninguna prueba de la nueva implementación es.
  **Aplicación futura:** Al escribir la versión nueva de algo que ya existe,
  escribir la prueba que dice «las dos responden igual» antes que las que dicen
  «la nueva funciona». Y en cualquier contador por identidad temporal, advertir
  que el reloj no es único.

- **2026-10-05 — Un almacén caído no es un límite abierto:**
  **Contexto:** Al mover el limitador a Redis appeared la pregunta que no tenía
  respuesta: si Redis no responde, ¿qué hace el limitador? Tratarlo como «sin
  límite» desactiva el freno de `/auth/login` justo cuando alguien adivina
  contraseñas; negarlo todo convierte un incidente de Redis en una caída del
  despacho.
  **Aprendizaje:** Ninguna de las dos salidas por defecto era honesta: la primera
  es una puerta abierta y la segunda es una decisión de negocio disfrazada de
  detalle técnico. Se counting **en memoria** —un presupuesto más débil, pero un
  presupuesto— con error registrado, y se dejó el criterio contrario como
  configuración explícita (`RATE_LIMIT_FAIL_CLOSED`). El aprendizaje es anterior
  y sigue: *avisar o fallar, nunca fallar en silencio*. Lo nuevo es que **la
  degradación debe seguir contando**, porque degradar no es lo mismo que
  desaparecer.
  **Aplicación futura:** Al añadir una dependencia nueva a un control de
  seguridad, escribir la prueba de qué cuenta cuando la dependencia no está, y
  que esa respuesta sea un número.

- **2026-10-05 — Un respaldo escrito a través de PowerShell 5.1 es basura:**
  **Contexto:** Al ejecutar el ensayo de restauración, `docker compose exec -T
  postgres pg_dump ... > postgres.dump` produjo un archivo de **373 KB que
  `pg_restore` rechazó** («input file does not appear to be a valid archive»).
  Repetido con `cmd /c`, el mismo volcado salió en **184 KB y 357 entradas
  válidas**. El pipe `tar | tar` falló igual, con `bad header checksum`.
  **Aprendizaje:** PowerShell 5.1 decodifica la salida nativa y la vuelve a
  escribir con su codificación, así que `>` y los pipes **corrompen binario**. El
  síntoma es el peor posible: el archivo existe, pesa más que el bueno y no dice
  nada. Un tamaño mayor no es una copia mejor. Y el digest lo habría detectado,
  que es exactamente para lo que existe: por eso el paso previo
  `verify_backup` no es burocracia, es lo que separó «no se pudo crear el
  volcado» de «el volcado es basura».
  **Aplicación futura:** Para salida binaria nativa usar `cmd /c "docker ... >
  archivo"`, o mejor hacer el trabajo **dentro del contenedor** y sacar el
  resultado con `docker cp`. Y nunca dar por bueno un volcado sin pasarle
  `pg_restore --list` o el verificador del proyecto.

- **2026-10-05 — Una regla escrita en la documentación no es un control:**
  **Contexto:** `RESTORE.md` decía, con su razón, que el destino del respaldo
  externo no puede ser el bucket donde están los documentos. Llevaba ahí desde que
  existe el módulo y **nada lo comprobaba**: copiar las credenciales de
  `STORAGE_BACKEND` en las de `BACKUP_REMOTE_*` se aceptaba sin protestar, que es
  justo la configuración que anula la función entera.
  **Aprendizaje:** La distancia entre una regla y su cumplimiento se mide
  buscando quién la ejecuta, igual que entre un dato y su verificación. Una
  prohibición descrita en prosa no falla: no hace nada, y quien la lee le
  concede una confianza que no está ganada. Se cerró con TDD: dos pruebas rojas
  por `DID NOT RAISE`, la comprobación en `from_settings`, y dos casos más que
  fijan lo que **no** debe rechazarse, porque un control que también cubre el caso
  legítimo acaba enseñando a ignorar el error.
  **Detalle que importó:** la comparación normaliza la barra final. `https://host`
  y `https://host/` son el mismo servidor, y una comprobación que un solo carácter
  desactiva es una comprobación que el operador desactiva sin querer.
  **Aplicación futura:** Al heredar o escribir una restricción de seguridad en un
  documento, localizarla y preguntar quién la hace cumplir; si la respuesta es
  «nadie», convertirla en prueba antes que en prosa. Y al añadir un rechazo,
  escribir la prueba del caso legítimo que ese rechazo no debe cubrir.

- **2026-10-04 — Un formato de respaldo se escribe en una máquina y se lee en otra:**
  **Contexto:** El verificador de digested de objetos se probó con un manifiesto
  generado en Windows y verificado en un contenedor Linux. Todo apareció como
  ausente: `str(Path.relative_to())` escribe `objects\evidencias\a.pdf`, y en
  Linux eso es **un** nombre de archivo con barras invertidas, no una ruta.
  **Aprendizaje:** El síntoma —«todos los objetos faltan»— se lee como pérdida
  total de datos, y la causa era el separador. Un formato pensado para sobrevivir a
  una restauración debe fijar sus separadores, porque la plataforma que lo wrote
  no es la que lo lee. La suite de tests, ejecutada siempre en Linux, jamás lo
  habría visto: **el bug vivía en la diferencia entre el host y el contenedor.**
  **Aplicación futura:** En todo artefacto portable —manifiestos, JSON, rutas de
  copia de seguridad) usar `.as_posix()` y una prueba que prohíba explícitamente
  la barra invertida. Y cuando el código se ejecuta en dos plataformas distintas,
  probar en la que no se desarrolla.

- **2026-10-04 — Un dato escrito y nunca leído no es una verificación:**
  **Contexto:** `objects.count` llevaba tiempo en `backup.sh` y `KNOWN_ISSUES.md`
  lo criticaba como si fuera la verificación. No lo era: **nadie lo leía**, y
  `MANIFEST.sha256`, que sí tenía el digest de cada archivo, tampoco.
  **Aprendizaje:** La diferencia entre un control y un registro se nota preguntando
  quién consume el valor. Un número que nadie lee es documentación, y llamarlo
  «cuenta de objetos» junto al manifiesto invitaba a pensar que algo lo
  comprobaba. Presentarlo como verificación era peor que no tenerlo, porque
  desvía la atención hacia algo que no protege nada.
  **Aplicación futura:** Antes de criticar o defender un control, buscar su
  consumidor. Si no existe, decir «informativo» en el sitio donde se genera y en
  la documentación, para que nadie lo cite como comprobación.

- **2026-10-04 — N errores contados uno a uno suelen ser un solo error:**
  **Contexto:** SQLAlchemy 2.1 daba 33 errores de `mypy`: 11 por
  `Select[Model]` frente a `Select[tuple[Model]]`, y 18 más por atributos de
  fila que «desaparecían» (`event.id`, `action.next_action_at`). Todo apuntaba a
  29 estar en `dashboard.py`.
  **Aprendizaje:** Antes de reescribir, `reveal_type` sobre `.scalars().all()`
  devolvió `Sequence[Case]` **sin error**. Los errores de atributo eran
  consecuencia: las anotaciones `Select[tuple[Modelo]]` de los helpers fijaban el
  tipo de fila y arrastraban todo lo demás. Cambiar esas ocho anotaciones a
  `Select[Any]` —la convención que el propio archivo ya usaba en otros dos
  métodos— resolvió los 33 de una vez.
  **Aplicación futura:** Cuando un mismo archivo concentra la mayoría de los
  errores, sospechar de las anotaciones que comparten los métodos y no de cada
  llamada. Y antes de corregir mecánicamente N errores, escribir el repro
  mínimo que los produce: si ese repro pasa, los N son el mismo defecto.

- **2026-10-04 — Congelar un valor viejo como contrato, no como nota:**
  **Contexto:** Sustituir Passlib por `argon2-cffi` era seguro solo si los hashes
  ya escritos en la base seguían validando. La forma de demostrarlo no es
  probarlo hoy, es dejar la prueba para siempre.
  **Aprendizaje:** `test_password_hashing.py` guarda un hash literal que escribió
  Passlib y **no importa Passlib**, así que el test sobrevive a la eliminación
  del paquete y sigue funcionando dentro de tres años. Además se comprobó con un
  login real sobre una cuenta existente. Un hash congelado es un contrato; un
  comentario que dice «los parámetros son los mismos» es una promesa.
  **Aplicación futura:** Al migrar cualquier cosa que toque datos persistidos,
  dejar el valor anterior como constante en un test y, si es posible, verificando
  además contra el sistema en ejecución.

- **2026-10-04 — Una prueba que no puede distinguir dos causas no es prueba:**
  **Contexto:** Al verificar la revocación de sesión, comprobé que el
  `revoked_at` de la fila pasó de nulo a valor y lo di por bueno. Pero la
  rotación de tokens de refresco **también** escribe `revoked_at` al gastarse:
  un 401 y una fila revocada son compatibles tanto con «se revocó al cerrar
  sesión» como con «se gastó antes». La prueba era ambigua y la acepté como
  prueba.
  **Aprendizaje:** Un indicador que dos mecanismos distintos pueden producir no
  prueba ninguno. Aquí el discriminador fue `audit_logs`, que registra la
  llamada: `POST /api/v1/auth/logout | success` en el instante del clic. Y la
  comprobación negativa —otra sesión del mismo usuario siguió activa— fue la que
  permitió distinguir «revocar esta» de «revocar todas».
  **Aplicación futura:** Antes de dar por buena una verificación de estado,
  enumerar qué otros mecanismos escriben ese mismo estado. Si hay más de uno,
  buscar un registro de auditoría o un contador independiente; y añadir siempre
  el caso negativo que separa las dos explicaciones.

- **2026-10-04 — Un gate que no puede ver el fallo no es un gate:**
  **Contexto:** Al borrar por accidente `uvicorn` de `pyproject.toml`, la imagen
  se construyó, `ruff` pasó, `mypy` pasó y las 678 pruebas pasaron. El servicio
  estaba muerto: `exec: "uvicorn": executable file not found in $PATH`.
  **Aprendizaje:** Ninguna prueba importa el entrypoint del contenedor, así que
  la suite entera es ciega a esa clase de fallo. La lección no es «añadir más
  pruebas»: es que **el gate tiene que poder observar lo que se rompe**. Aquí se
  pudo porque el `CMD` del Dockerfile es un dato legible, y la prueba compara ese
  binario contra las dependencias declaradas.
  **Aplicación futura:** Cuando un fallo solo lo detecta la ejecución del
  artefacto, buscar la forma de que un test lea ese artefacto. Y tras un
  incidente de este tipo, preguntarse qué otros gates lo habrían dejado pasar.

- **2026-10-04 — Un gate verde en tu máquina no es un gate verde:**
  **Contexto:** `mypy` estricto pasaba en el host con SQLAlchemy 2.0.43 y lo
  declaré restaurado. El rango abierto `<3` hacía que Docker resolviera 2.1.3,
  contra el cual hay **33 errores en 5 archivos**. Además el extra `dev` no
  declaraba `types-passlib` ni `types-python-jose`, así que en un contenedor
  limpio el gate no podía pasar aunque el código estuviera bien.
  **Aprendizaje:** Un gate verificado en un entorno es una afirmación sobre ese
  entorno. Y un gate que depende de paquetes instalados a mano no es un gate: es
  una costumbre. Los stubs que faltan no aparecen como error de código, sino
  como «Library stubs not installed», que se lee como un problema del entorno y
  se ignora.
  **Aplicación futura:** Declarar en el extra `dev` todo lo que el gate necesita,
  y verificar los gates con una **instalación limpia** (`pip install -e '.[dev]'`
  en un contenedor nuevo), no con el entorno del host ya instalado. Fijar los
  ceilings a lo verificado es lo que convierte un gate en un contrato.

- **2026-10-04 — Cuando el anotador refute tu anotación, no la fuerces:**
  **Contexto:** `revoke_all_for_user` usaba `result.rowcount` tras un `UPDATE`.
  Anoté `CursorResult[Any]` y `mypy` dijo que `execute` devuelve `Result[Any]`:
  la anotación era falsa. Las dos salidas fáciles eran un `cast` (una afirmación
  no verificada) o `isinstance` (una rama muerta).
  **Aprendizaje:** La tercera salida —`UPDATE ... RETURNING id` y contar las
  filas— es mejor que las dos: el conteo pasa a formar parte del resultado de la
  sentencia, así que lo tipa el sistema y lo calcula PostgreSQL, no el driver.
  Un `cast` sobre un valor que el tipo no promete es una mentira que el
  comprobador acepta porque se la pediste tú.
  **Aplicación futuro:** Ante un atributo que existe en ejecución pero no en el
  contrato de tipos, buscar la forma de que el dato venga *dentro* del resultado
  (`RETURNING`) antes de confirmar el contrato a mano.

- **2026-10-04 — Un `cast` es un punto ciego con permiso de anotador:**
  **Contexto:** Al cerrar los gates de `mypy`, tres de los siete errores de
  servicio eran el mismo error de diseño: `conditions` de facturación era
  `list[object]`, dos consultas de IA usaban `else True` en vez de
  `literal(True)`, y `media_type_label` usaba `cast(str, ...)`. Ninguno fallaba
  en ejecución.
  **Aprendizaje:** Los cuatro admitían la misma corrección fácil —`Any`, o el
  `cast` que ya estaba— y esa facilidad es la señal de alarma: el anotador
  obliga a escribir una afirmación de tipo en un punto donde nadie la verificó.
  Cuando el chequeo falla, el defecto está en el tipo que se estrecha en
  silencio, no en la anotación que falta.
  **Aplicación futura:** Ante un error de `mypy` en `where()`, `list[object]` o
  un `cast`, corregir el tipo real del dato en vez de silenciar al anotador. Y
  comprobar de antemano qué versión de la herramienta está instalada: una nota
  de deuda que atribuía siete avisos `ASYNC240` a `backup.py` describía una
  regla que no existe en el Ruff 0.12.11 del entorno, y no se había corregido
  nunca nada allí.

- **2026-10-04 — Anotar el tipo real de un fixture descubre bugs de test:**
  **Contexto:** 33 firmas de tests no tenían anotación. La tentación era
  `Any`. Al poner `Client`, `Lawyer` y `LocalStorage` aparecieron tres errores
  por `storage_key`, que es `str | None` porque un recurso registrado puede no
  tener archivo.
  **Aprendizaje:** Los tests afectados pasaban por la razón equivocada: pasaban
  `str | None` a un parámetro `str` y el runtime no distingue. Anotar el tipo
  real no es burocracia: es la única forma de que el comprobador vea el punto
  donde el test miente.
  **Aplicación futura:** Al anotar fixtures de `conftest.py`, esperar que
  aparezcan errores dentro de los tests. Un narrowing que hay que añadir con
  `assert ... is not None` suele estar tapando una aserción que no probaba lo
  que creía.

- **2026-10-03 — La zona del contenedor no es la zona del calendario:**
  **Contexto:** Una audiencia escrita como 11:00 se convirtió correctamente a 16:00 UTC, pero el Server Component la mostró como 16:00 porque `Intl.DateTimeFormat` heredó UTC del contenedor Node.
  **Aprendizaje:** Persistir UTC no basta: interpretar un `datetime-local` y presentar el instante deben compartir una zona de negocio explícita. El navegador y el servidor pueden tener zonas distintas y ambos resultados parecen válidos por separado.
  **Aplicación futura:** Centralizar zona y offset institucionales, usarlos en entradas y salidas, y verificar una hora real después del despliegue en contenedor, no solo la marca UTC de la API.

- **2026-10-03 — Una regla de prefijo se rompe con la raíz:**
  **Contexto:** El raíl encendía el ítem activo comparando por prefijo, para que `/admin/clientes` siguiera encendido al editar `/admin/clientes/8f3c…`. Pero la ruta del dashboard es `/admin` y **toda** pantalla empieza por `/admin/`, así que el dashboard quedaba encendido siempre: el menú mostraba dos ítems encendidos a la vez.
  **Aprendizaje:** Una regla correcta para nueve casos puede fallar en el décimo por ser la raíz. El prefijo solo es seguro si ningún href es prefijo de otro, y en un árbol de rutas el índice siempre lo es.
  **Aplicación futura:** Al comparar rutas para marcar activo, tratar el índice de la superficie como caso exacto y explícito, no como otro más. Y comprobarlo en cuatro rutas —índice, listado, ficha y otra ficha— no solo en la de listado.

- **2026-10-03 — Un menú móvil no es la versión corta del menú de escritorio:**
  **Contexto:** Los doce módulos ocupaban una tira horizontal de fichas. Filtraba los tres módulos «Pronto» porque no tienen `href`, empujaba el contenido de todas las pantallas con una barra que nadie pidió, y en móvil no había ni rol ni segunda salida: cerrar sesión era encontrar el único control que quedaba en la barra.
  **Aprendizaje:** Al responsive le basta con «que quepa» y entrega una versión recortada de lo que importa en escritorio. En un menú, lo recortado es justo lo que responde a «qué más existe»: los tres módulos prohibidos por `MASTER_PROMPT.md` y el pie con la identidad y las dos salidas.
  **Aplicación futura:** Cuando algo no cabe, preguntar qué pierde quien lo usa y devolver esa parte, en vez de una versión reducida por ancho.

- **2026-10-03 — `setState` en un efecto para reaccionar a una ruta:**
  **Contexto:** El menú se cerraba con un `useEffect` sobre `pathname`. ESLint lo rechazó con `react-hooks/set-state-in-effect`: produce una cascada de renders.
  **Aprendizaje:** Para «si esta entrada cambió, reinicia este estado», React pide ajustar el estado **durante el render**, no después. Es además la única forma de cubrir el botón «atrás» del navegador sin esperar un frame.
  **Aplicación futura:** Guardar el valor anterior en estado y comparar en el cuerpo del componente; si difiere, fijar ambos. Y cuando la acción sea «cerrar al navegar», pasar además `onNavigate` al enlace: cierra antes de que se pinte la página nueva.

- **2026-10-02 — Una tabla `border-collapse` no pinta la sombra de su celda:**
  **Contexto:** La regla de estado de cada fila iba como `box-shadow: inset`. El estilo calculado la mostraba en todas las filas y la pantalla no mostraba ninguna. Cambiada a `background-image: linear-gradient(...)` apareció al instante.
  **Aprendizaje:** `border-collapse: collapse` es exactamente el contexto donde `box-shadow` sobre una celda deja de pintarse, y es el peor fallo posible: el navegador confirma que el estilo está aplicado. Un degradado de fondo sí se pinta.
  **Aplicación futura:** Para marcar una fila o una celda, usar `background-image`, no `box-shadow`. Y cuando el estilo calculado dice que sí y la pantalla dice que no, sospechar del contexto de renderizado antes que de la especificidad.

- **2026-10-02 — Una clase de estilo anidada bajo un componente no viaja:**
  **Contexto:** `.row-title` y `.row-meta` se definieron como `.ledger .row-title`. Se usaron también en el Dashboard, fuera de `.ledger`, y no aplicaron: el número de expediente salió en IBM Plex Sans de 16 px en vez de la mono de 11 px y se partió en dos líneas.
  **Aprendizaje:** El alcance de un selector se parece a una dependencia invisible: la clase viaja a donde la copiaron y deja de funcionar sin aviso, porque el estilo por defecto es silencioso.
  **Aplicación futura:** Un estilo tipográfico que vale para dos sitios se declara autónomo. Si necesita contexto, que sea por elemento y no por ancestro, y comprobar el estilo **calculado** en el segundo sitio, no solo en el primero.

- **2026-10-02 — Arreglar un defecto de ids repetidos introduce el mismo defecto:**
  **Contexto:** Se eliminaron los ids duplicados de las fichas al añadir el diálogo de cierre al listado, que se monta una vez por expediente abierto: `close-closed_at` volvió a repetirse, esta vez tantas veces como expedientes abiertos.
  **Aprendizaje:** El arreglo correcto generaliza, y una corrección local aplicada en un sitio nuevo reintroduce el problema. Un id único depende de **quién monta el componente**, no del componente: quien lo reutiliza en un bucle es quien debe cualificarlo.
  **Aplicación futura:** Cuando un componente con ids propios se reutiliza en una lista, el prefijo tiene que ser un parámetro suyo. Y la comprobación de ids duplicados tiene que correr como puerta en cada cambio, no como tarea del arreglo anterior.

- **2026-10-02 — Una regla del proyecto puede ser una decisión del cliente, no un impediment:**
  **Contexto:** El encargo pedía CRUD completo con eliminación, y `PROJECT_RULES.md` prohíbe eliminar registros jurídicos físicamente. Preguntado, la firma eligió «desactivar / archivar».
  **Aprendizaje:** «No se puede» y «no se ha decidido» son cosas distintas. La regla existe para que alguien la confirme o la anule; negarse a preguntar convierte una regla en un muro y deja al cliente con una pantalla que no hace lo que pidió.
  **Aplicación futura:** Cuando una regla del proyecto contradiga una petición, mostrar la regla con su cita exacta, explicar el riesgo concreto y pedir decisión. Registrar la respuesta y su motivo en la especificación.

- **2026-10-02 — Un formulario no controlado no refleja lo que el servidor guardó:**
  **Contexto:** Al guardar un expediente, el chip de prioridad pasó a «urgente» pero el `<select>` seguía en «alta». Los campos de texto parecían correctos solo porque el usuario acababa de escribirlos. Recargar lo arreglaba, y por eso no era un fallo de guardado.
  **Aprendizaje:** React no toca el valor de un input no controlado tras un Server Action; solo los `<select>` revelan el desfase, porque React sí reaplica su `defaultValue`. La prueba de que un guardado funcionó no es el mensaje de éxito, es que lo que se ve a los dos lados del guardado cuente lo mismo. Y un campo de texto no demuestra nada: su contenido puede ser el del usuario.
  **Aplicación futura:** Después de toda escritura, comparar el estado derivado del servidor con el control. Si el formulario es no controlado, remontarlo con la versión del servidor (`updated_at`) como `key`.

- **2026-10-02 — Un id repetido rompe las etiquetas sin romper nada visible:**
  **Contexto:** La ficha de expediente pintaba el formulario y tres diálogos, y `notes` y `client_id` se repetían; en los listados, los filtros compartían id con el diálogo de alta. Nada se veía mal.
  **Aprendizaje:** Un `id` duplicado no produce un error visible: hace que cada `<label htmlFor>` de la página enfoque el primer control que encuentre, y ese puede ser el de otro formulario. El síntoma es «el clic en la etiqueta no hace nada», muy lejos de la causa.
  **Aplicación futura:** Cualquier página que monte más de un formulario necesita prefijar los ids. Añadir a la primitiva un `idPrefix` que cualifique el id sin tocar el `name` enviado, y comprobar ids duplicados en el DOM como puerta: es barato y detecta un fallo de accesibilidad entero.

- **2026-10-02 — Inventar un nombre de permiso no es restringir, es esconder:**
  **Contexto:** Expedientes desapareció del menú para todos porque el módulo exigía `cases:read`, un permiso que el proyecto no tiene: expedientes se autoriza por alcance (`read_all`, `read_assigned`, `read_published`).
  **Aprendizaje:** Una puerta construida con una llave que nadie tiene cierra igual que una cerradura rota, y ambas se ven igual. Un filtro de menú solo es correcto si la clave corresponde a algo que el backend comprueba de verdad.
  **Aplicación futura:** Antes de escribir un `permission` en el menú, confirmar que el nombre existe en la tabla de permisos. Si la autorización es por alcance y no por permiso, no poner permiso y dejar que la API filtre.

- **2026-10-02 — `MissingGreenlet` en `pre_ping` no es un bug del endpoint:**
  **Contexto:** Tras un `--force-recreate`, «Incorporar abogado» devolvió 500 con `sqlalchemy.exc.MissingGreenlet` dentro del ping de la conexión del pool. El mismo clic funcionó a la segunda, sin cambios de código.
  **Aprendizaje:** La traza apuntaba al pool y al dialecto, no a la lógica de negocio. Un 500 transitorio justo después de recrear contenedores es una conexión obsoleta, y buscar un fallo de código ahí cuesta mucho más que repetir la operación.
  **Aplicación futura:** Ante un 500 único e inmediato a un `recreate`, releer la traza buscando el dialecto o el pool antes que el endpoint, y repetir la operación una vez para separar infraestructura de código.

- **2026-09-30 — El patrón "permiso sin alcance" se repite por tercera vez:**
  **Contexto:** Agenda y hearings fallaron por un producto cartesiano. En evidencias, `get_visible_evidence` comprobaba visibilidad pero no alcance, y `/custody` no aplicaba ninguno. Un abogado sin expedientes asignados podía leer por UUID la evidencia de cualquier expediente.
  **Aprendizaje:** Un permiso controla *qué puede hacer* quien lo tiene. El alcance controla *sobre qué*. Con uno solo, cualquier persona de la firma lee cualquier registro adivinando su UUID.
  **Aplicación futura:** Cuando un endpoint lee por identificador, el alcance va dentro de la consulta y es parámetro obligatorio del método de servicio, nunca una decisión del endpoint. Si mypy no obliga a pasarlo, la fuga vuelve.

- **2026-09-30 — Una etiqueta MIME derivada de un ternario puede mentir:**
  **Contexto:** El derivado de una imagen con alfa se guardaba como PNG pero se etiquetaba `image/jpeg`, porque el MIME se calculaba con `"webp" if target == "WEBP" else "jpeg"`.
  **Aprendizaje:** Los mappings se escriben como tabla o función, no como cadena de condiciones. Un ternario con una sola condición especial trata todo lo demás como el caso por defecto.
  **Aplicación futura:** Para mapear valores a categorías, un diccionario explícito, y que un valor no contemplado sea visible en vez de silenciosamente incorrecto.

- **2026-09-30 — Detectar políglotos exige buscar en toda la cabecera:**
  **Contexto:** La detección de ZIP miraba solo los cuatro primeros bytes, así que un PDF con el directorio central del ZIP más adelante pasaba como PDF normal.
  **Aprendizaje:** El ataque clásico empieza como un archivo válido y lleva la segunda firma dentro. Buscar solo en el offset cero es buscar donde no hay nada interesante.
  **Aplicación futura:** Los marcadores embebidos se buscan en toda la ventana inspeccionada; los de arranque, solo al principio.

- **2026-09-30 — Un test que falla al construir el fixture tiene mal el fixture:**
  **Contexto:** `make_signed_pdf()` usaba un `ByteRange` sintético cuya aritmética no siempre cuadrava con el tamaño real del archivo.
  **Aprendizaje:** Cuando el fallo está en la construcción del dato de prueba y no en la aserción, el problema es el fixture. Debuggear la lógica de producción en ese caso es tiempo perdido.
  **Aplicación futura:** Si un test falla antes de alcanzar su primera aserción, revisar primero cómo se construyó el fixture.

- **2026-09-30 — Comprobar un límite con un solo valor no lo demuestra:**
  **Contexto:** Los tests de contratos de almacenamiento afirmaban `in (200, 404)` porque no tenía claro cuál era el valor correcto para un administrador. Resultó que `403` era lo que revelaba un test mal planteado.
  **Aprendizaje:** Una aserción que acepta dos resultados no verifica nada; solo documenta que no se sabe. Si el valor correcto no está claro, la prueba no está escrita.
  **Aplicación futura:** Antes de aceptar un rango, decidir cuál es el comportamiento correcto y afirmarlo. Si hay duda, es una pregunta de requisitos, no una banda de tolerancia.

- **2026-09-30 — Una subida exitosa no demuestra que los bytes llegaran:**
  **Contexto:** El camino de copia externa usaba `mc mirror`, que devuelve éxito si los datos salieron del proceso, no si llegaron íntegros. Además `minio/mc` no se puede descargar aquí, así que era un camino sin probar.
  **Aprendizaje:** Un respaldo remoto sin verificación por digest es una hipótesis sobre el estado de una red. Releer el objeto y comparar el hash cuesta el doble de E/S y convierte la copia en un hecho comprobable.
  **Aplicación futura:** Todo traslado de datos fuera del proceso debe releerse y verificarse. Si se ofrece un modo rápido, la salida debe declarar que es más débil.

- **2026-09-30 — `moto` en proceso no basta para probar transferencia:**
  **Contexto:** Los tests con `mock_aws` no ejercitan HTTP, firmado SigV4 ni paginación real. Lancé `moto.server` y ejecuté el CLI real contra él.
  **Aprendizaje:** El mismo motor puede correr en proceso como doble o como servidor. El modo servidor prueba el camino completo: cliente, red y respuesta.
  **Aplicación futura:** Para integraciones de red, ejecutar el flujo real contra el motor en modo servidor, aunque la suite siga usando el doble en proceso por velocidad.

- **2026-09-30 — Un escenario de prueba puede validar lo contrario de lo que cree:**
  **Contexto:** Inyecté corrupción remota y esperé que `push` la detectara, pero `push` reescribe el objeto antes de verificar, así que se sobrescribió la corrupción y dio verde.
  **Aprendizaje:** El camino de código bajo prueba decide qué puede fallar. `push` verifica lo que él mismo acaba de subir; para detectar corrupción posterior hay que usar `verify`.
  **Aplicación futura:** Antes de escribir un test que "debe fallar", comprobar que el punto de inyección está después del punto de verificación.

- **2026-09-30 — Verificar argumentos antes de tocar la red:**
  **Contexto:** `remote_backup` llamaba a `ensure_bucket()` antes de comprobar que hubiera una acción, así que una invocación vacía fallaba por red en vez de por uso.
  **Aprendizaje:** Validación primero, efectos después. En un CLI, el error más probable es el de invocación y debe reportarse sin efectos secundarios.
  **Aplicación futura:** Validar argumentos al principio de `run()`, antes de cualquier cliente o llamada externa.

- **2026-09-30 — Avisar o fallar, nunca fallar en silencio:**
  **Contexto:** El respaldo externo está apagado por defecto. Bloquear cada ejecución local llevaría a la gente a desactivar la comprobación.
  **Aprendizaje:** Una comprobación ignorable se desactiva; una que rompe el flujo se evade. Lo correcto es un aviso ruidoso por defecto y un modo estricto opcional.
  **Aplicación futura:** Controles de seguridad con un interruptor explícito que avise tres veces antes de dejar pasar.

- **2026-09-30 — Compose expande variables en el host, no en el contenedor:**
  **Contexto:** `compose.test.yaml` fijaba `PATH: "/opt/venv/bin:${PATH}"`. Compose lo expande con el PATH del host; en Windows ese valor no es un PATH POSIX, así que reemplazaba el del contenedor y ocultaba `/usr/bin`, rompiendo `pg_dump`.
  **Aprendizaje:** en un fichero Compose, `${PATH}` es del host. Sobrescribir variables del sistema del contenedor desde Compose rompe herramientas de forma silenciosa.
  **Aplicación futura:** No tocar `PATH` en Compose; la imagen ya lo define con `ENV`. Si una herramienta nativa desaparece, comprobar primero el PATH efectivo del contenedor.

- **2026-09-30 — Las herramientas nativas no entienden los drivers de SQLAlchemy:**
  **Contexto:** `pg_dump --dbname postgresql+asyncpg://...` ignoraba el host y caía al socket local, fallando con "No such file or directory".
  **Aprendizaje:** `pg_dump` y `pg_restore` no parsean `+asyncpg`. Hay que renderizar la URL con el driver `postgresql` antes de pasársela.
  **Aplicación futura:** Normalizar el driver antes de invocar una herramienta nativa con una URL construida por SQLAlchemy.

- **2026-09-30 — Un cliente pg_dump antiguo no puede volcar un servidor nuevo:**
  **Contexto:** El servidor es PostgreSQL 17 y el slim traía el cliente 15, que se niega a trabajar. Añadir el repositorio PGDG falló por dependencias, pero Debian trixie ya traía el cliente 17.
  **Aprendizaje:** Cliente y servidor PostgreSQL deben coincidir. Antes de añadir un repositorio APT externo, comprobar si la imagen base ya trae la versión correcta.
  **Aplicación futura:** Verificar la versión del cliente con `pg_dump --version` dentro del Dockerfile, para que el fallo aparezca al construir y no en producción.

- **2026-09-30 — Un respaldo sin restaurar es una hipótesis:**
  **Contexto:** La verificación crea una base de datos temporal, restaura, comprueba tablas y recuentos, y la borra.
  **Aprendizaje:** El tamaño del archivo y el código de salida de `pg_dump` no prueban nada. Lo único que prueba un respaldo es restaurarlo y preguntarle a la copia qué contiene.
  **Aplicación futura:** Todo respaldo generado sin verificación automática debe marcarse como no verificado en la salida y en la documentación.

- **2026-09-30 — Verificar integridad y verificar el respaldo son controles distintos:**
  **Contexto:** Se confundían al planificarlos. Uno pregunta si la base se puede restaurar; el otro, si los bytes siguen coincidiendo con su hash.
  **Aprendizaje:** Un volcado restaurable puede apuntar a objetos corruptos, y unos objetos íntegros no sirven si no se pueden emparejar con filas válidas. Cada control responde a una pregunta distinta y ninguno sustituye al otro.
  **Aplicación futura:** Documentarlos por separado y encadenarlos: restaurar, y después verificar integridad sobre el par restaurado.

- **2026-09-30 — `from_attributes` no se propaga a modelos anidados:**
  **Contexto:** `IntegrityScanResponse` validaba bien pero fallaba al convertir la lista de `IntegrityFinding`.
  **Aprendizaje:** En Pydantic v2 el `model_config` se aplica al modelo donde se declara, no a los tipos anidados. Un esquema con relación anidada necesita `from_attributes` en cada nivel.
  **Aplicación futura:** Al anidar modelos ORM en schemas, declarar el config en cada uno o usar un validador explícito.

- **2026-09-30 — Un filtro de alcance sobre otra tabla puede ser un no-op:**
  **Contexto:** `scope_filter` generaba predicados sobre `cases` que se aplicaban a consultas de `calendar_events` y `hearings` sin unir `cases`. SQLAlchemy lo convirtió en un producto cartesiano, así que la condición se cumplía si cualquier caso coincidía. Un abogado veía los eventos de expedientes ajenos.
  **Aprendizaje:** un predicado que referencia una tabla ausente del FROM se convierte en cross join y relaja la restricción hasta volverla inofensiva. El aviso `SAWarning: cartesian product` lo delata, y 211 tests en verde no lo detectaron porque ninguno afirmaba el caso negativo.
  **Aplicación futura:** Traducir siempre el predicado al `case_id` de la entidad hija con `case_scoped()`. Añadir un test que afirme que un elemento de un expediente no asignado está oculto, no solo que los propios son visibles.

- **2026-09-30 — Glacier rompe la garantía de disponibilidad:**
  **Contexto:** El tier de archivo por defecto era `GLACIER`. Tras la copia, el objeto quedaba ilegible hasta restaurar y `read` fallaba con `InvalidObjectState`.
  **Aprendizaje:** `GLACIER`, `DEEP_ARCHIVE` y `GLACIER_IR` no son "más baratos": son "no disponibles durante horas o días". En un sistema donde cualquier versión debe poder descargarse, son inaceptables.
  **Aplicación futura:** Elegir `STANDARD_IA` como tier de archivo y rechazar en el constructor las clases que requieran restauración.

- **2026-09-30 — Un test que no puede fallar no prueba nada:**
  **Contexto:** Escribí tests de privacidad del bucket y de validación de `ContentMD5` usando `moto`, que no aplica IAM ni valida MD5. Los tests pasaban sin verificar nada.
  **Aprendizaje:** Cuando el doble no implementa el comportamiento, el test pasa por la razón equivocada. Un test verde sobre una emulación incompleta es peor que no tener test, porque crea confianza falsa.
  **Aplicación futura:** Declarar en el docstring del módulo qué no cubre el doble, y afirmar la presencia del mecanismo (por ejemplo, que se envía `ContentMD5`) en lugar de su efecto en el servidor.

- **2026-09-30 — Las APIs de terceros envejecen dentro de tu código:**
  **Contexto:** `from botocore.s3 import inject_host` funcionaba en documentación antigua y ahora lanza `ModuleNotFoundError`; `inject_host` ya no existe en boto3 moderno.
  **Aprendizaje:** los workarounds de hace años sobreviven en blogs más que en las librerías. Un import perezoso dentro de un método puede llevar años sin ejecutarse en ningún camino de prueba.
  **Aplicación futura:** Ejecutar el constructor de cada integración al menos una vez en un test. Si una línea no se ejecuta, no sabes si sigue siendo válida.

- **2026-09-30 — Cambiar una columna de modelo no la mueve:**
  **Contexto:** Cambiar `STORAGE_BACKEND` de `local` a `s3` no reubica ningún archivo; la `storage_key` guardada sigue apuntando al disco local.
  **Aprendizaje:** Un cambio de configuración de infraestructura solo es neutro si no hay datos que haya que trasladar. Si los hay, hace falta una migración explícita que verifique la integridad antes de repuntar cada fila.
  **Aplicación futura:** Inventariar qué estado vivo depende de la variable que se cambia y escribir la CLI de migración con dry-run e idempotencia antes de tocar el entorno.

- **2026-09-30 — El registro de pruebas puede estar limitado:**
  **Contexto:** `minio/minio` y `minio/mc` no se pueden descargar: el registro solo permite imágenes `library/*`. `alpine` y `postgres` sí.
  **Aprendizaje:** Un `pull access denied` puede significar política del registro y no credenciales. Antes de rediseñar la infraestructura, hay que aislar si fallan todas las imágenes no oficiales o solo una.
  **Aplicación futura:** Probar una imagen conocida como `alpine` para distinguir restricción del registro de problema de credenciales, y sustituir el contenedor por una librería en proceso cuando sea posible.

- **2026-09-30 — Sesiones ya cargadas devuelven grafos obsoletos:**
  **Contexto:** Tras crear una versión documental, `document.versions` seguía vacío en la respuesta siguiente porque el objeto ya estaba en el mapa de identidad.
  **Aprendizaje:** Un `select()` con `selectinload` no refresca una colección previamente cargada en la misma sesión; hace falta `.execution_options(populate_existing=True)` o `session.refresh()`.
  **Aplicación futura:** Cuando un endpoint lea una relación que otro endpoint del mismo test pudo modificar, usar `populate_existing=True` de forma explícita.

- **2026-09-30 — La CLI de bootstrap tenía un bug de greenlet:**
  **Contexto:** `if role not in user.roles` falló con `MissingGreenlet` al crear el primer administrador.
  **Aprendizaje:** Comprobar pertenencia a una colección cargada de forma perezosa provoca IO implícito. La comprobación debe hacerse con una consulta explícita sobre la tabla de asociación.
  **Aplicación futura:** En CLI y servicios, validar asociaciones many-to-many con `select` sobre la tabla pivote, nunca con `in` sobre la colección.

- **2026-09-30 — Probar código que abre su propia sesión:**
  **Contexto:** Los tests del CLI fallaban porque usaban el motor global, cruzada con otro event loop, y además filtraban datos reales a otros tests.
  **Aprendizaje:** La sesión del test debe construirse sobre la misma `AsyncConnection` externa; `session.get_bind()` devuelve la fachada síncrona, así que hay que exponer la conexión explícitamente en un fixture.
  **Aplicación futura:** Exponer fixtures `test_engine`, `test_connection` y `session_factory`, e inyectar la fábrica en cualquier componente que abra su propia sesión.

- **2026-09-30 — Blacklists de contenido producen falsos positivos:**
  **Contexto:** Bloquear archivos que empiezan por `b"from "` o `b"import "` para impedir scripts Python rechazaba texto jurídico legítimo.
  **Aprendizaje:** Un patrón de bloqueo debe ser inequívoco. El shebang `#!` y las firmas `MZ`/`\x7fELF` no admiten falsos positivos; las palabras del lenguaje no.
  **Aplicación futura:** Al filtrar uploads, preferir firmas binarias o delimitadores estructurales antes que palabras clave del contenido.

- **2026-09-30 — Volumen Docker y usuario no root:**
  **Contexto:** El backend corre como UID 10001 y el volumen de documentos se creaba propiedad de root, con lo que no podía escribir.
  **Aprendizaje:** Un volumen nombrado hereda la propiedad del directorio existente en la imagen; si el directorio no se crea, el volumen nace como root.
  **Aplicación futura:** Crear y hacer `chown` de los directorios de datos en el Dockerfile antes de declarar `USER`.

- **2026-09-30 — Un endpoint de descarga debe devolver bytes:**
  **Contexto:** La descarga devolvía el contenido en base64 dentro de JSON, sin `Content-Disposition` ni cabeceras de integridad.
  **Aprendizaje:** Un archivo se sirve con `Response` binario, `Content-Disposition: attachment`, nombre saneado, `nosniff` y el hash en cabecera. Devolver base64 en JSON rompe la semántica HTTP y obliga al cliente a reconstruir el archivo.
  **Aplicación futura:** Unificar el patrón para cualquier descarga y añadir tests que verifiquen bytes y cabeceras.

- **2026-09-30 — Aislamiento de tests async en Docker:**
  **Contexto:** Los tests reutilizaban datos, ejecutaban una copia obsoleta del código y el pool async cruzaba event loops.
  **Aprendizaje:** El volumen debe coincidir con `WORKDIR`; PostgreSQL de tests debe ser efímero; cada test async debe usar una transacción revertible y un engine `NullPool` creado en su propio loop.
  **Aplicación futura:** Mantener `compose.test.yaml` en `/build`, ejecutar migraciones antes de pytest y no compartir pools async entre loops de pytest.

- **2026-09-30 — Overrides de dependencias FastAPI:**
  **Contexto:** Health y auth importaban funciones `get_session` distintas; sobrescribir una no afectaba la otra.
  **Aprendizaje:** `app.dependency_overrides` requiere exactamente el mismo objeto función usado en `Depends`.
  **Aplicación futura:** Importar y sobrescribir explícitamente cada dependencia de sesión o consolidarlas en una sola función canónica.

- **2026-09-30 — Savepoints para probar código que hace commit:**
  **Contexto:** Los endpoints hacen `session.commit()`, lo que liberaba la transacción externa del test.
  **Aprendizaje:** `AsyncSession(bind=connection, join_transaction_mode="create_savepoint")` mantiene los commits de la aplicación dentro de la transacción del test.
  **Aplicación futura:** Usar siempre `create_savepoint` en fixtures con transacción externa.

- **2026-09-30 — Cargas perezosas en contexto async:**
  **Contexto:** Un validador Pydantic accedía a `user.roles` y falló con `MissingGreenlet`.
  **Aprendizaje:** Cualquier acceso a relaciones ORM debe ocurrir dentro de una corrutina con `greenlet_spawn`; en validadores síncronos hay que garantizar la carga previa con `selectinload`.
  **Aplicación futura:** Cargar explícitamente los grafos de autorización en `get_current_user` y en los servicios administrativos.

- **2026-09-30 — Fallos silenciosos ocultan bugs:**
  **Contexto:** El middleware de auditoría fallaba al insertar `entity_id` no-UUID y un `except: pass` ocultaba el error.
  **Aprendizaje:** Un `except` naked en ruta crítica debe registrar el error; el fallo se manifiesta como "no se auditó nada".
  **Aplicación futura:** Sustituir `except: pass` por logging, y añadir tests que affirmen la escritura real.

- **2026-09-30 — Verificación HTTP real encuentra defects que los tests no:**
  **Contexto:** `docker compose up --force-recreate` sin `--build` reutilizó la imagen anterior, y `LogoutRequest` exigía `refresh_token` aunque era opcional.
  **Aprendizaje:** Verificar el flujo por HTTP tras cada despliegue local y reconstruir siempre con `--build`.
  **Aplicación futura:** Añadir un smoke test HTTP al checklist de cierre de fase.

- **2026-09-30 — Un middleware no debe consumir el cuerpo de la petición:**
  **Contexto:** El middleware de auditoría leía `request.body()` y en producción ocasionaba `400 There was an error parsing the body` en el manejador.
  **Aprendizaje:** En `BaseHTTPMiddleware`, el `Request` aguas abajo lee de `receive`; si el middleware consumió el stream, el cuerpo puede llegar vacío.
  **Aplicación futura:** No leer el cuerpo en middlewares; registrar el detalle en la capa de servicio.

- **2026-09-30 — Pydantic no coacciona UUID a str:**
  **Contexto:** `AuditLogResponse.entity_id` estaba declarado `str` y recibía `UUID`, provocando 500 al listar auditoría.
  **Aprendizaje:** Alinear los tipos de los esquemas con las columnas reales; los `model_config from_attributes` no convierten UUID a str.
  **Aplicación futura:** Al serializar modelos, copiar el tipo exacto de la columna y cubrirlo con un test de API.

- **2026-09-30 — Errores de validación no serializables:**
  **Contexto:** `exc.errors()` incluye la excepción original en `ctx`, y `JSONResponse` lanzaba `TypeError` convirtiendo un 422 en 500.
  **Aprendizaje:** Sanitizar `ctx` a texto antes de construir la respuesta de error.
  **Aplicación futura:** Mantener `safe_validation_errors` y añadir validadores con `ValueError` en los esquemas.

- **2026-09-30 — PowerShell y los acentos:**
  **Contexto:** `Invoke-RestMethod` con `-Body` de cadena y acentos enviaba ANSI y la API respondía 400.
  **Aprendizaje:** Para JSON con no-ASCII en PowerShell 5.1 hay que enviar bytes UTF-8 explícitos.
  **Aplicación futura:** Usar `Invoke-RestMethod` con cadenas ASCII en verificaciones rápidas o codificar a UTF-8.

- **2026-10-01 — Un permiso en la matriz de roles que no existe en el catálogo no lo siembra nadie:**
  **Contexto:** Fase 8 añadió `messages:*` a la matriz de roles pero olvidó añadir `MESSAGE_PERMISSIONS` a `get_permission_definitions()`. Las 38 fixtures fallaron con `KeyError: 'messages:read'`.
  **Aprendizaje:** La matriz de roles y el catálogo de definiciones son dos listas que deben crecer juntas. El síntoma es desconcertante: `KeyError` en una fixture, no un error de migraciones, porque la migración de permisos itera el mismo catálogo y no inserta nada sin avisar.
  **Aplicación futura:** El test `test_every_role_permission_exists_in_the_catalog` compara ambas listas. Mantenerlo y añadir un permiso nuevo solo si el test pasa.

- **2026-10-01 — `server_default=func.now()` no ordena un chat:**
  **Contexto:** `messages.sent_at` usaba solo `server_default=func.now()`. En PostgreSQL `now()` es la marca de tiempo de la transacción, así que tres mensajes escritos en la misma transacción compartían instante y el hilo salía en orden arbitrario.
  **Aprendizaje:** En PostgreSQL, `now()` es tiempo de transacción y `clock_timestamp()` es tiempo real. Para ordenación dentro de una misma transacción hace falta un valor evaluado en Python.
  **Aplicación futura:** Toda columna usada en `ORDER BY` que pueda tener empates dentro de una transacción necesita `default=` en Python además de `server_default=`, y un desempate explícito.

- **2026-10-01 — Recorrer una relación perezosa lanza `MissingGreenlet`:**
  **Contexto:** `_add_participant` iteraba `conversation.participants` y luego hacía `append`, lo que dispara una carga perezosa fuera de contexto await.
  **Aprendizaje:** Con `async_sessionmaker`, cualquier acceso a atributo que pueda requerir IO debe ocurrir dentro de una función `async` awaited, y aun así una colección no cargada falla. La solución es `session.refresh(obj, ["relacion"])`.
  **Aplicación futura:** Ante `MissingGreenlet`, no envolver en `greenlet_spawn`: consultar la base o usar `refresh` con la lista de atributos.

- **2026-10-01 — `result.all()` devuelve `Row`, no la entidad:**
  **Contexto:** `_message_response` hacía `MessageAttachmentResponse.model_validate(item)` sobre `result.all()` de un `select(MessageAttachment)`, provocando `ValidationError` en seis campos.
  **Aprendizaje:** `execute(...).all()` entrega filas con acceso por etiqueta; `.scalars().all()` entrega entidades. Con `select(Entidad)` se quiere `.scalars()`.
  **Aplicación futura:** Revisar cualquier `model_validate` alimentado por el resultado de un `select`.

- **2026-10-01 — Los permisos de borrado deben llamarse `archive`:**
  **Contexto:** `messages:delete` contradecía el invariante ya testeado de que abogado, asistente y cliente no poseen ningún permiso `*:delete`.
  **Aprendizaje:** El borrado de mensajes es lógico, así que el nombre correcto es `archive`, igual que `evidences:archive`. Nombrar la acción como `delete` choca con la política del proyecto aunque la implementación sea suave.
  **Aplicación futura:** Elegir el nombre del permiso según la política, no según el verbo del método.

- **2026-10-01 — Filtrar fuera de un subquery cuenta el producto cartesiano:**
  **Contexto:** `_count` hacía `select(func.count()).select_from(statement.subquery())` y luego aplicaba el filtro en el `COUNT` exterior. Como el filtro referencia una tabla ya ausente del `FROM`, SQLAlchemy la reincorporaba y el resultado era subconsulta × tabla completa: contar 2 expedientes devolvía 4, y un `kpis()` marcaba 18.
  **Aprendizaje:** En un agregado sobre subquery, **todos** los filtros van dentro de la consulta interna. Es la misma clase de fallo que ya documenta `case_scoped`, y por eso aquel comentario existe.
  **Aplicación futura:** Ante un `count` o `sum` que devuelva un múltiplo del valor esperado, sospechar de un filtro aplicado después del `subquery()` y comprobar el SQL generado.

- **2026-10-01 — Un panel se deriva del alcance, no del rol:**
  **Contexto:** Fase 9 podía haberse implementado como un endpoint por rol, como sugiere literalmente «dashboards por rol».
  **Aprendizaje:** Un usuario puede tener varios roles, y el alcance es lo que el resto de la aplicación ya aplica. Un endpoint por rol duplica consultas y crea un sitio donde el alcance se olvide. El endpoint único que varía por alcance tiene la misma capacidad de presentación y una sola puerta por donde filtrar.
  **Aplicación futura:** Ante requisitos de «una vista por rol», comprobar primero si lo que realmente cambia es el alcance.

- **2026-10-01 — Un permiso de agregado no es un permiso de datos:**
  **Contexto:** `dashboard:read` se concedió a los cuatro roles, incluido el cliente.
  **Aprendizaje:** Si el agregado solo cuenta filas que el llamante ya puede leer, negar el endpoint no protege nada: solo impide ver un cero honesto. El cliente sin expedientes ve ceros, y eso es más correcto que un 403.
  **Aplicación futura:** Al añadir un permiso de solo lectura sobre datos ya visibles, incluir a todos los roles que ya pueden ver esos datos.

- **2026-10-01 — Comparar el catálogo contra la matriz no demuestra nada sobre la base de datos:**
  **Contexto:** Los permisos `settings:*` y `metrics:read` se añadieron al catálogo y a la matriz, con su test de regresión en verde, y **ninguna migración los sembraba**. En producción cada endpoint habría respondido 403. La fixture `rbac_catalog` siembra las filas que faltan, así que los tests passaban mientras el despliegue estaba roto.
  **Aprendizaje:** Un permiso puede ser perfectamente coherente en el código y no existir en la base. La comprobación que importa compara el catálogo con las **filas sembradas**, y no debe apoyarse en la fixture que las siembra. Es el mismo fallo de Fase 8 por segunda vez, y la causa fue medir el invariante equivocado.
  **Aplicación futura:** Mantener `test_every_catalog_permission_reaches_the_database`, sin dependencia de `rbac_catalog`. Antes de dar por buena una fase con permisos nuevos, ejecutar la migración y comprobar los permisos contra la base.

- **2026-10-01 — `record_changes` omite el campo que no cambió:**
  **Contexto:** Borrar un ajuste pasaba `after={}`, y como `record_changes` salta todo campo ausente de `after`, no se registraba ninguna entrada: el ajuste desaparecía sin rastro.
  **Aprendizaje:** Para registrar una eliminación hay que pasar el valor ausente de cada campo, no un `after` vacío.
  **Aplicación futura:** Al auditar un borrado, comprobar que la función de registro produce entrada antes de darla por buena.

- **2026-10-01 — Afirmar que un payload está vacío es más débil que afirmar que no trae filas:**
  **Contexto:** `test_a_user_without_permissions_reads_nothing` enumeraba las formas de sobre de respuesta (`[]`, `{}`) y falló con un sobre paginado `{"items": [], "total": 0}`.
  **Aprendizaje:** Las entidades se direccionan por UUID, así que **la presencia de una UUID en cualquier parte del payload significa que volvió una fila**. Esa aserción no depende de la forma de la respuesta y no se puede esquivar.
  **Aplicación futura:** En tests de aislamiento, preferir properties estructurales del payload a comparaciones de forma.

- **2026-10-02 — En Next.js el refresco de sesión va en `proxy.ts`, nunca en el render:**
  **Contexto:** El token de acceso dura 30 minutos y el de refresco 7 días. El primer intento de renovar la sesión lo hizo `apiFetch`, dentro del render. El log mostró `POST /auth/refresh 200` seguido de un 401: la cookie escrita no entraba en el jar del mismo render, el reintento usaba el token caducado, y como el backend **rota** el token de refresco, el segundo intento destruía la sesión recién renovada.
  **Aprendizaje:** Un Server Component no puede escribir cookies. Solo el middleware, los Route Handlers y las Server Actions pueden, y solo allí la cookie nueva es visible para el código siguiente. `proxy.ts` es el sitio correcto para renovar antes de renderizar.
  **Aplicación futura:** Cualquier lógica de sesión en Next 16 va en `proxy.ts`. Y un `refreshSession()` en un Route Handler debe **devolver** el token nuevo en vez de hacer que el llamante lo relea del jar.

- **2026-10-02 — «Sin sesión» y «el servicio falló» no son la misma cosa:**
  **Contexto:** El panel redirigía a `/login` cuando el dashboard fallaba por cualquier motivo, incluidos 429 y tiempos de espera. Un 429 produjo un bucle infinito: `/portal` → `/login` → `/portal`.
  **Aprendizaje:** El error de una página debe propagar su naturaleza. Redirigir solo cuando no hay sesión, y mostrar el fallo del servicio como lo que es. Adjudicar mal un error convierte un incidente en un laberinto.
  **Aplicación futura:** En cualquier guard de sesión, separar `unauthenticated` de `unavailable` antes de decidir la navegación.

- **2026-10-02 — Una cifra de ahorro no se recorta a cero:**
  **Contexto:** Cuando un derivado pesa más que el original, la tabla y el cajón recortaban el porcentaje con `Math.max(0, …)` y mostraban `0,0 %` como si hubiera habido ahorro.
  **Aprendizaje:** Un negativo no es un cero. En un documento sobre evidencia, decir «0 % de ahorro» cuando el archivo creció es una afirmación falsa, y alguien podría tomar una decisión de almacenamiento a partir de ella.
  **Aplicación futura:** Distinguir siempre «sin medir», «sin datos», «sin cambio» y «mayor». Una raya nunca es un cero.

- **2026-10-02 — Un panel de integridad no puede afirmar lo que no verificó:**
  **Contexto:** La caja de SHA-256 del cajón de custodia se pintaba en verde con el rótulo «registrado» incluso para una evidencia en cuarentena, que no tiene original ni hash.
  **Aprendizaje:** El color y el rótulo de un panel de integridad son afirmaciones. Cuando no hay nada que verificar, el panel debe decirlo en voz alta, no insinuar que la verificación fue correcta.
  **Aplicación futura:** Los estados vacíos de un panel de verificación necesitan un tratamiento visual propio, no la reutilización del estado positivo.

- **2026-10-02 — `overflow-x` solo hace que el otro eje compute a `auto`:**
  **Contexto:** La navegación del portal mostraba una barra de scroll vertical en el borde derecho. El subrayado de la pestaña activa estaba posicionado un píxel por debajo del contenedor, y eso desbordaba el eje vertical ya convertido en `auto`.
  **Aprendizaje:** Especificar el segundo eje siempre que se restrinja el primero, o el navegador asumirá `auto` y cualquier desbordamiento de un píxel pinta una barra.
  **Aplicación futura:** `overflow-x-*` sin su compañero `overflow-y-*` es un error latente, aunque hoy no desborde nada.

- **2026-10-02 — Las etapas de un proceso que no se observan no se animan:**
  **Contexto:** `MASTER_PROMPT` 39 pide seis pasos de subida, pero la API es síncrona: un `POST` valida, comprueba seguridad, almacena, optimiza y genera la vista previa, y contesta. No hay forma de observar dos de esos pasos por separado.
  **Aprendizaje:** Animar una barra de progreso que no informa de nada es peor que no animarla: comunica una precisión que el sistema no tiene. La regla que funciona es hacer avanzar una etapa solo cuando hay un motivo para creer que ocurrió — en este caso, el contador de bytes, la respuesta del servidor y la presencia real de derivados.
  **Aplicación futura:** Al implementar un pipeline visual sobre una API síncrona, documentar qué etapas son observables y cuáles se agrupan, en lugar de fingir granularidad.

- **2026-10-02 — Un formulario que acepta datos personales debe poder mentir por omisión:**
  **Contexto:** La web pública hereda del diseño de referencia un formulario de consulta con nombre, teléfono, correo y descripción de un problema legal. No existe endpoint de contacto en el backend. La tentación era mostrar «Gracias, le contactaremos».
  **Aprendizaje:** Un mensaje de éxito falso aquí es lo más dañino que puede llevar la página: alguien comparte un problema legal y queda con la impresión de que el despacho lo sabe. La regla general: **el éxito se muestra solo cuando el sistema lo confirma**, y si la integración no existe, el hueco se declara antes de que la persona escriba, no después de que pulse.
  **Aplicación futura:** En cualquier formulario de captación, decidir primero dónde acaban los datos. Si no hay destino, decirlo en el formulario, no convertirlo en un buzón negro.

- **2026-10-02 — Un BOM UTF-8 al principio de un CSS descarta la primera regla:**
  **Contexto:** Al reconstruir `public-site.css`, el archivo quedó con BOM. El analizador leyó `BOM + primer comentario + primer selector` como **un único selector**, así que la regla `.wrap` desapareció entera y el minificador emitió un `?` suelto delante. Sin error ni aviso: la página simplemente dejó de estar contenida y se veía más ancha.
  **Aprendizaje:** El síntoma —«mi CSS no se aplica pero el archivo está bien»— se detecta midiendo `getComputedStyle`, no mirando la captura. Y `CSS.supports` devuelve `true` para una declaración que el navegador sí acepta en línea: la declaración era válida, lo que estaba mal era el selector.
  **Aplicación futura:** Escribir CSS como UTF-8 **sin BOM**. Si una regla no se aplica, inspeccionar el CSS servido en busca de caracteres raros delante del selector antes que culpar a la especificidad.

- **2026-10-02 — Un truncado se recupera del build, no de la memoria:**
  **Contexto:** Un script de PowerShell buscó un patrón que también aparecía en el comentario que acababa de escribir, y truncó `public-site.css` de 1000 líneas a 24.
  **Aprendizaje:** El CSS compilado del último build correcto (`app/.next/static/chunks/*.css`) conserva **todas las reglas**, aunque no los comentarios. Es la fuente de recuperación. Perder los comentarios duele menos que perder las reglas, y las reglas se pueden recuperar.
  **Aplicación futura:** Antes de un scripted edit sobre un archivo con contenido duplicado, anclar el patrón a algo único o comprobar el número de líneas antes y después.

- **2026-10-02 — Menos escalones, no más escalones:**
  **Contexto:** La web pasó de un contenedor fijo de 1200 px a cinco tramos (1200/1380/1560/2000/2360) más un juego de overrides que agrandaba el texto por encima de 2200 px. El resultado fue peor que el original.
  **Aprendizaje:** Cada breakpoint es un lugar donde el diseño puede romperse de una forma distinta, y escalonar la medida **y** el texto produce saltos, no una escala continua. `width: 100%; max-width: 1560px` hace todo el trabajo en una línea.
  **Aplicación futura:** Cuando una medida tenga que crecer, que crezca con una fórmula fluida y se detenga. Reservar los tramos para cambios de **composición**, que sí son discretos por naturaleza.

- **2026-10-02 — `backdrop-filter` crea un bloque contenedor:**
  **Contexto:** El velo del menú móvil se puso dentro de la cabecera, que lleva `backdrop-filter: blur()`. No atenuaba la página y no recibía el toque de cierre.
  **Aprendizaje:** Un elemento con `filter`, `backdrop-filter`, `transform`, `perspective` o `will-change` se convierte en **bloque contenedor de sus descendientes `position: fixed`**. El `inset: 0` del velo se resolvía contra los 91 px de la cabecera en lugar del viewport: cubría una banda, quedaba detrás por el `z-index` y no era pulsable. La regla general: un `position: fixed` que deba cubrir la ventana va en un hermano del elemento con filtro, nunca dentro.
  **Aplicación futura:** Antes de anidar un overlay fijo dentro de un componente, comprobar si ese componente tiene filtro, transform o will-change. Es un fallo silencioso: el elemento tiene el tamaño correcto en el DOM y no se ve.

- **2026-10-02 — Un `@media` colocado antes de la regla que quiere anular no hace nada:**
  **Contexto:** Los overrides de tipografía para pantallas de 2200 px y 3000 px se escribieron junto a las reglas del contenedor, más arriba en la misma hoja. El titular se quedó en 65 px en una TV 4K mientras el contenedor crecía a 2360 px.
  **Aprendizaje:** A igual especificidad gana la **última** declaración, y un `@media` no cambia la especificidad: solo la condición. Puesto antes de la regla base, se ignora sin error ni aviso. Es el mismo mecanismo por el que `.site-display` gana al `color` de su tarjeta padre.
  **Aplicación futura:** Los overrides de una escala fluida van **al final** de la hoja, con el motivo escrito al lado. Y cuando algo no aplica, sospechar del orden antes que de la especificidad.

- **2026-10-02 — «No desborda» y «se ve bien» son preguntas distintas:**
  **Contexto:** La web pública no tenía desbordamiento horizontal en ningún ancho —verificado— y aun así a 1900 px se veía como una cinta de 1200 px en 345 px de marfil vacío, y en un monitor grande el texto se quedaba pequeño porque todos los `clamp()` topaban a 1440.
  **Aprendizaje:** `scrollWidth === clientWidth` no dice nada de la composición. La medida de la caja fija fue el defecto real: contenía 1200 px dentro de una ventana de 1900. Y una escala fluida con techo es una escala que deja de responder a la pantalla.
  **Aplicación futura:** Barrido de anchos reales con **medición**, no inspección visual: celular, tablet, portátil, escritorio, monitor y TV. Y medir también cuánto ocupa el contenido del ancho disponible, no solo si desborda.

- **2026-10-02 — La verificación de un atributo no es la verificación del efecto:**
  **Contexto:** El menú móvil estaba dado por bueno porque `aria-expanded` pasaba a `true`. No lo estaba: faltaba comprobar que el panel se veía.
  **Aprendizaje:** `aria-expanded` lo actualiza React aunque el panel siga invisible. Un atributo de accesibilidad describe la intención del componente, no su resultado visible. Durante esta sesión el mismo menú dio falsa alarma dos veces por muestrear `opacity` a mitad de una transición de 180 ms en un render headless lento: la opacidad llegaba a 1 a los 1200 ms.
  **Aplicación futura:** Comprobar el **efecto** además del atributo: opacidad y visibilidad después de que la transición termine, y una captura. Y en headless, muestrear en el tiempo antes de acusar a un bug de maquetación.

- **2026-10-02 — Dos paletas para dos audiencias, no un error:**
  **Contexto:** El portal autenticado usa papel, tinta y lacre; la web pública usa azul petróleo, dorado y marfil. Podrían haberse forzado a una sola escala.
  **Aprendizaje:** La superficie autenticada es un documento en el que un abogado trabaja; la pública es una declaración hacia alguien que aún no ha decidido fiarse. Forzar una paleta común habría hecho que una de las dos dejara de decir lo que dice. Lo que sí debe ser común es la tipografía, y lo es.
  **Aplicación futura:** Antes de unificar sistemas de color entre superficies, comprobar si la diferencia es de uso y no de descuido. Si lo es, documentarlo en lugar de aplanarlo.

- **2026-10-02 — Un `useState` cuyo inicializador lee el entorno anula su propio efecto:**
  **Contexto:** El revelado al desplazar no funcionaba. El inicializador diferido hacía `typeof IntersectionObserver === "undefined"`, que vale `true` en el servidor y `false` en el cliente. React adopta el valor del servidor al hidratar, así que los 50 bloques salían visibles desde el primer pintado y el `IntersectionObserver` no tenía nada que observar.
  **Aprendizaje:** Un inicializador que depende del entorno produce un valor distinto en servidor y cliente, y la hidratación **gana el del servidor sin avisar**. No hay error ni aviso: el efecto simplemente nunca hace nada. Se detectó midiendo el comportamiento —cuántos elementos seguían esperando tras un desplazamiento completo: cero de cincuenta— y no leyendo el código.
  **Aplicación futura:** El estado de presentación que depende del entorno va en el CSS y lo activa una marca en el documento, y el componente solo añade una clase. Además, `dangerouslySetInnerHTML` en `<html>` inyecta **hijos**, no atributos.

- **2026-10-02 — Un `background` en línea borra todas las capas del CSS:**
  **Contexto:** Los huecos reservados del equipo perdían la trama diagonal porque el degradado en línea sustituía el `background` completo.
  **Aprendizaje:** El atajo `background` reemplaza cada capa, incluidas las que el CSS compone. Un matiz por variable es un matiz; un `background` en línea es una anulación.
  **Aplicación futura:** Pasar colores personalised por propiedades personalizadas y componer el fondo en el CSS.

- **2026-10-03 — Una animación con `fill-mode: both` sigue creando bloque contenedor cuando su último cuadro dice `transform: none`:**
  **Contexto:** El cajón de detalle de Documentos se abría como una banda del alto de una `<tr>` en lugar de cubrir la pantalla, con `getComputedStyle` informando `position: fixed` e `inset: 0px` y el rectángulo midiendo 1094×76 justo donde estaba la fila.
  **Aprendizaje:** Es el mismo fallo que `backdrop-filter` ya había enseñado —un elemento con transform es el bloque contenedor de sus `position: fixed` descendientes— pero la lectura de código miente: el keyframe `to { transform: none }` no produce `none` mientras la animación rellena, produce `matrix(1, 0, 0, 1, 0, 0)`, que sigue siendo una transformación. Por eso el error no aparece en el CSS, aparece en el rectángulo. Se midió con `getBoundingClientRect()` sobre el diálogo, no mirando la captura.
  **Aplicación futura:** Un overlay fijo que abre desde dentro de una fila, una tarjeta o cualquier nodo que se anima va **fuera** de esa rama del DOM (`createPortal`), no arreglado con `z-index`. Y la prueba de un overlay es su rectángulo contra `innerWidth`/`innerHeight`, no su `position` calculado.

- **2026-10-03 — Portal hacia `body` y una hoja sin capas se estrellan:**
  **Contexto:** Al portallar el cajón a `document.body`, `position: fixed` dejó de funcionar: el mismo elemento pasó de `fixed` a `relative` y acabó al final del flujo, debajo del viewport.
  **Aprendizaje:** `globals.css` tiene `body > * { position: relative; z-index: 1 }` para que el grano de papel quede detrás del contenido. Un hijo directo del body casaba con esa regla, y como esta hoja va **sin capa** mientras las utilidades de Tailwind viven en `@layer utilities`, gana sin importar la especificidad: (0,0,1) le gana a `.fixed`. Es el mismo mecanismo que ya costó un bug en `.site-nav-links`, en la dirección contraria.
  **Aplicación futura:** Todo overlay portallado lleva su propia clase sin capa (`body > .viewport-overlay`) declarada al lado de `body > *`, con el motivo escrito. Y cuando una utilidad de Tailwind «no se aplica», comprobar si el conflicto viene de una regla sin capa antes que de la especificidad o del orden.
- **2026-10-03 — Un router que solo hace `flush` responde 201 y no escribe nada:**
  **Contexto:** En `/admin/seguridad`, «Nuevo usuario» devolvía 201, el formulario anunciaba «dado de alta», la lista se refrescaba… y la cuenta no existía. `get_session` cede la sesión y la cierra sin confirmar, así que una ruta que deja que el servicio haga `flush` y responde bien nunca confirma nada. `admin.py` era el **único** router de escritura sin un solo `session.commit()`.
  **Aprendizaje:** El síntoma —un 201 y un mensaje de éxito— es exactamente el que un error produce, así que la duda correcta no es «¿guardó?» sino «¿qué prueba lo afirmaba?». Y la respuesta es: ninguna. 611 pruebas pasaban porque la fixture comparte **una** sesión y un SAVEPOINT entre la petición y la aserción, y una fila sin confirmar es perfectamente visible ahí. Leer el dato de vuelta no distingue el bug; hay que afirmar sobre la sesión.
  **Aplicación futura:** Ante un router nuevo, contar los `commit` awaitados por escritura (spy sobre `database_session.commit`), no leer el resultado de vuelta. Y ante un 2xx sospechoso, comprobar la fila con una conexión **por fuera** del proceso: es el único modo de distinguir «se guardó» de «pareció guardarse».

- **2026-10-03 — Un diff invertido en el servidor se hace pasar por «no cambió nada»:**
  **Contexto:** El diálogo de roles marcaba `abogado` y desmarcaba `asistente`, y la tabla seguía mostrando `ASISTENTE`. Las cuatro llamadas HTTP salían con 200: `toAdd` y `toRemove` estaban intercambiados, de modo que se «asignaba» el rol desmarcado y se «retiraba» el marcado. Con roles coincidentes el error es invisible; con roles distintos intercambia dos permisos y nadie se entera hasta que alguien pierde el acceso.
  **Aprendizaje:** Un conjunto de diferencias se lee una vez, comprobando los dos lados con un caso concreto, no releyendo el código: `wanted` son las casillas marcadas y `current` las que tiene el servidor; lo que está en `wanted` y no en `current` se **añade**, y al revés se **retira**. Cuando dos expresiones son simétricas y se parecen, el compilador no ayuda.
  **Aplicación futura:** Escribir primero el caso a mano en la prueba de la acción (`current=[asistente]`, `wanted=[abogado]` → añade `abogado`, retira `asistente`) antes de tocar la implementación. Un 200 por llamada no dice nada sobre el conjunto final.

- **2026-10-03 — Sin `revalidatePath`, la escritura existe y la pantalla miente:**
  **Contexto:** Desactivar un usuario escribía en la base (`is_active=false`) y el ledger seguía mostrando `ACTIVO` con el botón «Desactivar». `deactivateUser` y `reactivateUser` no llamaban a `revalidatePath`, a diferencia de `createUser`, `updateUser` y `setUserRoles`, que sí lo hacían.
  **Aprendizaje:** Un Server Action que escribe y no revalida deja el árbol del servidor describiendo el mundo anterior; la acción es correcta y la pantalla miente, que es peor que un error visible porque se lee como «la operación no hizo nada». En esta casa toda escritura de administración revalida la ruta de su módulo, sin excepción por acción pequeña.
  **Aplicación futura:** Al añadir una Server Action, el `revalidatePath` va en el mismo commit que el `apiFetch`. Al verificar en el navegador, comprobar que la fila **cambia sin recargar**: es la prueba de que la revalidación existe.

- **2026-10-03 — Un esquema de salida que revalida la entrada tumba la lista entera:**
  **Contexto:** `GET /admin/users` devolvía 500 para todo el mundo porque una fila sembrada tenía `admin@wabogados.local` y `UserBase.email: EmailStr` volvía a validar esa dirección al serializarla. Una sola fila inválida tumba la página, porque la respuesta se valida entera o no se valida.
  **Aprendizaje:** `EmailStr` (y cualquier validador de dominio) pertenece a la **entrada**. Un esquema que se usa también como respuesta hereda la regla de entrada y convierte un dato viejo en un 500. El mismo patrón ya había tumbado `GET /clients` por un `NIF` en un `Literal` cerrado.
  **Aplicación futura:** Al escribir un esquema, decidir primero si es de entrada o de salida: entrada valida, salida lee. Si un campo aparece en ambos, son dos tipos (`UserCreate` y `UserResponse`), no uno. Y el CLI que escribe directo en la base valida lo mismo que la API, porque si no deja entrar por la puerta de atrás exactamente lo que la puerta bloquea.

- **2026-10-03 — `compose.yaml` no monta el código del backend:**
  **Contexto:** Un cambio en `backend/app/**` no se veía en el backend en marcha: los tests sí lo veían (el servicio `test` monta `./backend:/build`) y el navegador no. La respuesta de la API era la antigua, sin error ni rastro.
  **Aprendizaje:** El servicio `backend` es `build: ./backend` sin bind mount, así que ejecuta una **imagen**. Editar el código no la cambia: hay que reconstruir. Los tests y el navegador están mirando dos cosas distintas, y ambos pueden estar «bien» a la vez.
  **Aplicación futura:** Tras tocar el backend, `docker compose up -d --build backend` antes de verificar nada en el navegador, y confirmar con una lectura dentro del contenedor (por ejemplo, contar los `session.commit()` del archivo desplegado) en lugar de asumir que el rebuild funcionó.
- **2026-10-03 — Un `onupdate` del servidor deja el atributo expirado y leerlo es un 500:**
  **Contexto:** En Configuración, crear un ajuste funcionaba y **modificarlo** devolvía 500 con `sqlalchemy.exc.MissingGreenlet`. `updated_at` es `onupdate=func.now()`, una expresión SQL que el ORM no puede calcular: tras un UPDATE el atributo queda expirado y hay que ir a buscarlo. El router serializa la respuesta desde una función normal, fuera del greenlet, así que ese `await` se dispara en el sitio equivocado.
  **Aprendizaje:** Un INSERT devuelve sus columnas (PostgreSQL + `RETURNING`), y por eso el alta funcionaba y la segunda escritura no: **son dos rutas de código y solo se probó una**. Detrás hay una regla: los servicios de este proyecto hacen `flush()` y luego `refresh()`, treinta y tantos sitios, y `settings.py` era el único servicio mutante sin el `refresh`. Cuando un servicio nuevo no sigue el patrón, el síntoma es un 500 en la *segunda* escritura, no en la primera.
  **Aplicación futura:** Después de un `flush()` en una ruta que modifica una fila existente, `await session.refresh(objeto)` si la respuesta se serializa fuera del greenlet. Y probar cada ruta de escritura **dos veces**: crear y modificar no son el mismo código, y una prueba que solo crea deja la mitad sin cubrir.

- **2026-10-03 — El navegador centra cada `th`, y una columna estrecha esconde el fallo:**
  **Contexto:** En Configuración la clave de cada ajuste aparecía flotando en el medio de su columna mientras el encabezado «CLAVE» estaba a la izquierda. Los otros siete listados tenían lo mismo, pero con columnas estrechas el texto centrado casi coincidía con el inicio y nadie lo veía.
  **Aprendizaje:** `<th scope="row">` es un `th`, y la hoja de estilos del navegador centra **todos** los `th`. La regla del proyecto solo corregía `thead th`, así que el cuerpo quedaba fuera. Un fallo de alineación se agrava con el ancho: la misma causa pasa de «imperceptible» a «obvio» según la celda, y por eso conviene corregirlo en la hoja compartida en lugar de en cada componente.
  **Aplicación futura:** Al escribir una tabla nueva, mirar el ancho real de la primera columna y no solo el marcado. Y ante un problema visual que «sale en una página y no en otra», sospechar primero de la hoja compartida.

- **2026-10-03 — Si el texto está en pantalla, el buscador debe encontrarlo:**
  **Contexto:** Buscar «retencion» en Configuración no devolvía nada, aunque «Retencion» estaba escrito como encabezado de bloque en la propia pantalla. La búsqueda cubría clave, descripción y valor, y no la categoría.
  **Aprendizaje:** Un buscador es una promesa sobre lo que la persona ve. Lo que la pantalla muestra como encabezado es un término de búsqueda, aunque el código que guarda la fila no lo contemplate: la división entre «datos que se buscan» y «datos que se muestran» no la hace el modelo, la hace quien lee.
  **Aplicación futura:** Al escribir un filtro de texto, incluir todo lo que la misma pantalla muestra cerca de la fila, y decirlo en el `placeholder`. Un filtro que ignora una palabra visible en pantalla enseña a la gente a no usarlo.

- **2026-10-03 — Una fila que se borra puede Serializable mal y la promesa queda vacía:**
  **Contexto:** El diálogo de borrado de Configuración promete que «el valor anterior queda anotado en el historial de cambios». Se comprobó en la base: `change_logs` guarda `value` y `category` con `change_reason = "Ajuste eliminado"` y actor. La promesa era verdad, pero no se había mirado.
  **Aprendizaje:** Cuando la interfaz promete que algo sobrevive a una acción destructiva, esa promesa es una afirmación sobre el backend y se verifica como una consulta, no como una frase bien escrita. En este caso el servicio tenía un comentario que explicaba exactamente por qué el borrado era aceptable (un ajuste no es un registro jurídico) y un `after` con nulos a propósito para que `record_changes` registrara la baja.
  **Aplicación futura:** Antes de escribir «no se pierde nada» en un diálogo, ejecutar la operación y consultar el historial. Si la promesa no se puede comprobar, no se escribe.

- **2026-10-06 - Un filtro de alcance, aplicado a la puerta equivocada, deja la lectura abierta**:
  **Contexto:** El mismo fallo aparecio cinco veces en una sola auditoria: `documents` (el listado filtraba, el detalle no), `billing` (diez rutas sin `get_user_scope`), `create_evidence` (una comprobacion con `CaseScope.ALL`, que devuelve `None` por definicion, asi que nunca se ejecutaba), `media` (ninguna ruta tomaba el alcance) y `messages`. En todos, la **escritura** comprobaba el expediente y la **lectura** no.
  **Aprendizaje:** Un alcance comprobado solo al crear deja un agujero permanente, porque elモデル de permisos no cambia solo: la persona deja de estar asignada y sigue viendo. Y una comprobacion que depende de un valor constante (`CaseScope.ALL`) no es una comprobacion: es codigo muerto que se lee como si protegiera. La segunda forma es peor que no tener filtro, porque la revision la da por buena.
  **Aplicacion futura:** En cualquier recurso con `case_id`, la pregunta es *que pasa cuando el alcance del usuario cambia*, no *puede crear en un expediente ajeno*. Y ante un filtro, comprobar que el predicado no es trivialmente `None`.

- **2026-10-06 - `NULL` en la columna de expediente significa material firm'swide, no material prohibido**:
  **Contexto:** Al filtrar `billing` estrictamente por expediente, `test_staff_drafts_but_neither_issues_nor_voids` paso de `422` ("un borrador no admite pagos") a `404` ("no existe"). Recepcion redacta facturas sin expediente y recibia una respuesta peor que la que se reemplacia. El mismo razonamiento aplica a `media_items` y a las conversaciones sin `case_id`.
  **Aprendizaje:** `case_scoped` produce `case_id IN (...)`, y `NULL IN (...)` nunca es verdadero, asi que las filas sin expediente desaparecen para un llamador restringido. Que eso sea lo correcto depende del negocio, no del SQL, y aqui no lo es.
  **Aplicacion futura:** El criterio que quedo, y que ya se uso dos veces: **expediente presente -> se filtra; `NULL` -> visible para quien tenga el permiso**. Fijarlo con una prueba que lo nombr (`test_a_firm_wide_invoice_is_not_case_scoped`) para que endurecerlo sea una decision visible y no un efecto colateral.

- **2026-10-06 - Una prueba que envia el campo equivocado no falla: desaparece**:
  **Contexto:** Al probar el limite de adjuntos, los ficheros se enviaron bajo el nombre `file` y el parametro del endpoint se llama `files`. FastAPI recibio **cero** ficheros, creo el mensaje sin adjuntos y devolvio `201`; el `assert 413` fallo por la razon equivocada. Sin el `DEBUG files= 0` se habria "arreglado" el endpoint persiguiendo una prueba que nunca lo ejercitaba.
  **Aprendizaje:** En multipart, el nombre del campo debe coincidir con el nombre del parametro. Un `default=[]` en la firma hace que el error sea silencioso en lugar de un 422, y el estado de exito (`201`) es indistinguible del estado de exito real.
  **Aplicacion futura:** Toda prueba de limite de subida necesita **ademas** una prueba de resultado que exija el camino feliz. Sin ella, un `default` permisivo convierte el endpoint en un caja negra que cualquier prueba de error atraviesa sin tocar.

- **2026-10-06 - Cambiar un helper sin cambiar a quien lo llama deja la mitad del sistema como estaba**:
  **Contexto:** El arreglo de `X-Forwarded-For` hizo `get_client_ip` seguro por defecto y actualizo **solo** el limitador. `audit.py` y las seis llamadas de evidencias siguieron usando `get_client_ip(request)`. Nadie lo noto: el nuevo default nunca es inseguro, ignora la cabecera, asi que los 769 tests pasaron mientras, detras de un proxy real, **toda la auditoria registraba la IP del proxy**.
  **Aprendizaje:** El riesgo no es la seguridad sino la **degradacion silenciosa**: un cambio de contrato solo se propaga a los sitios que se tocan, y cuando el default es seguro el fallo es invisible. La prueba que faltaba no era de seguridad sino de **cableado**.
  **Aplicacion futura:** Al cambiar la firma o el comportamiento de un helper compartido, buscar todos los llamadores (`grep`, no de memoria) y anadir una prueba que falle si alguien vuelve a omitir el argumento. Centralizar la lectura en un `_trusted_proxies()` hace que el olvido sea imposible de escribir.

- **2026-10-06 - Sin git, un error de edicion se recupera de una foto old**:
  **Contexto:** `-replace` encadenado con `| Out-Null` dejo `$c` en `$null` y `WriteAllText` vacio `test_messaging.py`: 960 de 1309 lineas. Se recupero de la imagen `wabogados_v1_master-backend:latest`, de 13 horas antes. La suite completa pasa, **pero el fichero no es el que habia y eso no se puede demostrar**.
  **Aprendizaje:** Un conjunto de pruebas en verde **no** prueba que el codigo bajo prueba sea el que crees. Y cuando la recuperacion viene de una instantanea antigua, el resultado es *plausible*, que es peor que estar roto porque deja de pedir verificacion.
  **Aplicación futura:** Comprobar (Get-Item).Length sobre todo fichero escrito con un script. Y tratar la ausencia de git como un hallazgo de seguridad activo, no como una molestia de método: mientras no exista, cualquier error destructivo de edición es irreversible y se recupera de una instantánea vieja, que es peor que no recuperar.

- **2026-10-22 — cap_drop ALL contra imágenes con init propio (ClamAV):**
  **Contexto:** Al integrar `clamav/clamav:1.5.4-debian13-slim` con la postura
  de seguridad del proyecto (`security_opt: no-new-privileges`, `cap_drop: ALL`),
  el init de la imagen entró en bucle de reinicio con cuatro errores distintos y
  sucesivos: sin CHOWN (volver a ajustar los dueños), sin DAC_READ_SEARCH
  (enumerar un volumen que queda en 0700 tras el primer pase), sin
  DAC_OVERRIDE (freshclam escribe un log propiedad del usuario clamav) y sin
  SETUID/SETGID (bajar privilegios a clamav para ejecutar clamd).
  **Aprendizaje:** El principio "cap_drop ALL" es correcto pero insuficiente por
  sí solo: las imágenes con entrypoint que ajustan permisos y bajan de
  usuario necesitan un conjunto mínimo legado y comentado capability por
  capability. Además, el healthcheck que documenta una variante de la imagen
  no sirve para otra (debian13-slim trae clamdcheck.sh, no clamdcheck.py):
  comprobar lo que la imagen trae, no lo que los docs de otra dicen.
  **Aplicación futura:** Ante una imagen con init propio y cap_drop ALL,
  arrancar con `docker run` en un shell para inspeccionar dueños/modos de los
  directorios tocados por el init, y añadir exactamente las capacidades del
  defendido en compose con comentarios. Falla cerrada nunca requiere
  adivinanzas: reproduce el error, no des la pausa completa.

- **2026-10-21/22 — la primera prueba de una ruta destapa lo que ninguna otra
  miraba:**
  **Contexto:** Al escribir la primera prueba del `413` de la biblioteca
  multimedia (el tope de 500 MB nunca se había ejercitado), la corrida destapó
  un aviso de deprecación (`HTTP_413_REQUEST_ENTITY_TOO_LARGE`, renombrado en
  Starlette 1.x) que ya estaba resuelto en el envoltorio
  `app/core/http_status.py` y que el router seguía sin usar, precisamente
  porque ese código de error nunca se ejecutaba en pruebas.
  **Aprendizaje:** Un código de error sin prueba es un rincón donde el
  mantenimiento se propaga a medias: la corrección de las constantes HTTP del
  proyecto existe, y lo que no la importa no la recibe.
  **Aplicación futura:** Al tocar por primera vez una respuesta de error,
  comprobar de qué módulo viene su constante; si existe el envoltorio propio,
  adoptarlo y probar la respuesta, que es cuando el aviso y la deprecación
  dejan de pasar desapercibidos.

- **2026-10-21/22 — una clave determinista de derivado frente a la expectativa
  de "clave distinta al reemplazar":**
  **Contexto:** La prueba de regeneración de miniatura esperaba que al reemplazar
  la imagen el `storage_key` cambiara, y falló con dos claves idénticas. La
  expectativa era contraria al diseño: `build_media_derivative_key` es
  determinista "a propósito", porque una regeneración escribe **sobre su propia
  salida** en vez de acumular copias junto a ella.
  **Aprendizaje:** Con claves deterministas, la identidad del objeto no prueba
  la regeneración: la prueba de sustitución debe comparar el **contenido** (el
  digest del derivado contra el resultado esperado), no la dirección.
  **Aplicación futura:** En cualquier esquema de claves reproducibles (S3,
  derivados, transcodes), afirmar sobre bytes y digest; reservar "cambió la
  clave" para afirmar una rotación de claves, que es distinta operación.

- **2026-11-11 — Auditoría y verificación local en host Linux:**
  **Contexto:** Auditoría del proyecto cruzando memoria y estado real. El
  ciclo del 8-nov llevaba sin commit (103 modificados + 37 sin seguimiento,
  con 4 migraciones nuevas) y la suite no se podía correr localmente.
  **Aprendizaje:** `backend/.venv` está creada en Windows (`Scripts/`,
  `pyvenv.cfg`) y es inutilizable en el host Fedora; la única vía local para
  pytest/ruff/mypy es el stack de Compose (`compose.test.yaml`), que además
  estaba parcialmente parado (solo clamav y evidence-worker). Lo sí
  verificable sin BD es barato y fiable: `npx tsc --noEmit` (limpio) y
  `python3 -m py_compile` (OK) en los módulos nuevos.
  **Aplicación futura:** Al auditar, distinguir "verificado hoy" de "estado
  registrado en memoria": memoria decía suite en verde de 2026-10-06/22, pero
  ese veredicto no cubre el trabajo sin commit posterior. Antes de declarar
  una tarea terminada sin venv local, exigir el paso por `docker compose -f
  compose.yaml -f compose.test.yaml` y commit del ciclo.

- **2026-11-11 — Pruebas visuales y catálogo público editable:**
  **Contexto:** La regresión pública esperaba siete tarjetas de servicios, pero la API activa publica doce áreas; siete solo corresponde al contenido de respaldo sin API.
  **Aprendizaje:** Una prueba de layout sobre datos reales no debe fijar el número de registros de un catálogo editable. Debe comprobar contenido no vacío, títulos únicos, navegación y ausencia de desbordamiento.
  **Aplicación futura:** Reservar recuentos exactos para fixtures controlados y verificar la composición responsive independientemente del volumen de datos publicado.

- **2026-11-11 — Precarga de tarjetas y límites compartidos de API:**
  **Contexto:** Las tarjetas con `next/link` precargaban detalles que consultaban el catálogo público; al recorrer repetidamente la portada en Playwright se alcanzó el límite compartido de 100 peticiones por minuto y apareció el contenido de respaldo.
  **Aprendizaje:** La precarga automática de muchas rutas dinámicas puede consumir el presupuesto de API aunque el usuario no navegue a ellas. Además, una prueba debe esperar la URL de destino antes de leer o rellenar la nueva página.
  **Aplicación futura:** Desactivar la precarga en rejillas de detalles con acceso a API cuando no compense, reutilizar el catálogo por render y evitar recargar toda la portada en cada iteración de pruebas de navegación.

- **2026-11-11 — Analítica, auditoría e identidad efímera:**
  **Contexto:** Un contador sin campos personales igualmente habría duplicado IP/user agent en el middleware de auditoría y los escenarios E2E habrían inflado el contador real.
  **Aprendizaje:** La minimización debe revisarse de extremo a extremo: payload cerrado, rutas publicadas, sin credenciales/metadatos reenviados, excepción exacta del intake en auditoría y pruebas de escritura en una base efímera separada. Un UUID solo en memoria estima navegaciones, no personas ni únicos mensuales.
  **Aplicación futura:** Respetar DNT/GPC, documentar explícitamente estimación/retención, usar un presupuesto separado e idempotencia transaccional y excluir pruebas generales mediante DNT; nunca sembrar demostraciones en datos reales.
