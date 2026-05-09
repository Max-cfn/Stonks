# Brief — Phase 2.9 : Fix banking OAuth + derniers correctifs UX

## ⚙️ Contexte d'exécution

- Auto-approve: `STONKS_AUTOAPPROVE_LEVEL=moderate` → tes commits, push
  `agent/*`, `gh pr create`, `alembic upgrade`, lecture/écriture sandbox
  `/opt/stonks/`, appels LLM ≤ $5 sont **auto-approuvés sans bloquer**.
- Hard-blocks gardent leur veto absolu : jamais de force push main, drop DB,
  rm -rf hors stonks, `git reset --hard` sur main, etc.
- LLM : DeepSeek V4 Pro via OpenRouter, provider DeepSeek officiel uniquement.
- **Boucle CI auto-fix obligatoire** sur la PR finale.
- Branche de départ : `main` (HEAD après merge PR #11).

## 🎯 Objectif global

La Phase 2.8 a corrigé 3 des 5 bugs post-dogfood. Il reste 2 correctifs UX
(validation login, hydration data-theme) + le flow banking OAuth est cassé
(client_id vide, redirect_uri mauvais port, lien frontend invalide).

**Mission : corriger les 6 bugs listés ci-dessous pour rendre le flow bancaire
fonctionnel et finaliser les correctifs UX.**

---

## 🌐 État runtime

| Service | URL/Port | Statut |
|---|---|---|
| Frontend Next.js | http://localhost:4173 | UP |
| Backend FastAPI | http://localhost:4174 | UP avec --reload |
| Postgres | localhost:5432 | UP |
| Enable Banking | sandbox | configuré dans `/opt/stonks/.env` |

**Compte test** : `hermes-test@stonks.fr` / `Test1234!`

---

## 🐛 Problème 1 (🔴 CRITICAL) — Banking OAuth : client_id vide

### Symptôme

`POST /cashflow/banks/connect` retourne une URL OAuth Enable Banking avec
`client_id=` VIDE :

```
https://auth.sandbox.enablebanking.com/oauth/authorize?
  client_id=&redirect_uri=http://localhost:8000/...
```

Sans `client_id`, Enable Banking rejette l'auth → impossible de connecter
une banque.

### Cause racine

Le backend lit la config depuis `packages/backend/.env` qui contient :
```
STONKS_ENABLE_BANKING_CLIENT_ID=
```
→ VIDE. La bonne valeur est dans `/opt/stonks/.env` mais le `.env` local
du package backend l'écrase.

### Fix

Copier la valeur depuis `/opt/stonks/.env` vers `packages/backend/.env` :
```
STONKS_ENABLE_BANKING_CLIENT_ID=36a2c3af-f771-4ae1-b56c-123e7f123d6a
```

**Fichier** : `packages/backend/.env`

---

## 🐛 Problème 2 (🔴 CRITICAL) — Banking OAuth : redirect_uri mauvais port

### Symptôme

L'URL d'auth contient `redirect_uri=http://localhost:8000/cashflow/banks/callback`
au lieu de `http://localhost:4174/cashflow/banks/callback`.

Après auth chez Enable Banking, le callback est envoyé au port 8000
(ancien port de dev) → personne n'écoute → échec.

### Cause racine

Le redirect_uri est soit hardcodé dans le code backend, soit configuré dans
une variable d'env (`STONKS_BACKEND_URL` ou similaire) avec l'ancienne valeur.

### Fix

1. Trouver où `redirect_uri` est construit dans `cashflow.py` (autour de la
   ligne 85-130)
2. Soit le rendre configurable via une variable d'env (`STONKS_BACKEND_URL`),
   soit le construire dynamiquement à partir du `Host` header de la requête
   entrante
3. S'assurer que le callback route (`/cashflow/banks/callback`) est bien
   enregistré sur le backend

**Fichier** : `packages/backend/src/stonks_backend/interfaces/api/routes/cashflow.py`

---

## 🐛 Problème 3 (🟡 MEDIUM) — Lien "Connecter un compte" pointe sur `/cashflow` sans locale

### Symptôme

Sur `/fr/cashflow`, le lien "Connecter un compte" a `href="/cashflow"` au lieu
de `/fr/cashflow`. Au clic → page blanche (pas de layout, pas de contenu).

### Cause racine

Le composant Cashflow utilise un `<Link href="/cashflow">` au lieu d'utiliser
le router i18n ou un chemin avec locale.

### Fix

Remplacer le lien par un bouton qui appelle l'API `POST /cashflow/banks/connect`
et redirige vers l'URL d'autorisation retournée. Ou au minimum corriger le href
pour inclure la locale.

**Fichier** : `apps/web/src/app/[locale]/(authenticated)/cashflow/` (trouver le
composant avec le lien "Connecter un compte")

---

## 🐛 Problème 4 (🟡 MEDIUM) — Pas de bouton pour déclencher l'API banks/connect

### Symptôme

La page Trésorerie affiche "Aucun compte bancaire" + lien "Connecter un compte",
mais ce lien ne déclenche PAS l'appel API `POST /cashflow/banks/connect`.
Aucun bouton/bouton ne fait cet appel.

### Cause racène

Le composant Cashflow n'implémente pas l'appel à l'API de connexion bancaire.

### Fix

Ajouter un bouton "Connecter une banque" qui :
1. Appelle `POST /api/cashflow/banks/connect`
2. Récupère l'`authorization_url` de la réponse
3. Redirige le navigateur vers cette URL (OAuth flow Enable Banking)

Gérer les états : loading (bouton désactivé + spinner), erreur (toast),
succès (redirection).

**Fichier** : `apps/web/src/app/[locale]/(authenticated)/cashflow/page.tsx`
(ou composant enfant)

---

## 🐛 Problème 5 (🔵 LOW) — Validation login : pas de messages d'erreur

### Symptôme (confirmé après merge PR #11)

Formulaire login soumis vide → aucun message d'erreur, pas de feedback.
Le fix de la PR #11 n'a pas eu l'effet escompté.

### Fix

1. Vérifier l'état actuel de `apps/web/src/app/[locale]/(auth)/login/page.tsx`
2. S'assurer que `react-hook-form` a des règles de validation sur les champs
   (`required`, `pattern` pour email, `minLength` pour password)
3. Afficher `formState.errors` sous chaque champ
4. Désactiver le bouton pendant `isSubmitting`
5. Afficher l'erreur API en toast si `401`

**Fichier** : `apps/web/src/app/[locale]/(auth)/login/page.tsx`

---

## 🐛 Problème 6 (🔵 LOW) — Hydration mismatch data-theme persistant

### Symptôme

Sur toutes les pages :
```
<html lang="en"
-  data-theme="light"
>
```

Le `style={{color-scheme}}` a bien été retiré par la PR #11, mais le mismatch
sur `data-theme` persiste.

### Fix

1. Forcer le `defaultTheme` à `"light"` (pas de `enableSystem` qui introduit
   une divergence SSR/client)
2. Ou : utiliser `suppressHydrationWarning` sur `<html>` dans `layout.tsx`
3. Ou : injecter le thème dans le HTML SSR via un script inline dans `<head>`
   pour que le SSR et le client produisent le même attribut

**Fichiers** :
- `apps/web/src/components/providers/Providers.tsx`
- `apps/web/src/app/layout.tsx`

---

## 📋 Plan d'exécution

- [ ] **ÉTAPE 0** — Branche `agent/fullstack/phase-2-9-fix-banking-and-ux`
- [ ] **ÉTAPE 1** — Fix client_id vide (`packages/backend/.env`)
- [ ] **ÉTAPE 2** — Fix redirect_uri (localhost:4174 au lieu de :8000)
- [ ] **ÉTAPE 3** — Fix lien "Connecter un compte" (locale + appel API)
- [ ] **ÉTAPE 4** — Ajouter bouton "Connecter une banque" avec appel API
- [ ] **ÉTAPE 5** — Fix validation login (react-hook-form rules + erreurs)
- [ ] **ÉTAPE 6** — Fix hydration data-theme (suppressHydrationWarning ou thème forcé)
- [ ] **ÉTAPE 7** — Test end-to-end : login → Trésorerie → clic Connecter → redirigé vers Enable Banking
- [ ] **ÉTAPE 8** — Test validation login : formulaire vide → messages d'erreur
- [ ] **ÉTAPE 9** — Vérifier console : plus de warning hydratation
- [ ] **ÉTAPE 10** — Tests backend + frontend passent
- [ ] **ÉTAPE 11** — PR + CI loop

## ❌ Hors-périmètre

- NE PAS modifier l'intégration Enable Banking elle-même (l'API est fonctionnelle)
- NE PAS modifier la structure de la DB
- NE PAS toucher aux autres pages (dashboard, portfolio, simulator)
- NE PAS modifier les CI workflows
- NE PAS modifier `agents_core/`

## 📊 Mode d'exécution

```
mode: autonomous_long_run
budget_usd_max: 3
approval_timeout_minutes: 720
```

## ✅ Définition de "fait"

- [ ] `POST /cashflow/banks/connect` retourne un `client_id` non-vide
- [ ] `redirect_uri` pointe sur `http://localhost:4174/cashflow/banks/callback`
- [ ] Page Trésorerie a un bouton qui déclenche l'OAuth flow Enable Banking
- [ ] Lien "Connecter un compte" ne casse plus la navigation
- [ ] Formulaire login affiche des erreurs sur champs vides
- [ ] Formulaire login affiche "Email ou mot de passe invalide" sur mauvais credentials
- [ ] Console navigateur : 0 warning hydratation sur toutes les pages
- [ ] Tous les tests passent (backend + frontend)
- [ ] CI GitHub toute verte
