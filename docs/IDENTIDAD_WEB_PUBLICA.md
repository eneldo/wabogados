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
