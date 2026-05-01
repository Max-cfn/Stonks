# Agent Protocol — Comment parler à l'orchestrateur

Ce document décrit **les 3 manières d'interagir** avec l'Orchestrateur Stonks, et le **format de brief** attendu pour les missions sérieuses.

---

## TL;DR

| Tu veux… | Utilise |
|---|---|
| Discuter, poser une question, faire un mini-test | **💬 Chat** dans l'UI Streamlit |
| Lancer une mission de plusieurs heures | **📝 Brief autonome** dans l'UI Streamlit |
| Débugger une commande dans le terminal | `task agents:dev` |

Tout ça pointe sur le **même orchestrateur**. La différence : le mode chat est synchrone (tu attends la réponse dans le browser), le mode autonome lance un subprocess détaché (tu peux fermer l'UI).

---

## Mode 1 — Chat live (90 % du temps)

```bash
task ui
```

Puis ouvre **http://serveurmax:8501** dans ton browser.

Section **💬 Chat** par défaut. Tu causes, il répond. Comme ChatGPT, sauf que c'est **ton** orchestrateur DeepSeek V4 Pro qui tourne sur ton serveur, avec accès à :

- ton repo `/opt/stonks/` (lecture/écriture/git)
- ton terminal (`shell_exec` avec allowlist)
- GitNexus (analyse d'impact avant tout changement)
- la délégation à des sous-agents

Chaque réponse affiche les **tool calls** (🔧) et leurs **résultats** (↳) en direct, comme dans Claude.ai. Tu vois ce qu'il fait au moment où il le fait.

Bouton **🔄 Nouveau chat** = reset le contexte (nouveau thread LangGraph).

### Exemples d'usage chat
- *"Liste les fichiers dans agents_core/ et résume leur rôle"*
- *"Vérifie que pnpm install passe sur apps/web"*
- *"Quelle est ta config OpenRouter actuelle ?"*
- *"Crée une branche `agent/backend/test-graph` et fais un commit vide"*

⚠️ **Le chat est synchrone**. Si tu lui donnes une tâche de 2 h, l'UI bloque. Pour ça → mode autonome.

---

## Mode 2 — Brief autonome (missions longues)

Section **📝 Brief autonome** dans l'UI.

1. Tu rédiges un brief en Markdown (template ci-dessous)
2. Tu cliques **▶️ Envoyer à l'orchestrateur**
3. L'UI lance un **subprocess détaché** (PID affiché)
4. Tu peux fermer l'UI, l'orchestrateur continue
5. Tu surveilles dans **📜 Logs** ou avec `tail -f execution_log.txt`
6. Quand il a besoin de ton OK, il bloque et apparaît dans **⏳ Approbations**

Si tu préfères la ligne de commande :
```bash
cp docs/briefs/_template.md docs/briefs/2026-04-29_cashflow.md
nano docs/briefs/2026-04-29_cashflow.md
task agents:run -- --brief docs/briefs/2026-04-29_cashflow.md
```

### Format de brief obligatoire

```markdown
# Brief — [titre court]

## Objectif
<phrase claire, 1-2 lignes — quoi, pas pourquoi>

## Contexte
<décisions déjà prises, contraintes, fichiers concernés, refs externes>

## Critères d'acceptation
- [ ] Critère 1 mesurable
- [ ] Critère 2 mesurable
- [ ] Critère 3 mesurable

## Hors-périmètre
- Ce que tu NE veux PAS qu'il touche
- Branches qu'il ne doit pas casser

## Mode d'exécution
mode: autonomous_long_run     # ou "interactive"
budget_usd_max: 20            # plafond OpenRouter
human_checkpoint_every_steps: 25
```

Le template complet est dans [`docs/briefs/_template.md`](./briefs/_template.md).

### Workflow imposé à l'orchestrateur

À réception du brief, **l'orchestrateur ne commence pas à coder**. Il :

1. **Produit un PLAN** numéroté (steps, agent assigné, durée estimée, livrables)
2. **Soumet le plan à ton approbation** via `request_human_approval`
3. **Attend ton OK** dans la section ⏳ Approbations
4. **Seulement après** dispatche aux sous-agents

À chaque `human_checkpoint_every_steps` étapes, il résume l'avancée dans `execution_log.txt`.

---

## Mode 3 — REPL terminal (debug)

```bash
ssh max@serveurmax
cd /opt/stonks
task agents:dev
```

Prompt s'ouvre, tu causes en français, il répond. Utile quand tu veux tester une commande sans passer par le browser.

Commandes spéciales :
- `exit` → quitter
- `reset` → repartir d'un thread vierge

---

## Système d'approbations (request_human_approval)

L'orchestrateur **bloque** et demande ton OK pour :

- Force push, suppression de branche, rewrite d'historique
- Suppression de migration DB ou rollback
- Installation de package global (apt, npm -g, pip --user)
- Modification de `.env.example` ou ajout de variables
- Ouverture d'un port < 1024
- Toute requête LLM dont le coût estimé > $5
- Modification du system prompt

### Comment répondre

#### Via l'UI
Section **⏳ Approbations** → bouton **✅ Approuver** ou **⛔ Rejeter** + commentaire optionnel.

#### Via le terminal
```bash
task agents:status                       # liste les req_id en attente
task agents:approve -- <req_id> "go"
task agents:reject  -- <req_id> "non, fais autrement"
```

Timeout par défaut : **30 minutes**. Au-delà, la demande passe en `timeout` et l'orchestrateur escalade ou abandonne.

---

## Règles que l'orchestrateur s'auto-impose

(Encodées dans le system prompt — ne pas les modifier sans `request_human_approval`.)

1. **Log obligatoire** : tout side-effect dans `execution_log.txt` (avant + après)
2. **GitNexus avant modif structurelle** : impact analysis sur tout rename/suppression/refactor
3. **Code-review systématique** : aucun merge sans le Reviewer Agent
4. **Anti-hallucination** : jamais de fichier "supposé exister" — toujours `file_read` avant
5. **Anti-boucle** : 3 fois la même action sans progrès → escalade humain
6. **Sandbox** : écritures limitées à `/opt/stonks/`, shell sur allowlist
7. **Commits atomiques** : un commit = une intention, format Conventional Commits
8. **Branches courtes** : `agent/<role>/<phase>/<slug>`, mergées par PR
9. **Tests obligatoires** sur crypto, calculs financiers, parsing PSD2 (≥80% coverage)
10. **Secrets jamais en clair** : `.env` et Vault uniquement

---

## 🌙 Autonomie H24 — fonctionnement quand tu n'es pas là

Tu peux totalement laisser Stonks tourner sans toi. Voici **ce qui résiste à quoi** :

| Scénario | UI Streamlit | Brief lancé via UI | Brief lancé via systemd |
|---|---|---|---|
| Tu fermes ton browser | ✅ continue | ✅ continue | ✅ continue |
| Tu fermes ton SSH | ✅ continue | ✅ continue | ✅ continue |
| L'UI crash | ✅ redémarre auto (5 s) | ✅ continue | ✅ continue |
| Le serveur reboot | ✅ redémarre auto au boot | ❌ meurt | ✅ relance possible |
| Coupure réseau | ✅ continue (LAN) | ✅ continue | ✅ continue |
| OOM kill | ✅ redémarre auto | ❌ meurt | ⚠️ ne redémarre pas auto |

### Mise en place de l'autonomie

```bash
# Une fois suffit — installe les services systemd (UI + brief template)
sudo task ui:install
```

À partir de là :
- **UI** tourne H24 sur `http://serveurmax:8501`, redémarre toute seule si elle plante, redémarre au boot du serveur
- Tu peux fermer ton SSH, rentrer chez toi, l'UI reste joignable

### Pour les briefs vraiment longs (résistants au reboot)

L'UI permet de lancer un brief en subprocess (✅ survit à fermeture de l'UI mais ❌ meurt au reboot). Pour un brief qui doit **vraiment** tourner même si tu reboot le serveur, utilise systemd directement :

```bash
# 1. Crée ton brief
cp docs/briefs/_template.md docs/briefs/2026-04-29_phase2.md
nano docs/briefs/2026-04-29_phase2.md

# 2. Lance-le comme service systemd
task brief:start -- 2026-04-29_phase2

# 3. Surveillance
task brief:status -- 2026-04-29_phase2     # statut + dernières lignes
task brief:logs -- 2026-04-29_phase2       # tail -f journalctl
task brief:list                            # tous les briefs en cours

# 4. Stop manuel si besoin
task brief:stop -- 2026-04-29_phase2
```

Note : un brief systemd ne **redémarre pas auto** s'il termine ou crash (ce serait une boucle infinie). Si le serveur reboot pendant que le brief tournait, tu dois le relancer manuellement à ton retour avec `task brief:start --`. La reprise transparente après crash arrive en Phase 2 (Redis + worker watchdog).

### Configurer un brief pour 24h sans humain

Dans le brief Markdown, en section `Mode d'exécution` :

```yaml
mode: autonomous_long_run
budget_usd_max: 20
human_checkpoint_every_steps: 50      # résumé tous les 50 steps
approval_timeout_minutes: 720         # 12h avant timeout d'une approbation
escalation_policy: minimal            # n'escalade que sur erreur bloquante ou choix critique
```

Si tu mets `escalation_policy: minimal` et `approval_timeout_minutes: 720`, l'orchestrateur tranchera tout seul tant qu'il peut, et n'attendra ton OK que pour les actions destructives (suppression de migration, force push, etc.). Si tu n'es pas là sous 12h pour répondre, la demande passe en `timeout` et il abandonne cette action puis continue le reste.

### Ce qu'il faut savoir avant de partir au lit

1. **Le coût LLM peut grimper en 8h** — même à 2 tokens/sec, un orchestrateur reasoning_effort=high peut consommer $5-10 par heure de bouclage actif. **Toujours mettre un `budget_usd_max`** dans le brief.
2. **Le quota OpenRouter** est sur ton compte → vérifie ton crédit avant : https://openrouter.ai/credits
3. **Le serveur partage la RAM** avec ton Minecraft ATM10 (10 Go). Si la mission est lourde, coupe le serv MC avant de partir : `sudo systemctl stop minecraft-atm10` (ou ton script habituel).
4. **`execution_log.txt` grossit vite** — pour 8h d'autonomie, prévois ~50-200 Mo. Le log est rotaté/archivé par le script `clean` mais pas en automatique.

### Diagnostic à ton retour

```bash
task ui:status                              # UI alive ?
task brief:list                             # quels briefs ont tourné ?
task agents:tail                            # 20 dernières actions
grep '"action": "error"' execution_log.txt | tail -10   # erreurs ?
grep '"human_intervention": true' execution_log.txt     # approbations en attente ?
```

Ou plus simple : ouvre l'UI et regarde successivement **📜 Logs**, **📊 Métriques**, **⏳ Approbations**.

---



## 🤖 Mode "all rights" — Briefs 24/7 sans supervision

Quand tu pars longtemps et que tu veux que l'orchestrateur tranche seul,
configure une **policy d'auto-approbation** + une **queue séquentielle**.

### Étape 1 — Choisir un niveau de confiance

Dans `/opt/stonks/.env`, mets :

```bash
STONKS_AUTOAPPROVE_LEVEL=conservative   # ou moderate, ou yolo
STONKS_AUTOAPPROVE_BUDGET_LIMIT_USD=5.0
```

| Niveau | Auto-approuve | Bloque toujours |
|---|---|---|
| `off` (défaut) | rien | tout passe par toi |
| `conservative` | lectures, écritures sandbox `/opt/stonks/`, `uv/pnpm install`, `git branch/commit`, `pytest/ruff`, `gitnexus index`, `docker compose up/down` | push sur main, suppression DB, force push, secrets, réseau externe |
| `moderate` | conservative + `git push agent/*`, `gh pr create`, `alembic upgrade`, appels LLM ≤ $5 | hard-blocks (force push main, drop DB…) |
| `yolo` | **TOUT** | uniquement les hard-blocks listés ci-dessous |

**Hard-blocks (toujours refusés, même en yolo) :**
- `force push` vers main / master / release
- `rm -rf` hors `/opt/stonks/`
- `drop database`, `truncate table`, `DELETE FROM ... sans WHERE`
- `chmod 777`, `chown root`
- `vault token revoke`, `vault secrets disable`
- `sudo rm/dd/mkfs/fdisk`
- `docker rm -f`, `docker volume rm`, `docker system prune`
- modifications de `/etc/passwd`, `/etc/sudoers`, `/etc/shadow`

**Recommandation :** pour la première grosse mission de nuit, prends
`conservative`. Tu peux passer en `moderate` ou `yolo` plus tard quand tu
auras vu comment l'orchestrateur se comporte.

### Étape 2 — Mettre tes briefs en queue

```bash
ssh max@serveurmax
cd /opt/stonks

# Ajoute les briefs dans l'ordre où tu veux qu'ils s'exécutent
task queue:add -- docs/briefs/2026-04-29_phase2-1-foundations.md
task queue:add -- docs/briefs/2026-05-01_phase2-2-cashflow.md
task queue:add -- docs/briefs/2026-05-02_phase2-3-portfolio.md

# Vérifie
task queue:list
#   ⏸ [queued ] 20260430_220000_phase2-1   →  docs/briefs/...
#   ⏸ [queued ] 20260430_220015_phase2-2   →  docs/briefs/...
#   ⏸ [queued ] 20260430_220030_phase2-3   →  docs/briefs/...
```

### Étape 3 — Démarrer le runner

```bash
task queue:start          # service systemd, daemon, survit SSH disconnect
# ou pour foreground :
task queue:run            # bloquant, dans ton SSH
```

Dans les 2 cas, le runner :
1. prend le 1er item `queued`
2. lance `python -m stonks_core.orchestrator.main autonomous --brief <chemin>`
3. attend la fin du sous-process
4. si exit_code = 0 → marque `done` et passe au suivant
5. si exit_code ≠ 0 et `stop_on_failure=True` → marque les suivants `skipped` et s'arrête
6. si `stop_on_failure=False` → continue malgré l'échec

### Étape 4 — Surveiller à distance

```bash
# Depuis ton mobile en SSH
task queue:list           # snapshot
task queue:logs           # tail live (journalctl -f)
task agents:tail          # 20 dernières actions de l'orchestrateur
task ui:status            # UI joignable ?
```

Ou via l'UI Streamlit (📜 Logs et 📊 Métriques en auto-refresh).

### Étape 5 — Ce qui se passe au matin

```bash
task queue:list
#   ✅ [done   ] 20260430_220000_phase2-1   →  ...
#   ✅ [done   ] 20260430_220015_phase2-2   →  ...
#   ▶️ [running] 20260430_220030_phase2-3   →  ...
```

Tu vas sur https://github.com/Max-cfn/Stonks/pulls : tu vois les PRs ouvertes, tu les valides à la main (le merge sur main reste **toujours** manuel).

### Stack complète pour autonomie totale

```bash
# 1. Une fois (config persistante)
sudo task ui:install                                                        # UI en daemon
echo "STONKS_AUTOAPPROVE_LEVEL=conservative" >> .env
sudo systemctl restart stonks-ui                                            # recharge la config

# 2. Quand tu pars pour 12-24h
task queue:add -- docs/briefs/2026-04-29_phase2-1-foundations.md
task queue:add -- docs/briefs/2026-05-01_phase2-2-cashflow.md
task queue:start

# 3. Au retour
task queue:list
gh pr list --repo Max-cfn/Stonks
```

### Audit trail

**Toute** auto-approbation est tracée dans `execution_log.txt` avec :
- l'`action` = `approval_auto`
- la `rule_matched` qui a déclenché l'auto-OK
- le `policy_level` au moment de la décision

Recherche les auto-approbations d'une nuit :
```bash
grep '"action":"approval_auto"' execution_log.txt | tail -50
```

Recherche les hard-blocks (l'orchestrateur a tenté un truc dangereux) :
```bash
grep '"action":"approval_hard_blocked"' execution_log.txt
```

---

## Surveillance pendant qu'il bosse

```bash
# Live tail dans le terminal
task agents:logs

# Snapshot rapide (qui bosse, sur quoi, combien de tokens)
task agents:status

# 20 dernières entrées en JSON pretty
task agents:tail
```

Ou ouvre **📜 Logs** / **📊 Métriques** dans l'UI.

---

## En cas de pépin

```bash
# Tout arrêter
pkill -f stonks_core.orchestrator
pkill -f streamlit

# Reset l'historique des conversations LangGraph (garde le code)
rm -rf agents_core/.langgraph/ agents_core/runtime/runs/*

# Purger les logs (avec backup)
mv execution_log.txt execution_log.$(date +%F).txt && touch execution_log.txt

# Réinstaller propre
task clean && task setup
```
