# Identidad visual de la web pública

La portada `/` utiliza el logo facilitado en `logo_Wabogados.jpg` y la paleta
de `wabogado-2.jpg`: azul noche `#252b39`, gris azulado `#303440`, rojo `#ed1c24`
y blanco. Los textos y estados interactivos usan variantes más claras del rojo
para mejorar el contraste sobre fondo oscuro.

## Recursos

- Original: `logo_Wabogados.jpg` (no modificar).
- Copia pública: `frontend/public/logo_Wabogados.jpg`.
- Derivado: `frontend/public/marca/wabogados-logo.webp`, sin los márgenes blancos
  excesivos, sin estirar ni recortar el dibujo.
- Regeneración: `python3 execution/prepare_public_brand.py` (requiere Pillow).

La cabecera y el pie muestran el mismo recurso con proporción natural y una
superficie blanca, manteniendo visibles tanto el negro como el rojo originales.
La paleta es compartida por toda la plataforma desde `globals.css`; el logo se
reutiliza con `BrandLogo`. Ver `docs/IDENTIDAD_PLATAFORMA.md` para portales y
estados semánticos. `.public-site` solo delimita la composición de la portada.
Los contenedores ocupan todo el ancho con márgenes interiores fluidos de 20–80 px.

## Portada editorial (2026-11-11)

La página principal tiene una composición editorial de dos columnas: mensaje y
acciones a la izquierda, ilustración arquitectónica enmarcada a la derecha.
En móvil se apilan sin ocultar contenido. La franja superior facilita la llamada
al despacho; las bandas de confianza, servicios numerados, principios y portal
tienen superficies y jerarquías diferenciadas. Se mantienen el logo original,
los colores corporativos, el equipo, las consultas reales y el acceso privado.

El rediseño usa `.public-home` dentro de `frontend/app/public-site.css`; no altera
los tokens compartidos ni la apariencia de login, administración o portal.
La sección de análisis incluye el ancla `criterio` utilizada por su paginación.
Las pruebas públicas también verifican el apilado de la portada y los enlaces a
consulta, servicios y firma.

## Navegación y consultas por área

Las tarjetas usan SVG de trazo uniforme de
`frontend/components/public/service-icon.tsx`, asignados por nombre normalizado
en `serviceIconName` (`lib/public-services.ts`), no por la posición del catálogo.
Laboral usa maletín; Penal, escudo; Familia, personas; Inmobiliario, casa;
Administrativo, institución; Ambiental, hoja; Bancario, banco; Civil, contrato;
Comercial, establecimiento; Internacional, globo; Procesal, documento verificado;
y Tributario, recibo. También se contemplan los nombres de respaldo, Constitución
y asesorías empresariales. Un área desconocida usa una balanza. Los SVG son
decorativos y mantienen los nombres y enlaces accesibles de las tarjetas.

- Cada tarjeta abre `/servicios/<nombre-normalizado>` (por ejemplo,
  `/servicios/administrativo`), con nombre y descripción del catálogo público.
  Portada y detalle comparten `lib/public-services.server.ts`; el catálogo sin
  API conserva las siete áreas de respaldo de `lib/public-services.ts`.
  Las tarjetas no precargan todos los detalles: la consulta al catálogo se hace
  al navegar, evitando consumir el límite de peticiones de la API solo al hacer
  scroll por las doce áreas. El catálogo público exitoso se comparte entre
  páginas con revalidación de 30 segundos, sin cachear identidades ni datos
  privados y sin sustituirlo por un respaldo cuando falla una petición.
- La página de área preselecciona ese nombre en `ContactForm`. La cabecera,
  el pie y «Ver todas las áreas» regresan a las secciones de la portada; no
  apuntan a anclas inexistentes dentro del detalle.
- El formulario general también muestra las áreas del catálogo vigente.
  `/api/consultas` comprueba los nombres publicados antes de enviar al backend.
  Por compatibilidad con el contrato desplegado, normaliza Penal, Familia, etc.
  a sus etiquetas originales; las demás áreas se registran como «Otra consulta»
  **con el nombre exacto del área al comienzo del mensaje**. No se pierde el área
  seleccionada. Si el prefijo supera 1500 caracteres, se solicita acortar el
  texto, sin recortarlo. No se modifica ni reconstruye el backend para este flujo.
- Un servicio desconocido muestra 404 con el catálogo disponible. Si falla el
  catálogo y no existe respaldo para la URL, se informa de la indisponibilidad.
- Las pruebas de envío del navegador simulan un rechazo y comprueban que no
  se muestra éxito ni se borran datos. No crean consultas reales en el despacho.

## Publicar y comprobar cambios locales

El frontend de Compose **no monta el código fuente del host**. Reiniciar el
contenedor o compilar `.next` en el host no actualiza la imagen en ejecución.
No es un fallo de Next.js standalone ni del caché del navegador.

Desde la raíz, sin detener el backend ni borrar volúmenes:

```sh
docker compose build frontend
docker compose up -d --no-deps --wait --wait-timeout 90 frontend
```

Desde `frontend/`:

```sh
npm run lint
npm run typecheck
npm run test:e2e -- --project=public
```

Las pruebas públicas no necesitan credenciales. Comprueban la descarga real del
logo, su proporción y límites dentro de la cabecera, los colores calculados,
el ancho de página, menú, teclado, privacidad y enlace al acceso privado.
Incluyen 320/390/768/820/900/901/1024/1440/1920/2560 px y generan capturas en
`.tmp/public-brand-review/`. No envían consultas ni modifican datos de la firma.
