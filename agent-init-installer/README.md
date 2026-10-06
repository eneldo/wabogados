# agent-init

Instalador global para preparar proyectos con memoria persistente multi-IA.

## Instalación

```bash
chmod +x install_agent_init.sh
./install_agent_init.sh
export PATH="$HOME/.local/bin:$PATH"
```

## Uso en un proyecto existente

```bash
cd /ruta/al/proyecto
agent-init --dry-run
agent-init
agent-init --check
```

## Uso indicando la ruta

```bash
agent-init /ruta/al/proyecto
```

## Archivos creados

- `.agent/MASTER_AGENT.md`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `memory/`
- `directives/`
- `execution/`
- `decisions/`
- `errors/`
- `architecture/`
- `.tmp/`

## Regla principal

Editar únicamente `.agent/MASTER_AGENT.md` para instrucciones globales y después ejecutar:

```bash
python3 execution/sync_agent_files.py
```

## Verificar sincronización

```bash
agent-init --check
```

## Actualizar la plantilla global

Los archivos globales viven en:

```text
~/.local/share/agent-init/
```

El comando vive en:

```text
~/.local/bin/agent-init
```
