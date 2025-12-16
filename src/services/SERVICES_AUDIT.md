# Audit des services (`src/services`) – logique vs orchestration

Principe réaffirmé :
- Modules `lib/*` portent la logique (calculs, conventions, sous-dossiers/suffixes, persistance). 
- Controllers = passe-plats. 
- Services = orchestration minimale (passent export_root/données, pas de chemins ni de suffixes).

## Synthèse par service

### s0_interface_service
- **Rôle attendu** : simple façade d’accès aux contrôleurs `lib/s0_interface` (pas de logique de mouvement ni de chemins).
- **Constat** : duplique l’instanciation d’ancrage/navigation ; risque de double logique. Pas de chemins.
- **Action** : soit le renommer en “NavigationInterfaceService” avec uniquement l’accès aux controllers, soit le retirer et laisser les autres services consommer directement `lib/s0_interface`.

### s1_session_setup_service
- **Rôle** : minimal — démarrage navigateur, sélection mode/difficulté, mise en place basique de session.
- **Constat** : ne gère plus game_id/iteration/export_root/overlay_enabled.
- **Action** : laisser la génération des identifiants/flags à la GameLoop ou à un state central partagé.

### s1_zone_capture_service
- **Rôle** : capture tuiles canvas (`capture_canvas_tiles`), assemblage via lib `s12_canvas_compositor`.
- **Constat** : les sous-dossiers s1_raw_canvases/s1_canvas doivent être gérés par capture (modules) et exposés via ce service. Vision/overlays consomment le `saved_path` nommé avec game_id/iteration.
- **Action** : garantir que le service capture expose le `saved_path` complet (et éventuellement le dossier capture pour l’itération), sans que d’autres services recomposent les chemins.

### s2_vision_analysis_service
- **Rôle** : appelle VisionController, ne persiste plus de capture (lève si pas de saved_path).
- **Constat** : lit `export_root/overlay_enabled/capture_saved_path` depuis `s30_session_context` (services ne passent plus d’args chemin).
- **Action** : RAS (orchestration minimale, contexte partagé).

### s3_storage_solver_service
- **Rôle** : façade vers `StorageSolverService` (lib) pour rejouer un snapshot storage.
- **Constat** : orchestration pure. 
- **Action** : RAS.

### s3_game_solver_service
- **Rôle** : vision → storage → solver.
- **Constat** : overlay_config/pré-solver overlay retirés ; le solver lit le contexte global (`s30_session_context`) pour export_root/flags/saved_path et gère les overlays en interne.
- **Action** : RAS côté service (passe-plat).

### s4_action_executor_service
- **Rôle** : exécute actions via Navigation/JS.
- **Constat** : orchestration ; pas de chemins overlay. 
- **Action** : RAS.

### s5_game_loop_service
- **Rôle** : boucle capture → vision → solver → (optionnel) exécution.
- **Constat** : centralise game_id/iteration/export_root/overlay_enabled via `set_session_context`; publie `capture_saved_path` après capture. Ne génère plus de pré-solver overlay ni de chemins ; modules consomment le contexte.
- **Action** : RAS (services passe-plats ; overlays gérés côté modules).

## Plan d’action proposé
1) **Vérif finale** : s’assurer que tous les appels utilisent `export_root` fourni par SessionStorage (clé `solver`) et ne recomposent pas de chemins/suffixes.
2) **Pré-solver overlay** : optionnel – extraire un helper lib (`lib/s4_solver/helpers.py`) si on veut dédupliquer la génération s40 appelée depuis s3/s5 ; sinon considérer cela comme orchestration acceptable.
3) **Navigation anchor** : si besoin de cohérence, déplacer l’init anchor dans NavigationController pour éviter la double logique `_setup_components`.
4) **Tests/réfs** : mettre à jour tout script/tests pour passer uniquement export_root (déjà fait pour 00/01/02). 
5) **Documentation** : INDEX_SERVICES/INDEX_LIB déjà alignés ; conserver la règle “services = orchestration, pas de chemins overlay”.
