# Plan P0 — Mejora de la página pública (ejecución)

**Inicio:** 2026-11-15  
**Autorización:** usuario autorizó iniciar P0 (1–3) y solicitó registrar cada paso en memoria antes de continuar con el siguiente.  
**Alcance P0:** 1) Confianza/legal/contacto (datos reales aprobados), 2) Claridad y conversión del formulario de consulta, 3) Prueba social sin inventar credenciales.

## Paso 1 — Confianza, legal y datos de contacto (P0-1)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Datos aprobados por la firma (confirmados por usuario)
- Correo: `amiabogado@hotmail.com`
- Razón social: `WABOGADOS`
- Responsable del tratamiento: `William Andres Ruiz`
- Canal/procedimiento para ejercer derechos: `Edificio Berna Carrera 9 No. 16-20 Oficina 206, Bogotá`
- Confirmación explícita para retirar etiquetas/notas de "Pendiente de revisión/confirmación": **Sí**

### Cambios realizados
- `frontend/app/(public)/page.tsx`: actualizado `CONTACT` (dirección aprobada + email), correo visible y enlazado en contacto, retirada nota "Pendiente de revisión" y texto "por confirmar"; nota informativa ajustada indicando tratamiento conforme a aviso aprobado.
- `frontend/components/public/contact-form.tsx`: aviso de privacidad actualizado con razón social, responsable del tratamiento y canal de derechos (incluye oficina y correo), retirada nota de pendiente de revisión.
- `frontend/components/public/site-header.tsx`: `FOOTER_CONTACT` actualizado con dirección/correo aprobados y correo visible/enlazado en footer.
- Ajuste colateral mínimo para mantener lint en verde: `frontend/components/admin/roles/role-form.tsx` (evitado `setState` síncrono en efecto; corrección no funcional del comportamiento esperado).

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` con 0 errores (persiste warning previo en `app/portal/casos/[caseId]/page.tsx:288`).
- Frontend reconstruido y redesplegado: `docker compose build frontend` + `docker compose up -d --no-deps --wait --wait-timeout 90 frontend`.
- Verificación en `http://localhost:3000`: presencia de `amiabogado@hotmail.com`; sin ocurrencias de "por confirmar" ni "Pendiente de revisión" en la portada servida.

### Notas
- El aviso de privacidad fue actualizado con la información aprobada proporcionada; no se inventaron plazos/procedimientos adicionales no indicados. Se recomienda que el despacho conserve respaldo interno de la aprobación textual completa si aplica.

## Paso 2 — Claridad y conversión del formulario de consulta (P0-2)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha cierre:** 2026-11-15

### Cambios realizados (`frontend/components/public/contact-form.tsx`)
- Añadido bloque visible "Qué ocurre al enviar" con expectativa de revisión/contacto del despacho y alternativa inmediata de llamada (`+57 312 469 9617`).
- Añadida microcopia de privacidad junto al consentimiento (finalidad limitada, sin cesión comercial).
- Mejoradas validaciones y accesibilidad: `noValidate` con validación previa accesible, mensajes de error específicos por campo, `aria-invalid` y `aria-describedby` (incluye pista de longitud en mensaje), foco en primer campo con error.
- Mensajes de rechazo/fallo mantienen y refuerzan alternativa telefónica e indican que los datos permanecen en el formulario.
- **Contrato preservado:** éxito mostrado solo con respuesta HTTP 201 (referencia/mensaje del servidor); el formulario se limpia únicamente tras registro exitoso.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado (`docker compose build frontend` + `docker compose up -d --no-deps --wait --wait-timeout 90 frontend`).

## Paso 3 — Prueba social sin inventar credenciales (P0-3)

**Estado:** COMPLETADO (ajustes implementados y desplegados localmente, sin inventar información)  
**Fecha cierre:** 2026-11-15

### Cambios realizados (`frontend/app/(public)/page.tsx`)
- Sección equipo: texto introductorio ajustado para enfatizar escucha, claridad y acompañamiento (sin afirmar credenciales, años, casos o reconocimientos).
- Nota inferior del equipo: retirada etiqueta "Pendiente" y reemplazada por mensaje factual/positivo sobre cercanía, criterio y comunicación en el proceso (sin datos no aprobados).

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado (`docker compose build frontend` + `docker compose up -d --no-deps --wait --wait-timeout 90 frontend`).

---

# Plan P1 — Mejora de la página pública (ejecución)

**Inicio:** 2026-11-15  
**Alcance P1:** 4) Jerarquía y escaneabilidad, 5) Estado operativo y transparencia, 6) Navegación y recorrido móvil, 7) Contenido de secciones condicionales.

## Paso 4 — Jerarquía y escaneabilidad del hero/servicios (P1-4)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/app/(public)/page.tsx`: hero con propuesta de valor más clara para personas y empresas, CTA principal "Solicitar consulta" siempre visible, acceso a portal como acción secundaria cuando aplica y alternativa de llamada.
- `frontend/lib/public-services.ts`: orientación genérica "cuándo acudir" por área (mapeo por nombre normalizado, sin casos ni credenciales inventadas) expuesta en `publicServices`.
- `frontend/app/(public)/page.tsx` y `frontend/app/servicios/[slug]/page.tsx`: tarjetas y detalle muestran "Cuándo acudir" para mejorar escaneabilidad.
- `frontend/app/servicios/[slug]/page.tsx`: nota de privacidad actualizada para coherencia con P0 (elimina mención desactualizada de aviso pendiente).

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado (`docker compose build frontend` + `docker compose up -d --no-deps --wait --wait-timeout 90 frontend`).

## Paso 5 — Estado operativo y transparencia (P1-5)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/app/(public)/page.tsx`: indicador de estado del sistema en contacto presentado de forma contextual ("Operativo/En revisión") con enlace a `/estado` para ver detalle.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

## Paso 6 — Navegación y recorrido móvil (P1-6)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/components/public/mobile-cta.tsx` (nuevo): barra fija discreta en móvil con acciones rápidas "Llamar" y "Consultar".
- `frontend/app/(public)/page.tsx` y `frontend/app/servicios/[slug]/page.tsx`: integración del CTA móvil (consulta a contacto/consulta del servicio).
- `frontend/app/public-site.css`: estilos responsive de la barra y espaciado inferior en `.public-home` para evitar solapamiento en pantallas pequeñas.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

## Paso 7 — Contenido de secciones condicionales (P1-7)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/app/(public)/page.tsx`: estado vacío de "Criterio Legal" más claro y útil (sin promesa de fechas), con invitación a realizar una consulta para orientación específica.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

**P1 (4–7) completado.**

---

# Plan P2 — Mejora de la página pública (ejecución)

**Inicio:** 2026-11-15  
**Autorización:** usuario autorizó continuar con P2 (8–10).  
**Alcance P2:** 8) SEO/metadatos y compartibilidad, 9) Rendimiento percibido/CWV, 10) Accesibilidad (WCAG).

## Paso 8 — SEO técnico y compartibilidad (P2-8)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/lib/site.ts` (nuevo): constantes compartidas de sitio/contacto (NAP aprobado) y `siteUrl()` basada en `NEXT_PUBLIC_SITE_URL` (fallback localhost).
- `frontend/app/layout.tsx`: `metadataBase` y metadatos base (título plantilla, OG/Twitter, robots) con idioma/localización.
- `frontend/app/(public)/page.tsx`: metadatos de portada (title/description/canonical/OG/Twitter) y JSON-LD (`Organization`/`LegalService`/`LocalBusiness` + `WebSite`) con información verificada.
- `frontend/app/servicios/[slug]/page.tsx`: metadatos por servicio (canonical, description con orientación, OG/Twitter) y JSON-LD `LegalService`; uso de contacto compartido.
- `frontend/app/robots.ts` y `frontend/app/sitemap.ts` (nuevos): reglas públicas/privadas y sitemap de portada + áreas de servicio.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado. Verificado: `/robots.txt` y `/sitemap.xml` responden correctamente.

## Paso 9 — Rendimiento percibido (P2-9)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/app/(public)/page.tsx`: imágenes no críticas (equipo y aliados) ajustadas con `sizes` más precisos, `loading="lazy"` y `decoding="async"` para reducir carga inicial sin afectar el LCP.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

## Paso 10 — Accesibilidad (P2-10)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/components/public/site-header.tsx`: enlace "Saltar al contenido principal" para navegación por teclado/lectores.
- `frontend/app/(public)/page.tsx` y `frontend/app/servicios/[slug]/page.tsx`: `main` con `id="contenido-principal"` como destino del salto.
- `frontend/app/public-site.css`: estilos de `.skip-link` visibles al recibir foco.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

**P2 (8–10) completado.**

---

# Plan P3 — Mejora de la página pública (ejecución)

**Inicio:** 2026-11-15  
**Autorización:** usuario autorizó continuar con P3 (11–13).  
**Alcance P3:** 11) Analítica first-party para embudo/priorización, 12) Consistencia SEO local avanzada, 13) Mejora continua/pruebas públicas ampliadas.

## Paso 11 — Analítica first-party para embudo/priorización (P3-11)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/app/(admin)/admin/estadisticas-web/page.tsx`: sección "Embudo estimado (priorización)" con pasos portada → áreas de servicio → clics en teléfono → solicitudes registradas, incluyendo desglose básico de clics (portada/áreas) y proporciones agregadas con advertencias de interpretación (no atribución de personas/sesión única).
- `docs/ESTADISTICAS_WEB.md`: documentación actualizada para reflejar el embudo en el panel.

### Notas
- Se reutilizan métricas existentes (vistas por ruta, clics telefónicos, consultas registradas en servidor) sin ampliar la recolección ni introducir identificadores persistentes.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

## Paso 12 — Consistencia SEO local avanzada (P3-12)

**Estado:** COMPLETADO (implementado y desplegado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/components/public/site-header.tsx`: footer unificado con `SITE_CONTACT` (fuente única NAP verificada).
- `frontend/app/(public)/page.tsx`: enlace "Cómo llegar" junto al mapa hacia OpenStreetMap con coordenadas de referencia del despacho.

### Validación y despliegue
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- Frontend reconstruido y redesplegado.

## Paso 13 — Mejora continua y pruebas públicas ampliadas (P3-13)

**Estado:** COMPLETADO (implementado y verificado localmente)  
**Fecha registro:** 2026-11-15  
**Fecha cierre:** 2026-11-15

### Cambios realizados
- `frontend/e2e/public-site.spec.ts`: ajustada expectativa de navegación del hero al copy vigente ("Ver áreas de práctica") tras mejoras de P1.
- `docs/IDENTIDAD_WEB_PUBLICA.md`: documentadas mejoras P0–P3, puntos de SEO/`NEXT_PUBLIC_SITE_URL`, accesibilidad, embudo de analítica y estado de pruebas.
- `docs/ESTADISTICAS_WEB.md`: documentado embudo estimado en panel (Paso 11).

### Validación
- `frontend`: `npm run typecheck` OK; `npm run lint` 0 errores (warning previo en portal).
- **Pruebas públicas:** `npx playwright test --project=public` → **19/19 aprobadas** (tras ajuste de prueba al copy actualizado).
- Frontend reconstruido y redesplegado durante los pasos de P3 según correspondió.

**P3 (11–13) completado. P0–P3 completados.**

## Paso 13 — Mejora continua y pruebas públicas ampliadas (P3-13)

**Estado:** PENDIENTE


## Paso 9 — Rendimiento percibido (P2-9)

**Estado:** PENDIENTE

## Paso 10 — Accesibilidad (P2-10)

**Estado:** PENDIENTE


