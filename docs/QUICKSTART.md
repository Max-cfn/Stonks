# Quickstart — Stonks

Tu pilotes l'Orchestrateur Stonks. Ce guide t'explique les **3 commandes**
que tu utiliseras 99 % du temps.

---

## 1. Première installation (à faire une fois)

```bash
cd /opt/stonks

# Installer toutes les dépendances (JS + Python + GitNexus)
task setup

# Configurer ton .env (tu DOIS le faire manuellement — ne committe jamais)
cp .env.example .env
nano .env   # → mets ta vraie OPENROUTER_API_KEY
            # → ne touche pas le reste pour l'instant

# Vérifier que la config est bonne
task agents:dry-run
```

---

## 2. Parler à l'Orchestrateur — 3 manières

### A. Via le browser (recommandé pour l'usage quotidien)

```bash
task ui
```

Puis ouvre **http://serveurmax:8501** dans Chrome/Firefox.

Workflow :
1. Onglet **📝 Briefing** → tu écris ton brief, clique "Envoyer"
2. Tu fermes le browser (ou tu pars dormir)
3. L'orchestrateur travaille, te demande des approbations dans l'onglet **⏳ Approbations**
4. Tu reviens quand tu veux, tu valides ou refuses, il continue
5. Onglet **📜 Logs** → tu vois ce qu'il a fait

### B. Via le terminal (REPL — pour tester / discuter)

```bash
task agents:dev
# tu écris ton brief, ligne vide pour envoyer
# tu lis la réponse, tu re-écris, etc.
```

### C. Via un fichier brief (pour les longues missions)

```bash
# 1. Crée ton brief en markdown depuis le template
cp docs/briefs/_template.md docs/briefs/$(date +%F)_cashflow.md
nano docs/briefs/$(date +%F)_cashflow.md

# 2. Lance l'orchestrateur dessus
task agents:run -- --brief docs/briefs/$(date +%F)_cashflow.md

# Il peut tourner pendant des heures. Tu peux fermer le SSH (lance via `tmux` ou `nohup`).
```

---

## 3. Surveiller en cours d'exécution

```bash
task agents:status        # snapshot : agents, tokens, coût, approbations
task agents:tail          # 20 dernières lignes du log
task agents:logs          # tail -f live du execution_log.txt
```

---

## 4. Approuver / rejeter une demande de l'orchestrateur

### Via le browser
Onglet **⏳ Approbations** → bouton Approuver / Rejeter.

### Via le terminal
```bash
task agents:status                    # → liste les req_id en attente
task agents:approve -- <req_id> "ok"
task agents:reject  -- <req_id> "non, fais autrement"
```

---

## 5. Configurer une mission longue (24 h sans déranger)

Dans ton brief, ajoute en section "Mode d'exécution" :

```yaml
mode: autonomous_long_run
budget_usd_max: 20
human_checkpoint_every_steps: 25
```

L'orchestrateur escalade UNIQUEMENT si :
- Erreur bloquante non-récupérable
- Décision sensible (force push, suppression, install global, etc.)
- Coût estimé > budget_usd_max

Sinon il continue, même 24 h. À chaque 25 étapes, il résume dans `execution_log.txt`.

---

## 6. Liens utiles

- **OpenRouter** dashboard : https://openrouter.ai/credits | https://openrouter.ai/activity
- **DeepSeek V4 Pro** specs : https://openrouter.ai/deepseek/deepseek-v4-pro
- **Repo GitHub** : https://github.com/Max-cfn/Stonks
- **GitNexus** (knowledge graph) : https://github.com/abhigyanpatwari/GitNexus
- **Picsou-finance** (réf PSD2) : https://github.com/Zoeille/picsou-finance
- **Enable Banking** (PSD2) : https://enablebanking.com/
- **Taskfile** : https://taskfile.dev/
- **LangGraph** : https://langchain-ai.github.io/langgraph/

---

## 7. En cas de pépin

```bash
# Tu veux tout arrêter
pkill -f stonks_core.orchestrator
pkill -f streamlit

# Tu veux tout reset (perd l'historique des conversations LangGraph)
rm -rf agents_core/.langgraph/ agents_core/runtime/runs/*

# Tu veux purger les logs (garde une copie)
mv execution_log.txt execution_log.$(date +%F).txt
touch execution_log.txt

# Tu veux réinstaller propre
task clean
task setup
```
