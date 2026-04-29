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
