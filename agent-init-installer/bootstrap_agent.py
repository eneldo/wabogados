#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path.cwd()

DIRECTORIES = [
    ".agent", "memory", "memory/history", "directives", "execution",
    "decisions", "errors", "architecture", "docs", "tests", "logs", ".tmp",
]

FILES = {
    "memory/README.md": """# Memoria Persistente

Esta carpeta contiene conocimiento persistente del proyecto.
No utilizarla como log exhaustivo.
""",
    "memory/project_context.md": """# Contexto del Proyecto

## Objetivo
Pendiente de analizar.

## Estado actual
Pendiente de analizar.

## Arquitectura
Pendiente de analizar.

## Backend
Pendiente de analizar.

## Frontend
Pendiente de analizar.

## Base de datos
Pendiente de analizar.

## Infraestructura
Pendiente de analizar.

## Servicios externos
Pendiente de analizar.

## Seguridad
Pendiente de analizar.

## Funcionalidades terminadas
Pendiente.

## Funcionalidades pendientes
Pendiente.

## Riesgos conocidos
Pendiente.
""",
    "memory/learnings.md": """# Aprendizajes del Agente

Los aprendizajes más recientes deben agregarse arriba.

Formato:

- **YYYY-MM-DD — Tema:**
  **Contexto:** qué ocurrió.
  **Aprendizaje:** qué se descubrió.
  **Aplicación futura:** cómo aplicar este conocimiento.

---

<!-- Nuevos aprendizajes debajo de esta línea -->
""",
    "memory/conventions.md": "# Convenciones del Proyecto\n\nRegistrar convenciones estables.\n",
    "memory/user_preferences.md": "# Preferencias del Proyecto\n\nRegistrar preferencias técnicas y operativas estables.\n",
    "memory/known_issues.md": """# Problemas Conocidos

### ISSUE-XXXX — Título

**Estado:** OPEN / MITIGATED / RESOLVED

**Síntoma:**

**Causa:**

**Solución o mitigación:**

**Prevención:**
""",
    "memory/solutions.md": "# Soluciones Verificadas\n\nSoluciones técnicas reutilizables comprobadas.\n",
    "memory/environment.md": """# Entorno

## Sistema operativo
Pendiente.

## Python
Pendiente.

## Node.js
Pendiente.

## Docker
Pendiente.

## Base de datos
Pendiente.

## Servicios
Pendiente.

Nunca almacenar secretos en este archivo.
""",
    "memory/dependencies.md": "# Dependencias Importantes\n\nRegistrar dependencias críticas y compatibilidades.\n",
    "memory/patterns.md": "# Patrones Reutilizables\n\nRegistrar patrones técnicos verificados.\n",
    "memory/session_summary.md": f"""# Última sesión

Fecha: {date.today().isoformat()}

## Objetivo trabajado
Inicialización del sistema de agente persistente.

## Cambios realizados
Preparación de memoria, directivas y sincronización.

## Problemas encontrados
Ninguno registrado.

## Estado actual
Workspace preparado para aprendizaje continuo.

## Pendientes
Analizar el proyecto real y completar `memory/project_context.md`.

## Próximo paso recomendado
Ejecutar análisis inicial del repositorio.
""",
    "directives/README.md": "# Directivas\n\nProcedimientos operativos reutilizables del proyecto.\n",
    "directives/development.md": """# Desarrollo

1. comprender requisito;
2. consultar memoria;
3. inspeccionar código;
4. localizar implementación existente;
5. realizar cambio mínimo;
6. validar;
7. ejecutar pruebas;
8. registrar aprendizajes relevantes.
""",
    "directives/debugging.md": """# Depuración

1. reproducir el problema;
2. capturar error;
3. leer stack trace;
4. consultar problemas conocidos;
5. identificar causa raíz;
6. aplicar corrección mínima;
7. verificar;
8. crear test de regresión cuando corresponda;
9. registrar aprendizaje reutilizable.
""",
    "directives/testing.md": """# Testing

No inventar comandos. Consultar primero:
- package.json
- pyproject.toml
- Makefile
- README
- scripts existentes
""",
    "directives/deployment.md": """# Deployment

No realizar despliegues destructivos sin verificar:
- configuración;
- variables;
- backups;
- servicios;
- migraciones;
- health checks;
- rollback.
""",
    "directives/security.md": """# Seguridad

Nunca versionar secretos.
Verificar `.env`, credenciales, permisos, dependencias, servicios y logs sensibles.
""",
    "decisions/README.md": "# Architecture Decision Records\n\nUsar ADR-0001-nombre.md.\n",
    "errors/README.md": "# Registro de Errores\n\nSolo errores importantes o recurrentes.\n",
    "errors/recurring_errors.md": "# Errores Recurrentes\n",
    "errors/resolved_errors.md": "# Errores Resueltos\n",
    "architecture/README.md": "# Arquitectura\n\nDocumentación de arquitectura del sistema.\n",
    ".env.example": "# Copiar a .env y completar localmente.\n",
}

GITIGNORE_ENTRIES = [
    ".env", ".env.*", "!.env.example", ".tmp/", "logs/", "__pycache__/",
    "*.pyc", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
    "credentials.json", "token.json",
]

def create_dir(path: Path, dry: bool) -> None:
    if path.exists():
        print(f"[OK]     {path.relative_to(ROOT)}/")
        return
    print(f"[CREATE] {path.relative_to(ROOT)}/")
    if not dry:
        path.mkdir(parents=True, exist_ok=True)

def create_file(path: Path, content: str, dry: bool) -> None:
    if path.exists():
        print(f"[KEEP]   {path.relative_to(ROOT)}")
        return
    print(f"[CREATE] {path.relative_to(ROOT)}")
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

def update_gitignore(dry: bool) -> None:
    path = ROOT / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    additions = [e for e in GITIGNORE_ENTRIES if e not in lines]
    if not additions:
        print("[OK]     .gitignore")
        return
    print(f"[UPDATE] .gitignore (+{len(additions)})")
    if not dry:
        text = existing.rstrip()
        if text:
            text += "\n\n"
        text += "# Agent workspace / secrets\n" + "\n".join(additions) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print(f"\nProyecto: {ROOT}\n")
    for d in DIRECTORIES:
        create_dir(ROOT / d, args.dry_run)
    for rel, content in FILES.items():
        create_file(ROOT / rel, content, args.dry_run)
    update_gitignore(args.dry_run)

if __name__ == "__main__":
    main()
