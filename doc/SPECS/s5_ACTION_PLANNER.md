- **Séparation cleanup** : exécuter les `cleanup_actions` (bonus) en simple clic, hors métriques solver/CSP.
- **Ménage local (optionnel)** : après avoir cliqué un `SAFE`, ajouter éventuellement quelques clics opportunistes sur des `ACTIVE` adjacentes pour déclencher une résolution plus loin, sans que s4 ne contienne de logique dédiée.
- **Overlay plan** : produire un `overlay_path` (audit des actions planifiées).
- **Options solver** : `allow_guess` et `enable_cleanup` sont pilotés en s4 ; s5 consomme simplement les deux listes d’actions (solver + cleanup) fournies.

Clarification : le planner est agnostique du mode solver (réduction vs CSP). Il ne fait qu’ordonner/exécuter les actions qui lui sont données (flags, safes, cleanup), sans heuristique de priorité “SAFE-first”.

## 7. Référence – Dumb Solver Loop

La stratégie actuelle (réduction de frontière systématique, bypass CSP si assez d’actions, sinon CSP sur `TO_PROCESS`) est décrite ici :

`doc/FOLLOW_PLAN/s44_dumb_solver_loop.md`