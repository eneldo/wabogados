# Identidad visual compartida de WABOGADOS

## Alcance

La web pública, el acceso, la administración, el portal del cliente y las
pantallas de abogados/personal comparten ahora **el mismo sistema visual**.
También lo usan mensajes, documentos, evidencias, formularios, diálogos,
indisponibilidad, página no encontrada y estado del sistema.

Los permisos y el contenido de cada perfil se mantienen: unificar la identidad
no significa mostrar los mismos módulos o expedientes a todos.

## Criterios de color y jerarquía

| Función | Color | Uso |
| --- | --- | --- |
| Fondo institucional | `#252b39` | Continuidad con la web pública, fondo de trabajo |
| Navegación | `#1e2431` | Separar menú y contenido sin cambiar de identidad |
| Superficie | `#303440` | Tarjetas, formularios y diálogos |
| Rojo del logo | `#ed1c24` | Marca y marcador de navegación activa |
| Acción principal | `#c91620` | Botones con texto blanco y contraste suficiente |
| Acento de texto | `#ff7077` | Enlaces, foco y acentos sobre azul oscuro |
| Texto | `#f5f6f8` | Títulos y contenido principal |
| Texto secundario | `#c4c9d3` | Descripciones y navegación |

El azul/gris organiza la interfaz; el rojo atrae la atención a la acción
principal. No se colorea todo de rojo: las confirmaciones siguen en verde y las
advertencias en ámbar, con sus etiquetas. Las acciones destructivas mantienen
tratamiento de peligro, texto explícito y confirmación. El color no es el único
indicador de estado.

## Una sola fuente

- Paleta, contraste, superficies y tipografía: `frontend/app/globals.css`.
- Logo reutilizable: `frontend/components/brand-logo.tsx`.
- Recurso aprobado: `frontend/public/marca/wabogados-logo.webp`.
- Icono del navegador: `frontend/app/icon.png`, derivado del mismo original.
- Regeneración sin alterar el original: `python3 execution/prepare_public_brand.py`.
- `public-site.css` mantiene la composición de la portada; ya no redefine una
  paleta diferente para la web pública.

El logo conserva su proporción natural, sobre una base blanca para mantener el
negro y rojo originales. Tiene tamaños definidos para encabezado, menú lateral,
móvil, acceso y pie; no debe sustituirse por texto ni deformarse.

Los nombres antiguos `ink` y `paper` quedan como compatibilidad para textos.
Para fondos nuevos usar `canvas`, `surface`, `shell` u `overlay`, y para botones
principales `action` + `on-action`. No invertir texto/fondo usando `bg-ink`.

## Verificación

```sh
# Desde frontend/
npm run lint
npm run typecheck
npm run test:e2e -- --project=public
# Cuenta administradora real facilitada solo mediante variables de entorno:
npm run test:e2e -- --project=private
```

Las pruebas comprueban descarga y proporción del logo, colores calculados y
contraste de al menos 4,5:1 en los pares de texto principales/semánticos.
El recorrido privado incluye los 13 módulos, plantillas de cliente/personal,
evidencias y un diálogo de cliente abierto y cancelado, sin guardar registros.

Las plantillas comunes se inspeccionan con una sesión administradora autorizada;
eso no se presenta como un login real de un cliente, abogado o asistente. No se
cambian credenciales, roles ni permisos de cuentas reales para probar estilos.

Publicación local: reconstruir y recrear **solo frontend** según
`docs/IDENTIDAD_WEB_PUBLICA.md`. No es necesario detener backend ni base de datos.
