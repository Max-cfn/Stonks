# Brief — Phase 2.1 FINALIZE : merger la PR #2 backend foundations

## Contexte d'entrée — IMPORTANT

Cette mission **NE redémarre PAS Phase 2.1 from scratch**. Une PR existe déjà :
- PR #2 https://github.com/Max-cfn/Stonks/pull/2
- Branche : `agent/backend/phase-2-1-foundations`
- État : 9 commits, 55/55 tests passent, coverage 79.74% (juste sous le seuil 80% historiquement)
- CI : `lint` SUCCESS, `Backend (packages/backend)` SUCCESS, `JavaScript` SUCCESS, `Secret scan` SUCCESS, `test` (backend-ci.yml) FAIL à cause du seuil coverage, `Python (agents_core)` FAIL ruff (mais déjà fixé sur la branche dans le dernier commit)

**Ta mission : faire passer toute la CI verte sur cette PR, puis demander à l'humain de merger.**

## Objectif
Finaliser la Phase 2.1 :
1. Vérifier que la CI est verte sur la PR #2 après les derniers fixes
2. Si pas verte : creuser l'erreur, fix, push
3. Améliorer la coverage des modules sous-testés (`vault_client.py` à 32%, `user_repo.py` à 46%, `refresh_token_repo.py` à 38%) pour remonter au-dessus de 85% global
4. Mettre à jour la description de la PR avec un récap clair de tout ce qui est livré
5. Ouvrir un canal pour merge humain via `request_human_approval`

## Pré-requis
- Tu travailles sur la branche `agent/backend/phase-2-1-foundations`
- Si pas dessus, fais : `git checkout agent/backend/phase-2-1-foundations && git pull origin agent/backend/phase-2-1-foundations`
- N'OUBLIE PAS : la branche contient déjà beaucoup de code, tu dois ADD/AMEND, pas REWRITE
- PAS de `git reset --hard`, PAS de `git push --force` (les hard-blocks le refuseront de toute façon)

## Critères d'acceptation

### Tâche 1 — État des lieux (obligatoire en premier)
- [ ] `git status` propre, branche à jour avec origin
- [ ] `cd packages/backend && .venv/bin/pytest tests/ -v --cov=stonks_backend --cov-report=term-missing` lancé localement
- [ ] Note dans `execution_log.txt` : nombre de tests, % coverage actuel par module, modules à améliorer
- [ ] `gh pr view 2 --repo Max-cfn/Stonks --json statusCheckRollup` lancé pour voir l'état CI

### Tâche 2 — Combler la coverage
Cible : ≥ 85% global, ≥ 95% sur `infrastructure/security/`.

- [ ] `tests/test_vault_client.py` : tester le fallback `.env`, l'erreur si Vault unreachable, le caching
- [ ] `tests/test_user_repo.py` : tests d'intégration avec une fixture Postgres temporaire (testcontainers ou fixture pytest avec asyncpg) — get_by_email, save, update
- [ ] `tests/test_refresh_token_repo.py` : create + revoke + cleanup expired
- [ ] Tous les nouveaux tests doivent passer en CI
- [ ] La barre `--cov-fail-under` dans `.github/workflows/backend-ci.yml` doit pouvoir être remontée à **85** (mais NE LA REMONTE PAS dans cette PR — laisse à 78 pour ne pas casser à nouveau ; tu noteras dans la description PR que la barre devra remonter en Phase 2.2 quand on aura plus de tests d'intégration)

### Tâche 3 — Mettre à jour la description PR
Réécris la description de la PR #2 (`gh pr edit 2 --body "..."`) avec :
- Résumé des fichiers livrés (par dossier)
- Tableau coverage final par module
- Liste des "criteria coché / non coché" du brief original
- Instructions pour l'humain qui review (comment tester en local : `task stack:up && task migrate && cd packages/backend && task test`)
- Mention explicite : "✋ Ne pas merger si CI rouge"

### Tâche 4 — Demander le merge
Une fois CI verte :
- [ ] Appelle `request_human_approval` avec :
  - reason : `"Phase 2.1 prête pour merge — review et merge PR #2"`
  - payload : `{"pr_url": "https://github.com/Max-cfn/Stonks/pull/2", "ci_status": "all_green", "coverage": "<le %>", "phase_next": "2.2 Cashflow"}`
- [ ] **NE merge PAS toi-même.** Le merge sur main est une décision humaine (hard-block dans la policy)
- [ ] Attends la réponse. Si approved : log `phase=completion status=ok pr=2`. Si rejected : applique les remarques humaines puis re-demande.

## Hors-périmètre
- ❌ Démarrer Phase 2.2 (Cashflow) — c'est le prochain brief de la queue
- ❌ Modifier des fichiers hors `packages/backend/` (sauf `.github/workflows/backend-ci.yml` si vraiment nécessaire et justifié)
- ❌ Toucher à `agents_core/` (orchestrateur lui-même)
- ❌ Force push, rewrite history, merge direct sur main
- ❌ Modifier `.env.example` (les variables backend sont déjà ajoutées)

## Workflow imposé
1. **Diagnostic d'abord** : pas une seule modif tant que tu n'as pas fait `git status`, `gh pr view 2`, et `pytest --cov`
2. Pour chaque test ajouté : commit atomique avec message Conventional Commits (`test(backend): cover vault_client error paths`)
3. Pousse sur la même branche `agent/backend/phase-2-1-foundations`, **pas** sur une nouvelle branche
4. La policy auto-approve est en `moderate` : tes pushes sur `agent/backend/*`, tes `gh pr edit`, tes `pytest` sont auto-OK. Tu n'as pas besoin de demander pour ces actions.

## Mode d'exécution
mode: autonomous_long_run
budget_usd_max: 8
human_checkpoint_every_steps: 15
approval_timeout_minutes: 720
escalation_policy: minimal

## Définition de "fait"
✅ La PR #2 a tous ses checks CI verts, sa description est à jour, un
   `request_human_approval` a été émis pour le merge, et tu as logué
   `phase=completion status=ok pr_url=...`.
❌ Tu n'as pas le droit de marquer "fait" tant que la CI n'est pas verte.
