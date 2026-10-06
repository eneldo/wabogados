# ADR-0007 — Frontend Stack & Docker Strategy

**Fecha:** 2026-09-30
**Estado:** Accepted

## Contexto
El frontend debe ser moderno, tipado estrictamente, accesible y desplegable en contenedor.

## Decisión
**Stack:**
- Next.js 16 (App Router, Server Components por defecto)
- React 19
- TypeScript strict mode (`strict: true`)
- Tailwind CSS 4 (PostCSS plugin)
- ESLint 9 flat config (`eslint.config.mjs`)
- Lucide Icons (pendiente)
- shadcn/ui (pendiente)
- TanStack Query / React Hook Form / Zod (pendiente)

**Docker:**
- Multi-stage: `base` → `builder` → `runner` (non-root)
- Output `standalone` para imagen mínima
- Healthcheck: `wget --spider -q http://localhost:3000/`
- Security: `no-new-privileges:true`, `cap_drop: ALL`

**Variables:**
- `API_INTERNAL_URL` para comunicación backend→frontend en red Docker.

## Alternativas descartadas
- Pages Router: legacy, sin Server Components.
- CSS Modules / Styled Components: Tailwind 4 es más productivo y consistente.
- Imagen monolítica sin standalone: mayor superficie de ataque y tamaño.

## Impacto
- SSR/ISR/SSG nativos, streaming, Suspense.
- Type safety end-to-end con schemas compartidos (pendiente).
- Imagen de producción ~100MB vs ~1GB.
- Security hardening por defecto.