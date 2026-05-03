# Brief — Recovery : faire passer la CI sur PRs #3 et #4 + finir Phase 2.3 et 2.4

## ⚙️ Contexte d'exécution en queue

Ce brief tourne dans une queue séquentielle lancée via `task queue:start`.
- Auto-approve : `STONKS_AUTOAPPROVE_LEVEL=moderate` → tes commits, pushes
  agent/*, gh pr edit, alembic upgrade sont auto-approuvés.
- Hard-blocks : force push main, rm -rf hors stonks, drop database.
  Impossibles même en moderate.
- Branche de départ : `main`. Tu checkoutes les branches selon tes besoins.

## 🎯 Objectif

Pendant l'absence du humain, la queue Phase 2.1→2.5 a tourné. État actuel :

| Phase | PR | État | Travail restant |
|---|---|---|---|
| 2.1 Foundations | #2 | ✅ MERGED | Rien |
| 2.2 Cashflow | #3 | OPEN, CI ROUGE (lint + Backend) | Fixer la CI |
| 2.3 Portfolio | aucune | branche locale `agent/backend/phase-2-3-portfolio` (commit `9a21d94`) **non poussée**, **pas de PR** | Pousser, ouvrir PR, fixer CI |
| 2.4 Frontend Web | aucune | **branche n'existe pas** — phase non commencée ou skippée silencieusement | Démarrer et finir Phase 2.4 selon le brief original |
| 2.5 Mobile | #4 | OPEN, CI ROUGE (lint + Backend) | Fixer la CI |

**Ta mission : faire en sorte qu'au matin, l'humain ait 4 PRs vertes prêtes à
merger** (#3, #4, et 2 nouvelles pour Phase 2.3 et Phase 2.4).

## 🔁 Méthode imposée — boucle CI auto-fix

Pour CHAQUE PR dont la CI est rouge :

```
LOOP (max 8 itérations) :
  1. gh_pr_status(pr_number) → snapshot
  2. SI all_green → succès, passe à la PR suivante
  3. gh_pr_failed_logs(pr_number, max_chars=8000) → comprends l'erreur
  4. Identifie le problème précis (ruff rule, mypy error, test failed,
     coverage threshold, missing dep, secret detected, etc.)
  5. Lis les fichiers concernés (file_read)
  6. Applique le fix (file_write)
  7. Vérifie en local SI POSSIBLE :
     - shell_exec(command=".venv/bin/ruff check src/ tests/", cwd="packages/backend")
     - shell_exec(command=".venv/bin/mypy src/ --strict", cwd="packages/backend")
     - shell_exec(command=".venv/bin/pytest tests/ -x --tb=short", cwd="packages/backend")
  8. git_commit + git_push (auto-approuvé en moderate)
  9. gh_wait_for_ci(pr_number, timeout_minutes=15)
  10. retour à l'étape 1
```

**Garde-fou** : si la même erreur se répète 3 fois → escalade humain via
`request_human_approval`. Si > 8 itérations sans convergence → escalade.

## 📋 Plan d'exécution séquentiel

### ÉTAPE 1 — Audit initial (obligatoire en premier)

- [ ] `git_status` + `gh_pr_list --state open --repo Max-cfn/Stonks` (via shell_exec)
- [ ] Pour PR #3 et #4 : `gh_pr_status(3)` et `gh_pr_status(4)` puis
      `gh_pr_failed_logs(3)` et `gh_pr_failed_logs(4)`
- [ ] Vérifie l'existence de la branche `agent/backend/phase-2-3-portfolio`
      en local : `git branch --list agent/backend/phase-2-3-portfolio`
- [ ] Note tout dans `execution_log.txt` avec `phase=recovery_audit`

### ÉTAPE 2 — Fix PR #3 (Cashflow)

- [ ] `git checkout agent/backend/phase-2-2-cashflow`
- [ ] `git pull origin agent/backend/phase-2-2-cashflow`
- [ ] Boucle CI auto-fix jusqu'à toute verte
- [ ] À la fin : `gh pr edit 3` pour mettre à jour la description avec un
      résumé propre, puis `request_human_approval` pour le merge

### ÉTAPE 3 — Pousser Phase 2.3 et ouvrir PR

- [ ] `git checkout agent/backend/phase-2-3-portfolio`
- [ ] `git push -u origin agent/backend/phase-2-3-portfolio`
- [ ] `gh pr create` avec un titre clair `feat(portfolio): Phase 2.3 — ...`
      et une description listant les livrables
- [ ] Boucle CI auto-fix jusqu'à toute verte
- [ ] `request_human_approval` pour le merge

### ÉTAPE 4 — Faire Phase 2.4 (Frontend Web)

La branche n'existe pas, il faut la créer et bosser dessus. Réfère-toi au
brief `docs/briefs/2026-05-04_phase2-4-frontend-web.md` pour les critères
d'acceptation détaillés.

- [ ] `git checkout main && git pull`
- [ ] `git checkout -b agent/web/phase-2-4-frontend-web`
- [ ] Implémenter Next.js 15 + Tailwind + shadcn/ui + auth + 4 pages
      (dashboard, cashflow, portfolio, settings) selon le brief
- [ ] Tests + CI verte
- [ ] PR + boucle CI auto-fix
- [ ] `request_human_approval` pour le merge

**Budget pour Phase 2.4** : tu démarres avec **$15** disponible. Si tu vois
que ça ne tient pas, escalade humain à mi-parcours plutôt que de cramer le
budget pour rien.

### ÉTAPE 5 — Fix PR #4 (Mobile)

- [ ] `git checkout agent/mobile/phase-2-5-app`
- [ ] Boucle CI auto-fix jusqu'à toute verte
- [ ] `request_human_approval` pour le merge

## ❌ Hors-périmètre (NE PAS toucher)

- Force push, rewrite history, merge direct sur main
- Modifier `agents_core/`, `system_prompt.py`, `.env.example`
- Ajouter de nouvelles features non demandées dans les briefs originaux
- Démarrer une Phase 3 quoi que ce soit

## 📊 Mode d'exécution

mode: autonomous_long_run
budget_usd_max: 30
human_checkpoint_every_steps: 30
approval_timeout_minutes: 720
escalation_policy: minimal

## ✅ Définition de "fait"

✅ Les 4 PRs (#3, #4, et les 2 nouvelles pour 2.3 et 2.4) ont CI all_green.
✅ Tu as appelé `request_human_approval` pour chacune avec ce payload :
   `{"pr_url": "https://github.com/Max-cfn/Stonks/pull/N", "ci_status": "all_green", "phase": "..."}`
✅ Tu as logué `phase=completion status=ok prs=[3,4,X,Y]` à la fin.

❌ Tout autre état = brief non terminé. Continue ou escalade humain
   (request_human_approval avec reason="recovery brief — bloqué sur ...").
