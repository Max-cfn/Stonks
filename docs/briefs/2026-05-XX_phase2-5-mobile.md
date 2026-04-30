# Brief — Phase 2.5 : Mobile (Expo, écrans principaux, push)

## Objectif
Application mobile React Native via Expo SDK 52+, écrans miroirs du web 
(Dashboard / Cashflow / Portfolio / Settings), auth JWT, push notifications 
pour alertes prix Portfolio.

## Contexte
- apps/mobile/ existe en stub (Expo)
- Phase 2.4 mergée (frontend web fonctionnel comme référence UX)
- Stack figée :
  - expo ~=52, react-native ~=0.76, typescript ~=5.6
  - expo-router ~=4 (file-based routing)
  - nativewind ~=4 (Tailwind sur RN)
  - @tanstack/react-query
  - expo-secure-store pour tokens
  - expo-notifications pour push
  - victory-native ou react-native-svg-charts pour graphes
  - jest + @testing-library/react-native

## Critères d'acceptation

### Setup
- [ ] Expo SDK 52+, expo-router en App folder
- [ ] NativeWind configuré, tokens design alignés avec apps/web
- [ ] Theme dark/light géré au niveau RN (useColorScheme)
- [ ] i18n FR/EN partagé avec apps/web (extraction packages/shared-i18n si pertinent)
- [ ] Splash + icon (assets simples, peut générer via task ou placeholders)

### Auth
- [ ] Écrans Login + Register (formulaires natifs)
- [ ] Stockage JWT via expo-secure-store (pas AsyncStorage)
- [ ] Refresh token interceptor
- [ ] Protected routes via layout group (auth)/

### Écrans
- [ ] (auth)/login + (auth)/register
- [ ] (tabs)/dashboard
- [ ] (tabs)/cashflow (liste transactions + filtres simples)
- [ ] (tabs)/portfolio (holdings + 1 graphe par ticker)
- [ ] (tabs)/settings (profile, alertes, logout)

### Push notifications
- [ ] Token Expo enregistré côté backend (nouveau endpoint POST /users/push-token)
- [ ] Test : alerte prix déclenche une push (via expo notifications)
- [ ] Tap sur push → ouvre écran portfolio

### Tests
- [ ] Tests unitaires sur hooks d'auth, formatters
- [ ] Coverage ≥ 60% (mobile : moins exigeant que backend)

### CI / Git
- [ ] Branche agent/mobile/phase-2-5-app
- [ ] CI verte : eslint, tsc, jest
- [ ] PR vers main, Reviewer Agent
- [ ] EAS build configuré dans eas.json (preview profile, builds non lancés en CI)

## Hors-périmètre
- ❌ Soumission App Store / Play Store
- ❌ Biométrie (Face ID, etc.) — peut être Phase 3
- ❌ Mode offline complet — peut être Phase 3
- ❌ Modifications backend sauf endpoint push-token

## Mode d'exécution
mode: autonomous_long_run
budget_usd_max: 20
human_checkpoint_every_steps: 25
approval_timeout_minutes: 720
escalation_policy: minimal

## Définition de "fait"
✅ pnpm --filter mobile start lance Expo, l'app tourne sur Expo Go (iOS et 
   Android testés au moins en simu), login → 4 onglets affichent la donnée 
   backend, push de test reçue, CI verte.