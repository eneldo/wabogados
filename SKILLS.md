# Skills reutilizables para WABOGADOS y próximos proyectos

Versión 1.0 · 30 de septiembre de 2026

## Propósito y alcance

Este documento reúne 27 definiciones listas para adaptar y separar en archivos `SKILL.md`. Es un catálogo con instrucciones operativas, no una instalación automática en OpenCode ni en ChatGPT. Conservar este documento como referencia de preparación; evitar cargarlo completo en cada tarea.

Cada bloque de código contiene el contenido de una skill independiente. Su nombre y descripción indican cuándo seleccionarla. El formato de descubrimiento, las rutas de instalación y las opciones de activación deben comprobarse en la documentación oficial de la versión de OpenCode utilizada antes de instalar; este documento no prescribe una ruta de configuración no verificada.

## Principios comunes

- Respetar las instrucciones del usuario y las reglas vigentes del proyecto.
- Usar el stack existente; no imponer tecnologías desde una skill general.
- Mantener las reglas particulares de cada producto en sus especificaciones.
- Leer contexto y referencias de forma selectiva, ampliando la lectura si hay dudas o dependencias.
- No reducir controles de seguridad ni verificaciones necesarias para ahorrar tokens.
- No prometer porcentajes de ahorro: dependen del modelo, contexto y ejecución.
- No afirmar que un comando, prueba, publicación o integración tuvo éxito sin evidencia.
- Evitar incorporar secretos y datos personales a memorias, ejemplos y logs.

## Índice

1. [Inicio y contexto](#iniciar-proyecto)
2. [Planificación por fases](#planificar-fases)
3. [Continuidad y memoria](#mantener-continuidad)
4. [Diseño e implementación frontend](#implementar-frontend)
5. [Componentes y estilos compartidos](#mantener-componentes)
6. [Backend y API](#implementar-api)
7. [Base de datos y migraciones](#gestionar-base-datos)
8. [Autenticación y permisos](#implementar-permisos)
9. [Seguridad de aplicaciones](#revisar-seguridad)
10. [Documentos y evidencias](#gestionar-evidencias)
11. [Auditoría y trazabilidad](#registrar-auditoria)
12. [Pruebas y revisión funcional](#verificar-cambios)
13. [Diagnóstico de errores](#diagnosticar-errores)
14. [Revisión de cambios](#revisar-diff)
15. [Docker y despliegue](#preparar-despliegue)
16. [Respaldos y recuperación](#verificar-respaldos)
17. [Documentación técnica](#documentar-sistema)
18. [Informes y exportaciones](#generar-informes)
19. [Integraciones externas](#integrar-servicios)
20. [Funciones de IA](#integrar-ia)
21. [Gestión jurídica](#gestionar-juridico)
22. [Gestión SG-SST](#gestionar-sst)
23. [Inventarios y mantenimiento](#gestionar-activos)
24. [Seguimiento de metas municipales](#seguir-metas)
25. [DICOM y PACS](#integrar-dicom)
26. [Indicadores y calidad en salud](#medir-calidad-salud)
27. [Arquitectura multiempresa](#aislar-empresas)

## Selección y carga

Activar primero las skills de contexto y de la tarea concreta. Usar continuidad al cerrar. Incorporar seguridad, pruebas y revisión según el riesgo. No activar todas por defecto.

Prioridad inicial: iniciar-proyecto, mantener-continuidad, implementar-frontend, implementar-api, gestionar-base-datos, implementar-permisos, verificar-cambios y gestionar-evidencias.

El orquestador selecciona el alcance; frontend, backend y revisor consultan los procedimientos necesarios. Una skill no requiere un agente exclusivo. Resolver cambios pequeños con un solo agente.

## Relación con los archivos del proyecto

Buscar archivos equivalentes antes de crear otros. Utilizar `AGENTS.md` para reglas generales; el resumen, estado y handoff para continuidad; el Prompt Maestro y las especificaciones para requisitos; y el registro de decisiones para acuerdos duraderos. Las rutas concretas pertenecen a cada repositorio.

En WABOGADOS, consultar `WABOGADOS_web.html` para la web pública y las especificaciones del Motor de Evidencias para documentos. No convertir la paleta, módulos o reglas de WABOGADOS en requisitos de otros productos.

## Definiciones independientes

<a id="iniciar-proyecto"></a>

### 1. Inicio y contexto

```markdown
---
name: iniciar-proyecto
description: "Al iniciar o retomar un proyecto de software."
---

# Inicio y contexto

1. Leer AGENTS.md y los archivos de resumen, estado y handoff existentes.
2. Identificar stack, restricciones y tarea activa; resolver discrepancias con la fuente vigente.
3. Buscar las rutas pertinentes antes de ampliar la lectura.

## Entrega

Entregar objetivo inmediato, archivos pertinentes y dudas que bloqueen la tarea.
```

<a id="planificar-fases"></a>

### 2. Planificación por fases

```markdown
---
name: planificar-fases
description: "Al convertir requisitos en un plan de implementación."
---

# Planificación por fases

1. Identificar dependencias y resultados verificables.
2. Dividir el alcance en incrementos pequeños; separar lo actual de las fases futuras.
3. Definir criterios de aceptación y validación proporcionales al riesgo.

## Entrega

Entregar tareas ordenadas, dependencias y criterios de aceptación.
```

<a id="mantener-continuidad"></a>

### 3. Continuidad y memoria

```markdown
---
name: mantener-continuidad
description: "Al cerrar una tarea o preparar el relevo de una sesión."
---

# Continuidad y memoria

1. Actualizar el estado actual con resultados comprobados.
2. Reemplazar datos obsoletos; conservar decisiones duraderas en su archivo correspondiente.
3. Registrar archivos modificados, verificaciones, bloqueos y siguiente acción; excluir secretos.

## Entrega

Entregar un handoff breve, sin copiar conversaciones completas.
```

<a id="implementar-frontend"></a>

### 4. Diseño e implementación frontend

```markdown
---
name: implementar-frontend
description: "Al crear o modificar pantallas a partir de requisitos o referencias visuales."
---

# Diseño e implementación frontend

1. Leer la especificación de pantalla y los componentes cercanos.
2. Reproducir jerarquía, proporciones, colores y comportamiento de la referencia aprobada.
3. Implementar estados de carga, vacío, error y éxito; comprobar teclado y vista móvil.
4. Validar integración con la API sin simular éxito real.

## Entrega

Entregar pantalla implementada, validación visual y pendientes de integración.
```

<a id="mantener-componentes"></a>

### 5. Componentes y estilos compartidos

```markdown
---
name: mantener-componentes
description: "Al crear patrones visuales reutilizables o corregir inconsistencias."
---

# Componentes y estilos compartidos

1. Consultar los tokens y componentes existentes.
2. Consolidar patrones repetidos sin introducir abstracciones innecesarias.
3. Preservar contratos de componentes, accesibilidad y estados; revisar consumidores afectados.

## Entrega

Entregar componentes reutilizables y pantallas verificadas.
```

<a id="implementar-api"></a>

### 6. Backend y API

```markdown
---
name: implementar-api
description: "Al implementar endpoints, servicios y validaciones del backend."
---

# Backend y API

1. Consultar contratos, permisos y patrones del proyecto.
2. Validar entradas y aplicar reglas de negocio en el servidor.
3. Definir transacciones, errores consistentes y límites; evitar exponer información sensible.
4. Verificar casos permitidos, inválidos y accesos denegados.

## Entrega

Entregar endpoints, contratos actualizados y verificaciones.
```

<a id="gestionar-base-datos"></a>

### 7. Base de datos y migraciones

```markdown
---
name: gestionar-base-datos
description: "Al modificar esquemas, consultas o migraciones."
---

# Base de datos y migraciones

1. Inspeccionar modelos y secuencia vigente de migraciones.
2. Definir integridad, índices y compatibilidad con datos existentes.
3. Preparar migración y estrategia de recuperación; comprobar en entorno de prueba.
4. Revisar consultas y evitar operaciones destructivas fuera del alcance autorizado.

## Entrega

Entregar cambio de esquema, migración validada y límites de recuperación.
```

<a id="implementar-permisos"></a>

### 8. Autenticación y permisos

```markdown
---
name: implementar-permisos
description: "Al trabajar en acceso, sesiones, roles o autorización por registro."
---

# Autenticación y permisos

1. Consultar matriz de permisos y mecanismo de autenticación vigente.
2. Aplicar autorización en backend por operación, registro y organización cuando corresponda.
3. Gestionar caducidad, revocación y protección de credenciales con las herramientas del stack.
4. Probar acceso permitido, denegado y acceso cruzado entre usuarios o empresas.

## Entrega

Entregar reglas de acceso y evidencias de pruebas positivas y negativas.
```

<a id="revisar-seguridad"></a>

### 9. Seguridad de aplicaciones

```markdown
---
name: revisar-seguridad
description: "Al cambiar funciones sensibles o revisar una aplicación antes de publicar."
---

# Seguridad de aplicaciones

1. Delimitar superficie y amenazas vinculadas al cambio.
2. Revisar validación, secretos, sesiones, archivos privados y aislamiento de datos.
3. Consultar documentación oficial vigente cuando dependa de versiones o recomendaciones actuales.
4. Priorizar hallazgos reproducibles por impacto y corregir dentro del alcance.

## Entrega

Entregar hallazgos con evidencia, correcciones y riesgos pendientes.
```

<a id="gestionar-evidencias"></a>

### 10. Documentos y evidencias

```markdown
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
```

<a id="registrar-auditoria"></a>

### 11. Auditoría y trazabilidad

```markdown
---
name: registrar-auditoria
description: "Al añadir historial de acciones o cambios relevantes."
---

# Auditoría y trazabilidad

1. Definir eventos y campos útiles: actor, acción, objeto, fecha y correlación.
2. Evitar registrar contraseñas, tokens o contenido sensible innecesario.
3. Proteger el historial contra cambios no autorizados y definir retención.
4. Verificar que los eventos reflejen operaciones confirmadas y fallos relevantes.

## Entrega

Entregar eventos auditables, controles de acceso y validación.
```

<a id="verificar-cambios"></a>

### 12. Pruebas y revisión funcional

```markdown
---
name: verificar-cambios
description: "Al validar criterios de aceptación o cambios con riesgo de regresión."
---

# Pruebas y revisión funcional

1. Seleccionar verificaciones según comportamiento y riesgo.
2. Reutilizar herramientas existentes; probar errores y límites además del caso normal.
3. Ejecutar los controles pertinentes y distinguir resultados reales de pruebas no ejecutadas.
4. Evitar pruebas que solo repitan la implementación.

## Entrega

Entregar resultados, fallos y limitaciones de la cobertura.
```

<a id="diagnosticar-errores"></a>

### 13. Diagnóstico de errores

```markdown
---
name: diagnosticar-errores
description: "Al investigar un fallo reproducible o un incidente."
---

# Diagnóstico de errores

1. Recoger síntomas, versión, logs pertinentes y pasos de reproducción sin secretos.
2. Formular hipótesis y contrastarlas con evidencia.
3. Aplicar la corrección mínima que resuelva la causa y verificar el escenario original.
4. Actualizar continuidad y registrar incertidumbres.

## Entrega

Entregar causa comprobada o hipótesis pendiente, corrección y verificación.
```

<a id="revisar-diff"></a>

### 14. Revisión de cambios

```markdown
---
name: revisar-diff
description: "Al revisar código antes de integrarlo."
---

# Revisión de cambios

1. Leer el diff y los requisitos asociados.
2. Inspeccionar dependencias suficientes para evaluar comportamiento y seguridad.
3. Priorizar defectos concretos; indicar ubicación, impacto y reproducción.
4. No reescribir por preferencias de estilo ni afirmar ausencia total de errores.

## Entrega

Entregar hallazgos priorizados o alcance y límites de una revisión sin hallazgos.
```

<a id="preparar-despliegue"></a>

### 15. Docker y despliegue

```markdown
---
name: preparar-despliegue
description: "Al preparar contenedores, configuración o una publicación."
---

# Docker y despliegue

1. Consultar proveedor, infraestructura y procedimiento existentes.
2. Separar secretos del código; configurar healthchecks y versiones reproducibles.
3. Verificar construcción, arranque, migraciones y reversión en entorno adecuado.
4. Publicar únicamente dentro del alcance autorizado y comprobar salud posterior.

## Entrega

Entregar configuración, verificación y procedimiento de reversión.
```

<a id="verificar-respaldos"></a>

### 16. Respaldos y recuperación

```markdown
---
name: verificar-respaldos
description: "Al diseñar copias o comprobar restauraciones."
---

# Respaldos y recuperación

1. Definir datos, archivos, objetivos de recuperación y retención con el proyecto.
2. Proteger copias y credenciales; registrar resultados y alertas.
3. Restaurar en entorno aislado y comprobar consistencia entre base de datos y archivos.
4. No sobrescribir producción para probar una copia.

## Entrega

Entregar restauración comprobada y tiempos observados, no solo éxito del backup.
```

<a id="documentar-sistema"></a>

### 17. Documentación técnica

```markdown
---
name: documentar-sistema
description: "Al documentar instalación, configuración, contratos u operación."
---

# Documentación técnica

1. Consultar implementación y comandos reales.
2. Mantener una fuente por tema y enlazar detalles en vez de duplicarlos.
3. Documentar requisitos, pasos reproducibles y pendientes explícitos.
4. Verificar ejemplos y excluir secretos o datos personales.

## Entrega

Entregar documentación coherente con el estado implementado.
```

<a id="generar-informes"></a>

### 18. Informes y exportaciones

```markdown
---
name: generar-informes
description: "Al generar PDF, Word, Excel o reportes desde datos del sistema."
---

# Informes y exportaciones

1. Confirmar fuentes, filtros, permisos y reglas de cálculo.
2. Usar herramientas apropiadas al formato y proteger contra fórmulas inyectadas en exportaciones tabulares.
3. Comprobar totales, fechas, caracteres y trazabilidad de datos.
4. Renderizar documentos cuando importe la presentación y revisar páginas, tablas y cortes.

## Entrega

Entregar archivo validado y explicar filtros o límites relevantes.
```

<a id="integrar-servicios"></a>

### 19. Integraciones externas

```markdown
---
name: integrar-servicios
description: "Al conectar APIs, correo, almacenamiento u otros servicios."
---

# Integraciones externas

1. Consultar contratos y documentación oficial vigente.
2. Proteger credenciales; definir timeouts, reintentos acotados e idempotencia donde corresponda.
3. Verificar errores, duplicados y límites del proveedor.
4. No enviar mensajes ni ejecutar acciones externas fuera de la autorización del usuario.

## Entrega

Entregar integración verificable y comportamiento ante fallos.
```

<a id="integrar-ia"></a>

### 20. Funciones de IA

```markdown
---
name: integrar-ia
description: "Al incorporar modelos o recuperación de documentos en una aplicación."
---

# Funciones de IA

1. Definir tarea, datos permitidos, presupuesto y criterios de evaluación.
2. Tratar documentos y resultados del modelo como entradas no confiables.
3. Aplicar permisos antes de recuperar información; limitar exposición de datos y acciones de herramientas.
4. Evaluar calidad, latencia y costo con casos representativos; permitir revisión humana cuando corresponda.

## Entrega

Entregar función evaluada, métricas observadas y limitaciones.
```

<a id="gestionar-juridico"></a>

### 21. Gestión jurídica

```markdown
---
name: gestionar-juridico
description: "Al implementar clientes, expedientes, actuaciones y agenda de WABOGADOS."
---

# Gestión jurídica

1. Leer la especificación jurídica y matriz de acceso vigentes.
2. Relacionar actuaciones, responsables, documentos y clientes con el expediente correcto.
3. Separar información interna de la visible para clientes.
4. No inventar plazos judiciales ni interpretar normas sin fuente y validación profesional.

## Entrega

Entregar flujo jurídico con permisos y trazabilidad comprobados.
```

<a id="gestionar-sst"></a>

### 22. Gestión SG-SST

```markdown
---
name: gestionar-sst
description: "Al desarrollar riesgos, actividades, indicadores y evidencias de SST."
---

# Gestión SG-SST

1. Consultar reglas aprobadas y normativa vigente cuando la tarea dependa de ella.
2. Relacionar responsables, actividades, riesgos y evidencias.
3. Documentar fórmulas, fuentes y fechas de los indicadores.
4. No presentar automatización como certificación de cumplimiento legal.

## Entrega

Entregar función trazable y supuestos pendientes de validación profesional.
```

<a id="gestionar-activos"></a>

### 23. Inventarios y mantenimiento

```markdown
---
name: gestionar-activos
description: "Al implementar activos, movimientos u órdenes de mantenimiento."
---

# Inventarios y mantenimiento

1. Consultar reglas de identificación, ubicación y estados.
2. Mantener consistencia entre activos, custodios, movimientos y órdenes.
3. Controlar concurrencia y autorizaciones en cambios relevantes.
4. Verificar historial y cierres sin borrar trazabilidad.

## Entrega

Entregar flujo de activos consistente y auditable.
```

<a id="seguir-metas"></a>

### 24. Seguimiento de metas municipales

```markdown
---
name: seguir-metas
description: "Al implementar productos, avances e informes del plan municipal."
---

# Seguimiento de metas municipales

1. Leer estructura aprobada de líneas, programas, productos y responsables.
2. Definir unidad, línea base, meta, período y regla de cálculo.
3. Separar avance reportado, validado y aprobado; vincular evidencias.
4. Comprobar agregaciones y evitar mezclar porcentajes incompatibles.

## Entrega

Entregar indicadores reproducibles con fuente, período y aprobación.
```

<a id="integrar-dicom"></a>

### 25. DICOM y PACS

```markdown
---
name: integrar-dicom
description: "Al trabajar en estudios, series, imágenes o integración con PACS."
---

# DICOM y PACS

1. Consultar esquema, documentación primaria y restricciones del entorno.
2. Preservar identificadores y relaciones DICOM; proteger datos de pacientes.
3. Verificar transferencia, orden de instancias y comportamiento del visor.
4. No modificar identidad clínica ni estudios productivos sin alcance y procedimiento autorizados.

## Entrega

Entregar integración validada y limitaciones clínicas o técnicas explícitas.
```

<a id="medir-calidad-salud"></a>

### 26. Indicadores y calidad en salud

```markdown
---
name: medir-calidad-salud
description: "Al implementar indicadores clínicos o administrativos de salud."
---

# Indicadores y calidad en salud

1. Consultar definición aprobada de numerador, denominador, fuente y período.
2. Validar completitud, duplicados y datos faltantes.
3. Aplicar permisos y minimizar datos personales.
4. Verificar resultados con ejemplos calculados y revisión del responsable.

## Entrega

Entregar indicador reproducible y limitaciones de los datos.
```

<a id="aislar-empresas"></a>

### 27. Arquitectura multiempresa

```markdown
---
name: aislar-empresas
description: "Al implementar separación de datos en un SaaS."
---

# Arquitectura multiempresa

1. Identificar empresa desde un contexto autenticado y validado.
2. Aplicar aislamiento en consultas, escrituras, archivos, cachés y trabajos asíncronos.
3. Revisar restricciones de base de datos y operaciones administrativas.
4. Probar accesos cruzados usando identificadores conocidos y solicitudes manipuladas.

## Entrega

Entregar aislamiento comprobado en casos permitidos y denegados.
```

## Preparación para uso real

1. Seleccionar las skills que el proyecto necesita.
2. Separar cada bloque elegido en su propio `SKILL.md`; no guardar el catálogo completo como una sola skill.
3. Añadir referencias o scripts solo cuando hagan falta. Enlazar cada referencia desde su skill y explicar cuándo consultarla.
4. Verificar el descubrimiento y los nombres en la instalación de OpenCode utilizada.
5. Probar cada procedimiento en una tarea pequeña del proyecto; revisar que no introduzca tecnologías, permisos o requisitos ajenos.
6. Versionar las definiciones junto con el proyecto o en un repositorio de skills reutilizables.
7. Ajustar a partir de resultados reales, evitando duplicar el Prompt Maestro.

## Instrucción para tu IA

> Lee las reglas y el estado vigente del proyecto. Selecciona las skills pertinentes del catálogo y prepara sus archivos independientes según la configuración verificada de esta instalación. Conserva las especificaciones particulares en el proyecto. No cargues todas las skills en cada tarea. Implementa el alcance autorizado, verifica el resultado y actualiza la continuidad.

## Criterios de aceptación del catálogo

- Las 27 skills tienen nombre, descripción, procedimiento y entrega.
- Las skills generales pueden reutilizarse sin copiar requisitos de WABOGADOS.
- Las skills de dominio se seleccionan únicamente para su producto correspondiente.
- La preparación de archivos no equivale a instalación: comprobar descubrimiento antes de afirmar que están activas.
