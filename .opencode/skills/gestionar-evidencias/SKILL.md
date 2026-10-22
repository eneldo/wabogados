---
name: gestionar-evidencias
description: "Al implementar carga, optimización, almacenamiento o descarga de PDF, PNG y JPEG."
---

# Documentos y evidencias

1. Leer la especificación de evidencias y sus límites.
2. Validar tamaño, contenido real, MIME y extensión; limitar recursos de procesamiento y tratar entradas como no confiables.
3. Preservar el original inmutable y su SHA-256; crear derivados con hash propio y vínculo a la versión de origen.
4. Optimizar sin prometer ahorro fijo; conservar el original si no hay mejora o falla el proceso.
5. Evitar modificar originales firmados; mantener originales cifrados o protegidos según el proyecto.
6. Registrar versiones, resultados, autor y trazabilidad; autorizar cada descarga y evitar rutas públicas.
7. Comprobar legibilidad, PDFs firmados, archivos inválidos, fallos y acceso denegado.

## Entrega

Entregar original y derivados trazables, métricas de tamaño y validación; no afirmar que compresión con pérdida conserva identidad binaria.
