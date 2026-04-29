# Brief — [titre court ici]

> Format de brief pour l'Orchestrateur Stonks. Remplis chaque section.
> L'Orchestrateur produira un PLAN détaillé qu'il soumettra à ton approbation
> avant de bosser.

## Objectif
<!-- 1-2 phrases. Quoi faire concrètement, pas pourquoi. -->

## Contexte
<!--
Ce qu'il faut savoir : décisions déjà prises, contraintes techniques,
fichiers/modules concernés, références externes (docs, repos).
-->

## Critères d'acceptation
<!-- Liste de cases mesurables. Si une case ne peut être cochée, le brief échoue. -->
- [ ] 
- [ ] 
- [ ] 

## Hors-périmètre
<!-- Ce que l'agent NE doit PAS faire (évite les dérives). -->
- 
- 

## Mode d'exécution
<!--
Choix :
  - "interactive"          : tu valides chaque étape majeure (par défaut)
  - "autonomous_long_run"  : il bosse jusqu'à 24 h sans demander, escalade seulement si bloqué
-->
mode: interactive
budget_usd_max: 5
human_checkpoint_every_steps: 10
allow_branches:
  - "agent/**"
forbid_branches:
  - "main"
  - "release/**"

## Notes libres
<!-- Tout ce qui n'entre pas dans les sections ci-dessus. -->
