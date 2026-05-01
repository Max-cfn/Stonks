#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  install-systemd.sh — Installe les services systemd Stonks           ║
# ║                                                                      ║
# ║  Lance avec : sudo bash scripts/install-systemd.sh                   ║
# ║                                                                      ║
# ║  Crée :                                                              ║
# ║   - stonks-ui.service       (UI Streamlit, daemon H24)               ║
# ║   - stonks-brief@.service   (template, lancé à la demande)           ║
# ║                                                                      ║
# ║  Idempotent : peut être relancé sans casser ce qui marche.           ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "❌ Lance ce script avec sudo : sudo bash scripts/install-systemd.sh"
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "═════════════════════════════════════════════════════"
echo "  Installation des services systemd Stonks"
echo "═════════════════════════════════════════════════════"

# 1. UI service
echo "▶ Installation de stonks-ui.service"
cp "$REPO_ROOT/infra/systemd/stonks-ui.service" "$SYSTEMD_DIR/stonks-ui.service"

# 2. Brief runner (template)
echo "▶ Installation de stonks-brief@.service (template)"
cp "$REPO_ROOT/infra/systemd/stonks-brief@.service" "$SYSTEMD_DIR/stonks-brief@.service"

# 3. Queue runner
echo "▶ Installation de stonks-queue.service"
cp "$REPO_ROOT/infra/systemd/stonks-queue.service" "$SYSTEMD_DIR/stonks-queue.service"

# 4. Reload systemd
systemctl daemon-reload

# 5. Enable + start UI (le seul qui doit tourner H24)
echo "▶ Activation de stonks-ui (boot + auto-restart)"
systemctl enable --now stonks-ui.service

# 6. Status
sleep 2
echo ""
echo "═════════════════════════════════════════════════════"
systemctl status stonks-ui.service --no-pager -l | head -10
echo "═════════════════════════════════════════════════════"
echo ""
echo "✅ Services systemd installés."
echo ""
echo "Commandes utiles :"
echo "  task ui:status        # état de l'UI"
echo "  task ui:logs          # tail -f des logs UI"
echo "  task ui:restart       # forcer un redémarrage"
echo "  task brief:start -- 2026-04-29_demo  # lance un brief résilient au reboot"
echo "  task brief:status -- 2026-04-29_demo # état du brief"
echo "  task brief:stop -- 2026-04-29_demo   # arrêt propre du brief"
echo ""
echo "URL de l'UI : http://$(hostname -I | awk '{print $1}'):8501"
