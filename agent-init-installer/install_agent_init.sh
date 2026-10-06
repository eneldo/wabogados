#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/agent-init"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo
echo "=============================================="
echo " Instalador global agent-init"
echo "=============================================="
echo

mkdir -p "$BIN_DIR"
mkdir -p "$SHARE_DIR"

cp "$SCRIPT_DIR/agent-init" "$BIN_DIR/agent-init"
cp "$SCRIPT_DIR/MASTER_AGENT.md" "$SHARE_DIR/MASTER_AGENT.md"
cp "$SCRIPT_DIR/bootstrap_agent.py" "$SHARE_DIR/bootstrap_agent.py"
cp "$SCRIPT_DIR/sync_agent_files.py" "$SHARE_DIR/sync_agent_files.py"

chmod +x "$BIN_DIR/agent-init"
chmod +x "$SHARE_DIR/bootstrap_agent.py"
chmod +x "$SHARE_DIR/sync_agent_files.py"

SHELL_RC=""
case "${SHELL##*/}" in
  bash) SHELL_RC="$HOME/.bashrc" ;;
  zsh) SHELL_RC="$HOME/.zshrc" ;;
esac

PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

if [[ -n "$SHELL_RC" ]]; then
  touch "$SHELL_RC"
  if ! grep -Fqx "$PATH_LINE" "$SHELL_RC"; then
    printf '\n# agent-init\n%s\n' "$PATH_LINE" >> "$SHELL_RC"
    echo "[UPDATE] $SHELL_RC"
  else
    echo "[OK] $SHELL_RC ya contiene ~/.local/bin"
  fi
fi

echo
echo "[OK] Instalado:"
echo "     $BIN_DIR/agent-init"
echo "     $SHARE_DIR/"
echo
echo "Para usarlo en esta terminal:"
echo
echo '    export PATH="$HOME/.local/bin:$PATH"'
echo
echo "Luego:"
echo
echo "    cd /ruta/de/tu/proyecto"
echo "    agent-init --dry-run"
echo "    agent-init"
echo
echo "Verificación:"
echo
echo "    agent-init --check"
echo
