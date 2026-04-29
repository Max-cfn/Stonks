#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Stonks — Bootstrap script                                           ║
# ║                                                                      ║
# ║  Setup complet de l'environnement de dev sur une machine vierge.     ║
# ║  Idempotent : tu peux le relancer sans casser ce qui marche.         ║
# ║                                                                      ║
# ║  Pré-requis :                                                        ║
# ║    - Ubuntu 22+ ou Debian 12+                                        ║
# ║    - sudo accessible                                                 ║
# ║    - Node 20+ et pnpm 10+ déjà présents                              ║
# ║    - Python 3.12 et pip                                              ║
# ║                                                                      ║
# ║  Usage : bash scripts/bootstrap.sh                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '✅ %s\n' "$*"; }
warn() { printf '⚠️  %s\n' "$*"; }
fail() { printf '❌ %s\n' "$*" >&2; exit 1; }

bold "═══════════════════════════════════════════════════════════"
bold "  Stonks — Bootstrap"
bold "═══════════════════════════════════════════════════════════"

# 1. Vérification des outils de base
bold "▶ Vérification des outils"
command -v node      >/dev/null || fail "node manquant (besoin de >= 20)"
command -v pnpm      >/dev/null || fail "pnpm manquant (besoin de >= 10)"
command -v python3   >/dev/null || fail "python3 manquant"
command -v git       >/dev/null || fail "git manquant"
command -v task      >/dev/null || warn "task pas trouvé — installe via : sudo snap install task --classic"
command -v gh        >/dev/null || warn "gh CLI pas trouvé (optionnel pour les PR)"
ok "node $(node -v) | pnpm $(pnpm -v) | python $(python3 -V | awk '{print $2}')"

# 2. Install uv si absent
if ! command -v uv >/dev/null; then
    bold "▶ Installation de uv (Python package manager)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version | awk '{print $2}')"

# 3. Création du .env si absent
if [ ! -f .env ]; then
    bold "▶ Création de .env depuis .env.example"
    cp .env.example .env
    warn "⚠️  Édite .env et remplis OPENROUTER_API_KEY avant de lancer l'orchestrateur."
else
    ok ".env existe déjà (préservé)"
fi

# 4. Install des deps JS
bold "▶ Installation des deps JS (pnpm)"
pnpm install --frozen-lockfile=false
ok "deps JS installées"

# 5. Setup du venv Python pour les agents
bold "▶ Setup du venv Python (agents_core/)"
cd "$REPO_ROOT/agents_core"
if [ ! -d .venv ]; then
    uv venv --python 3.12 .venv
fi
.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true
uv pip install --python .venv/bin/python -e ".[dev]"
ok "venv Python prêt"

# 6. Création des dossiers runtime
cd "$REPO_ROOT"
mkdir -p agents_core/runtime/{approvals,runs,checkpoints} docs/briefs
touch execution_log.txt
ok "dossiers runtime créés"

# 7. Install GitNexus si absent
if ! command -v gitnexus >/dev/null; then
    bold "▶ Installation de GitNexus (knowledge graph code-review)"
    if command -v sudo >/dev/null && [ "$EUID" -ne 0 ]; then
        sudo npm install -g gitnexus@latest || warn "Échec install GitNexus (non bloquant pour Phase 1)"
    else
        npm install -g gitnexus@latest || warn "Échec install GitNexus (non bloquant pour Phase 1)"
    fi
fi
command -v gitnexus >/dev/null && ok "gitnexus $(gitnexus --version 2>/dev/null | head -1 || echo installé)"

# 8. Validation finale
bold "▶ Vérification de la config (dry-run)"
cd "$REPO_ROOT/agents_core"
if .venv/bin/python -c "from stonks_core.orchestrator.config import get_settings; get_settings()" 2>/dev/null; then
    ok "config Python OK"
else
    warn "config Python invalide — vérifie .env (notamment OPENROUTER_API_KEY)"
fi

bold "═══════════════════════════════════════════════════════════"
bold "  ✅ Bootstrap terminé"
bold "═══════════════════════════════════════════════════════════"
echo ""
echo "Prochaines étapes :"
echo "  1. nano .env                              # mets ta clé OpenRouter"
echo "  2. task agents:dry-run                    # valide la config"
echo "  3. task ui                                # lance l'UI Streamlit (http://localhost:8501)"
echo ""
echo "Voir docs/QUICKSTART.md pour le guide complet."
