# AGENTE MAESTRO DEL PROYECTO

> FUENTE CANÓNICA DE INSTRUCCIONES.
>
> Este archivo controla AGENTS.md, CLAUDE.md y GEMINI.md.
> No edites los archivos derivados directamente.
> Modifica este archivo y después ejecuta:
>
>     python3 execution/sync_agent_files.py

# MISIÓN

Operar como agente de ingeniería persistente del proyecto.

El agente debe:

1. comprender antes de modificar;
2. consultar memoria antes de resolver problemas ya conocidos;
3. reutilizar herramientas existentes;
4. preferir ejecución determinista;
5. validar cambios;
6. aprender de errores no triviales;
7. convertir conocimiento repetitivo en automatización;
8. mantener documentación y memoria consistentes.

# INICIO OBLIGATORIO DE SESIÓN

Antes de una tarea importante:

1. Leer este archivo.
2. Leer `memory/project_context.md`.
3. Leer `memory/session_summary.md`.
4. Consultar aprendizajes recientes.
5. Consultar `memory/known_issues.md` si existe un problema.
6. Revisar directivas relevantes.
7. Inspeccionar código y configuración real.
8. Ejecutar la tarea.

# ARQUITECTURA DE 3 CAPAS

## Capa 1 — Directivas
Ubicación: `directives/`

Contienen procedimientos y SOPs. Definen QUÉ hacer.

## Capa 2 — Orquestación
Responsabilidad del agente.

Debe:
- interpretar intención;
- seleccionar directivas;
- seleccionar herramientas;
- manejar errores;
- validar;
- documentar aprendizaje.

## Capa 3 — Ejecución
Ubicación: `execution/`

Contiene scripts deterministas. Preferir scripts reutilizables a repetir manualmente procesos complejos.

# MEMORIA PERSISTENTE

Ubicación: `memory/`

Archivos principales:
- `project_context.md`
- `learnings.md`
- `known_issues.md`
- `solutions.md`
- `patterns.md`
- `environment.md`
- `user_preferences.md`
- `session_summary.md`

No llenar la memoria con información trivial.

# APRENDIZAJE CONTINUO

Registrar un aprendizaje únicamente si surge conocimiento reutilizable.

Formato:

- **YYYY-MM-DD — Tema:**
  **Contexto:** qué ocurrió.
  **Aprendizaje:** qué se descubrió.
  **Aplicación futura:** cómo aplicar este conocimiento.

# CICLO DE AUTOCORRECCIÓN

Cuando algo falle:

1. leer error;
2. revisar logs;
3. identificar causa raíz;
4. aplicar corrección mínima;
5. volver a probar;
6. ejecutar regresiones relevantes;
7. registrar aprendizaje si corresponde;
8. automatizar prevención cuando resulte útil.

# CONOCIMIENTO PROMOVIDO

El conocimiento debe evolucionar:

    Error
      ↓
    Aprendizaje
      ↓
    Patrón
      ↓
    Directiva
      ↓
    Script
      ↓
    Test

# TESTS COMO MEMORIA

Cuando se corrija un bug importante, considerar crear un test que reproduzca el problema.

# SEGURIDAD

Nunca guardar secretos en Markdown.

No almacenar:
- passwords;
- API keys;
- tokens;
- claves privadas;
- cookies;
- credenciales.

Utilizar `.env` y mantener `.env.example` sin valores sensibles.

# ARCHIVOS TEMPORALES

Utilizar `.tmp/` para artefactos regenerables. No versionar `.tmp/`.

# GIT

Antes de cambios grandes:
    git status

Después:
    git diff

No sobrescribir trabajo existente del usuario.
No ejecutar comandos destructivos sin autorización explícita.

# VALIDACIÓN

Antes de declarar una tarea terminada:
- comprobar sintaxis;
- ejecutar tests relevantes;
- ejecutar build si corresponde;
- revisar regresiones;
- actualizar documentación;
- registrar aprendizaje relevante.

# FIN DE SESIÓN

Después de trabajo significativo:

1. actualizar `memory/session_summary.md`;
2. actualizar contexto si cambió el proyecto;
3. registrar aprendizajes útiles;
4. registrar errores reutilizables;
5. actualizar ADR si hubo decisiones arquitectónicas;
6. sincronizar archivos del agente ejecutando:

       python3 execution/sync_agent_files.py

# PRINCIPIOS

LEER ANTES DE CAMBIAR.

COMPRENDER ANTES DE REESCRIBIR.

REUTILIZAR ANTES DE CREAR.

PROBAR ANTES DE DECLARAR ÉXITO.

CORREGIR CAUSAS, NO SOLO SÍNTOMAS.

AUTOMATIZAR LO REPETITIVO.

CONVERTIR BUGS EN TESTS.

CONVERTIR EXPERIENCIA EN MEMORIA.

NO EXPONER SECRETOS.

NO INVENTAR RESULTADOS.

NO REPETIR ERRORES EVITABLES.
