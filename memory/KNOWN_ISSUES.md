# KNOWN ISSUES

- **`npm audit` con 5 avisos high en la cadena de lint del frontend (2026-10-21).**
  `eslint-config-next` ≥14.3 arrastra `fast-glob`/`micromatch`/`braces`
  (ReDoS por agotamiento de pila). Esas dependencias son devDependencies del
  linting: **no viajan a producción**. No se aplicó `--force` (rompería la
  config de ESLint); se resuelven con el upgrade de Next/eslint-config-next.
- **No hay motor antivirus.** La validación de evidencia es estructural:
  firmas, formatos prohibidos, políglotos y dimensional. Eso detecta ejecutables
  disfrazados y bombas de descompresión, **no malware**. Una firma que exige
  análisis antivirus necesita ClamAV o un proveedor externo, y eso implica decidir
  dónde se analiza y qué hacer con un positivo.
- **La firma digital PDF se detecta pero no se valida.** Se informa de si existe
  una firma y de si su `ByteRange` cubre el archivo, lo que detecta un documento
  modificado después de firmarse. No se comprueba la validez criptográfica.
- **El respaldo de objetos ya se verifica por digest (2026-10-04).** Antes solo
  existía `objects.count`, que sobrevive a un archivo truncado.
  `app.cli.verify_backup_files` relee cada objeto y compara su SHA-256 contra
  `MANIFEST.sha256`, y `scripts/backup.sh` lo ejecuta antes de la copia externa y
  se detiene si falla. Lo que sigue sin probarse es una restauración completa con
  la aplicación caída.
- **El destino externo aún no existe.** La firma decidió el 2026-10-05 que será un
  bucket S3 de otro proveedor, con credenciales propias; falta crear la cuenta, el
  bucket con versionado y la credencial dedicada. Pasos en `docs/RESTORE.md`.
  `BACKUP_REMOTE_ENABLED` sigue en `false` porque el destino actual es el MinIO del
  propio host. **El código ya rechaza** que ese destino sea el bucket de los
  documentos, que era una regla escrita y no comprobada.
- **El respaldo externo no es inmutable.** Si alguien obtiene las credenciales de
  `BACKUP_REMOTE_*`, puede borrar las copias. La firma dejó la política sin
  decidir (Object Lock o equivalente); no está configurado.
- ~~**Facturación e IA jurídica inertes**~~ **Corrección (2026-10-05):** no lo
  estaban. Ambos módulos tienen backend, permisos sembrados, migraciones y
  pantalla, y se verificaron funcionando en el navegador. La memoria anterior
  decía lo contrario; era una nota obsoleta que se propagó a `NEXT_STEPS` y
  `project_context`. La única parte realmente pendiente de IA Jurídica es la
  **generación asistida**, y la propia pantalla lo dice en voz alta.
- **Multimedia no procesa nada todavía.** No hay transcodificación, ni miniaturas,
  ni duración medida (la columna `duration_seconds` existe desde la migración
  `b6c7d8e9f0a1` y **nadie la escribe**), ni cola para archivos grandes. En
  concreto falta: `ffmpeg` en la imagen, tabla de derivados multimedia, worker,
  y un contrato de escritura en streaming porque `StorageBackend.write()` solo
  acepta bytes completos. `integrity.py`, `retention.py` y `backup_manifest.py`
  **tampoco conocen `media_items`**, así que el material de la biblioteca no entra
  en el escaneo de integridad, el tiering ni el manifiesto de respaldo.
- **Ensayo de restauración hecho, con dos límites (2026-10-05).** Se borró la base
  y el almacenamiento con la aplicación detenida y se restauró desde la copia:
  los recuentos coinciden y 6 de 6 versiones documentales verifican su digest.
  Informe en `docs/RESTORE.md` §9. Pendiente: que lo ejecute alguien distinto del
  autor, y correr `scripts/backup.sh` completo en un host con `bash` (este host no
  lo tiene, así que sus pasos se replicaron a mano).
- **`scripts/backup.sh` sin probar de principio a fin en este entorno.** No es un
  defecto del script: es que este host no tiene intérprete `bash`. Sus pasos se
  verificaron uno a uno contra los contenedores.
- **PowerShell 5.1 corrompe la salida binaria nativa.** Un `pg_dump` redirigido con
  `>` produjo un archivo que `pg_restore` rechazó. Para binario usar `cmd /c` o
  `docker cp`.
- **MinIO sin verificar.** Este entorno no puede descargar `minio/minio`. El
  mecanismo S3 sí se probó contra un endpoint HTTP real.
- **`verify_integrity` completo es caro.** Descarga todos los bytes.
- **Los cuerpos `run()` de los CLI no tienen test automatizado.** Los argumentos
  y los códigos de salida sí están cubiertos; la lógica se ha ejecutado a mano en
  Docker.
- ~~Rate limiter en memoria~~ **cerrado (2026-10-05)**: `REDIS_URL` selecciona un
  contador compartido (`app/services/rate_limit_store.py`), con ventana
  deslizante y script Lua. Si el store falla, **cuenta en memoria y registra un
  error**; `RATE_LIMIT_FAIL_CLOSED=true` lo niega todo. Sin `REDIS_URL` sigue
  siendo por proceso, y el arranque lo dice en un warning.
- ~~`slowapi` es una dependencia muerta~~ **eliminada (2026-10-05)**: estaba
  declarada y nunca importada. El limitador es propio.
- **La CLI de migración a S3 solo mueve `document_versions`.** `evidence_files`,
  `evidence_derivatives`, `message_attachments` y `media_items` se quedan atrás y
  aparecerán como `missing` en `verify_integrity` si se cambia el backend sin
  migrarlos. Los errores del CLI (clave y extensión de `--rekey`, idempotencia,
  `--offset`, archivos ausentes mudos y código de salida siempre 0) sí están
  corregidos y con prueba.
- **Antivirus sigue sin integrar.** La validación de evidencia es estructural
  (firmas, políglotos, dimensiones): detecta ejecutables disfrazados, **no
  malware**. Existe un estado `EvidenceStatus.SCANNING` que se asigna y no hace
  nada — el hueco exacto del paso «escaneo antivirus» de `MASTER_PROMPT` §18.
  Integrarlo exige dos decisiones que no son mías: **dónde se analiza** y **qué
  se hace con un positivo**.
- **S3 en producción sin poder verificarse aquí.** El código está casi listo
  (arranque estricto, verificación por digest), pero la imagen `minio/minio` **no
  se puede descargar en este entorno** (`pull access denied`), así que el camino
  S3 solo se ha probado contra `moto` en proceso. Huecos conocidos del CLI de
  migración `import_documents_to_s3.py`: solo migra `document_versions` (no
  `evidence_files`, `evidence_derivatives`, `message_attachments` ni
  `media_items`), su `--rekey` está roto, no tiene `--offset` y devuelve 0 aunque
  haya digest discrepante o archivo local ausente.
- **Passlib sustituido (2026-10-04).** Emitía avisos de deprecación en Python
  3.12 y usaba `crypt`, que 3.13 elimina. Ahora el hash es `argon2-cffi`
  directamente, con los mismos parámetros, y un hash escrito por passlib sigue
  validando. No queda ninguna incidencia por aquí.
- **Sin derivaciones PDF rasterizadas.** Solo hay derivados PDF; no se genera una
  vista en imagen para un PDF escaneado.
- **Sin notificación al cliente** cuando se publica una evidencia.
- **`postgres-test` contaminado.** Si la suite se ejecuta con un motor distinto
  al del servicio, quedan filas reales. Reiniciar el servicio antes de repetir:
  `docker compose -f compose.yaml -f compose.test.yaml restart postgres-test`
- **No hay forma de reactivar ni de reabrir desde la interfaz.** Desactivar un
  cliente o abogado es de una dirección, y cerrar un expediente también. No es un
  descuido: para reactivar falta endpoint, y reabrir un expediente reescribiría su
  historia. Si la firma lo necesita, es una decisión nueva y hay que tomarla
  explícitamente, no colarla como botón.
- **Un 500 puntual tras un `recreate` no es un fallo del endpoint.** Conexiones
  obsoletas del pool hacen que el `pre_ping` de SQLAlchemy lance `MissingGreenlet`
  y la primera escritura tras recrear contenedores conteste 500. El mismo clic
  funciona a la segunda. Reconocerlo evita investigar un bug de código que no
  existe: leer la traza por dialecto o pool antes que por endpoint.
- **Una tabla `border-collapse` no pinta la sombra de su celda.** No es un
  problema del proyecto sino del contexto, pero costó una investigación larga: el
  estilo calculado informaba la sombra como aplicada y la pantalla no mostraba
  nada. Para marcar filas o celdas usar `background-image`.

## Sin control de versiones (2026-10-06) — el problema de infraestructura mas grave

**Este repositorio no es un repositorio git.** No hay `.git`, no hay historial, no hay
`git checkout`. Verificado: `git rev-parse` responde *fatal: not a git repository*.

Por eso, el 2026-10-06, encadenar un `-replace` de PowerShell con `| Out-Null` dejo
`$c` en `$null` y **`WriteAllText` vacio `backend/app/tests/test_messaging.py` entero**.
960 de 1309 lineas, cuatro pruebas de la sesion. Sin red de seguridad.

Se recupero de la imagen `wabogados_v1_master-backend:latest`, que conservaba una copia
de 13 horas antes. **El fichero recuperado no es byte a byte identico al que habia**, y
eso no se puede demostrar ni con la suite en verde. Esa es la parte que no se puede
arreglar: el dano ya esta.

Como recuperar si vuelve a pasar, en este orden:

1. `backend/.coverage` (SQLite, 1,1 MB) tiene rutas y numeros de linea, **no codigo
   fuente**. Sirve para saber que existia el fichero, no para reconstruirlo.
2. `docker create <imagen>` + `docker cp <id>:/app/app/tests/<fichero> .` — es lo unico
   que funciono. Las imagenes `test` y `docker-backend` **no** llevan el codigo de
   pruebas; `wabogados_v1_master-backend:latest` si.
3. Los `.pyc` de `__pycache__` se **sobrescriben** en la siguiente ejecucion de pytest.
   worthless despues del primer fallo.
4. No hay copia local, ni `.tmp/`, ni informe HTML de cobertura generado.

**Lo que hay que hacer y es una decision de la firma: inicializar git.** Mientras no
exista, cualquier error destructivo de edicion es irreversible y se recupera de una foto
old, que es peor que no recuperar.

### Regla de edicion que se incumplio

No encadenar `-replace` con `| Out-Null`: la tuberia devuelve `$null` y el
`WriteAllText` siguiente escribe un fichero vacio. Asuncion incorrecta de que el
`Out-Null` se aplica solo a la salida *visible*. Comprobacion posterior que siSirvio:
`Test-Path` mas `(Get-Item).Length` sobre el fichero escrito, siempre.
