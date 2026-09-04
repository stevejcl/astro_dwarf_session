# Support multi-Dwarf dans `astro_dwarf_session`

Ce document couvre uniquement les évolutions côté `astro_dwarf_session`
(branche `V3_multi`) permettant de piloter plusieurs Dwarf en parallèle
depuis une seule instance de l'application. Le support multi-session
proprement dit (connexions indépendantes, routage des commandes) vit dans
`dwarf_python_api` (`DwarfConfig`/`DwarfSession`/`DwarfManager`, branche
`multi_V3`) - voir son propre `MIGRATION_MULTI_V3.md` pour ce qui concerne
la bibliothèque elle-même. Ici : comment `astro_dwarf_session` s'en sert.

## Architecture générale

`astro_dwarf_session` gérait déjà plusieurs *profils* (répertoires de
configuration `Devices_Sessions/<nom>/`), mais un seul à la fois : un
sélecteur de profil redirigeait un pointeur global (`set_config_data()`)
vers le bon `config.py`/`config.ini`, et tout le reste du code lisait ce
pointeur implicitement. Aucune notion de connexion simultanée à plusieurs
appareils.

Le travail a consisté à faire cohabiter ce mécanisme existant (conservé
tel quel pour la compatibilité mono-dwarf) avec une couche additive basée
sur `DwarfSession`/`DwarfManager` : chaque profil peut désormais avoir sa
propre session vivante, réutilisée d'un changement de profil à l'autre
plutôt que reconstruite à chaque fois (ce qui aurait cassé une connexion
déjà ouverte).

## `astro_dwarf_scheduler.py`

- **`CURRENT_SESSION`** (global, miroir de `CURRENT_CONFIG_NAME`) +
  **`get_current_session()`** : donne accès à la `DwarfSession` du profil
  actuellement sélectionné.
- **`setup_new_config()`** construit ou **réutilise** une `DwarfSession`
  via `DwarfManager` à chaque changement de profil, en plus de rediriger
  `set_config_data()` (comportement historique inchangé). Réutilise la
  session existante si ce `dwarf_uid` a déjà été vu dans cette exécution -
  préserve une connexion déjà ouverte au lieu de forcer une reconnexion à
  chaque bascule de profil.
- **`start_connection()`** et **`start_STA_connection()`** acceptent
  `session=None` ; cette dernière lit `session.config.dwarf_ip`/
  `dwarf_model_id` directement si fournie, sinon retombe sur `config.py`
  global comme avant.
- **`check_and_execute_commands()`** et **`retry_procedure()`** acceptent
  aussi `session=None` (repli sur `get_current_session()` si omis - compat
  CLI inchangée). Point important : un appelant qui boucle (comme le
  scheduler UI) doit **capturer sa session une seule fois** et la
  repasser explicitement à chaque itération, plutôt que laisser ces
  fonctions ré-résoudre `get_current_session()` à chaque appel - sinon,
  changer de profil dans l'UI pendant qu'un scheduler tourne encore pour
  un autre appareil redirigerait silencieusement ses prochaines commandes
  vers le nouveau profil sélectionné.
- Trois appels (`start_connection()`/`start_STA_connection()` dans le
  bloc `if __name__ == '__main__':`) sont **restés mono-dwarf** - c'est le
  lancement CLI autonome du script, sans notion de profil sélectionné,
  décision assumée plutôt qu'un oubli.

## `dwarf_session.py`

Toute la chaîne d'orchestration d'une session accepte et propage
`session=None` :

- **`start_dwarf_session(program, stop_event=None, session=None)`** - la
  fonction principale qui exécute une session planifiée complète (init,
  calibration, GOTO, capture, EQ Solving...). Tous ses appels internes
  (`perform_*`) propagent `session`.
- **`select_solar_target()`**, **`print_camera_data()`**,
  **`print_wide_camera_data()`**, **`try_attemps()`** (via des lambdas
  capturant `session`, sans modifier sa signature) - même traitement.
- **`start_polar_align`**/**`stop_polar_align`** (dans `dwarf_python_api`,
  mais consommées ici) - voir plus bas le bug `motor_action`.

**Non session-aware, sciemment** : les appels `perform_update_camera_setting`
restants (IR/binning/count sur certains chemins) utilisent encore la
fonction V2 legacy, non migrée - ils ciblent l'implicite mono-dwarf. Le
reste de la chaîne a depuis basculé vers les équivalents V3
(`perform_set_ir_filter_v3`, `perform_set_astro_stack_binning_v3`,
`perform_set_astro_stack_count_v3`), qui eux sont bien session-aware.

## `connect_bluetooth.py`

`connect_bluetooth_win()` et `connect_bluetooth_cmd()` acceptent et
transmettent `session=None` vers `connect_ble_dwarf_win()`/
`connect_ble_direct_dwarf()` (côté `dwarf_python_api`), qui appliquent la
découverte BLE (ip/dwarf_id/dwarf_uid) directement à la session fournie.

## `astro_dwarf_session_UI.py`

### Connexion et déconnexion

- **`bluetooth_connect_thread()`** : `self.disable_controls()` verrouillait
  le sélecteur de profil au démarrage de la connexion, mais rien ne le
  réactivait à la fin (succès ou échec) - impossible de connecter un
  second Dwarf après le premier. Corrigé avec un `finally` systématique.
- **`run_scheduler()`** capture désormais `scheduler_session =
  get_current_session()` **une seule fois** au démarrage et débloque le
  sélecteur de profil dès que la session est figée (plus besoin d'attendre
  l'arrêt complet du scheduler pour changer de profil et connecter un
  second appareil).
- **`finalize_close()`** (fermeture de l'app) déconnectait une seule
  session par défaut au lieu de toutes - corrigé pour boucler sur
  `get_manager().all()`.
- **`verifyCountdown()`** (chemin de timeout forcé) utilisait aussi
  `perform_disconnect()` sans session - la session figée du scheduler
  principal est maintenant gardée en attribut d'instance
  (`self.scheduler_session`) pour que ce chemin y accède correctement.

### Boutons d'action manuelle

Tous les boutons manuels (positionnement polaire, EQ Solving,
calibration, autofocus, reboot, powerdown, arrêt de session astro,
verrouillage/déverrouillage hôte, bascule RGB/power) capturent
`session = get_current_session()` et le propagent à leurs appels
`perform_*` internes.

**Bug le plus important trouvé pendant les tests réels** :
`motor_action()` (utilisée par le positionnement polaire, 12 branches
selon l'action demandée) avait été **totalement oubliée** dans la
migration initiale - elle ne suit pas le motif `perform_*` habituel, donc
invisible aux recherches automatiques. Résultat observé : le fichier de
log changeait bien en changeant de profil dans la combo, mais les
commandes moteur continuaient d'aller au dernier appareil connecté (celui
devenu "session par défaut" du gestionnaire), quel que soit le profil
affiché. Corrigé côté `dwarf_python_api` (les 12 branches routent
maintenant vers `session`), et `run_start_polar_position()` utilise aussi
`session.config.dwarf_model_id` plutôt que la config globale pour
déterminer le comportement D3 vs Mini.

### Scheduler : un seul à la fois, avec message clair

Choix assumé (option prudente plutôt qu'une refonte complète par profil,
qui aurait dû toucher `toggle_buttons`/`session_info_label`/tous les
contrôles caméra partagés) : **un seul scheduler principal actif à la
fois**. `self.scheduler_running_config_name` mémorise quel profil le
possède ; tenter de démarrer ou arrêter depuis un autre profil affiche un
message clair (`messagebox.showwarning`) au lieu de démarrer un second
scheduler en silence ou d'arrêter le mauvais. `on_combobox_change()`
rafraîchit l'affichage du bouton pour refléter l'état du profil
sélectionné, pas celui qui tourne ailleurs.

### "Scheduler 2" : harnais de test pour le parallélisme réel

Pour valider que deux sessions peuvent réellement tourner en parallèle
sans passer par la refonte complète : un **second bouton/thread
totalement indépendant** (`self.scheduler_running_2`,
`self.scheduler_stop_event_2`, `run_scheduler_2()`), qui capture sa propre
session au moment du clic (même mécanisme de figeage que le scheduler
principal) et ne touche à aucun widget partagé avec lui (pas de
`toggle_buttons`/`session_info_label` dupliqués - volontairement minimal).
Validé sur du vrai matériel : deux Dwarf connectés en BLE simultanément,
deux sessions planifiées tournant réellement en parallèle, routage des
commandes confirmé correct pour chacune (y compris positionnement polaire,
après le fix `motor_action`).

Si l'usage à deux schedulers (ou plus) devient permanent plutôt qu'un
test, la vraie refonte par profil reste à faire.

### Séparation des logs par appareil

Trois couches de correctifs, du plus simple au plus complet :

1. **Fichier dédié par scheduler** (`_attach_dedicated_log_file()`) : au
   lieu de dépendre du handler de fichier global d'`update_log_file()`
   (un seul actif à la fois, redirigé à chaque changement de profil - donc
   perdait les logs du scheduler qui continue de tourner en arrière-plan
   dès qu'on change de profil dans la combo), chaque scheduler ouvre son
   propre `FileHandler`.
2. **Filtre par thread** (`_ThreadFilter`) : un `FileHandler` seul
   captait quand même *tout* le trafic du logger racine, pas seulement
   celui de son propre appareil. Comme chaque scheduler tourne dans son
   propre thread, un filtre sur `record.thread` (attribut gratuit de tout
   `LogRecord`) sépare parfaitement les deux flux sans toucher à aucun
   appel `log.notice(...)` existant.
3. **Exclusion du handler global** (`exclude_thread_from_shared_log()`/
   `include_thread_in_shared_log()`, mécanisme générique côté
   `dwarf_python_api`'s `my_logger.py`) : le handler global
   d'`update_log_file()` captait encore occasionnellement le trafic d'un
   thread déjà couvert par son propre handler dédié. Chaque scheduler
   s'enregistre dans une liste d'exclusion le temps de son exécution.
4. **Thread `event_loop` de chaque session** (`_ensure_session_io_thread_excluded()`,
   appelée après connexion et à chaque itération, idempotente) : le
   thread d'arrière-plan asyncio qui gère l'I/O socket bas niveau
   (`session.event_loop_thread`, côté `dwarf_python_api`) est distinct du
   thread "scheduler" - fallait l'exclure aussi, y compris après une
   reconnexion qui en recrée un nouveau.

Résultat validé sur plusieurs sessions réelles à deux appareils : **zéro
ligne croisée** entre les fichiers de log des deux Dwarf.

**Limite restante, cosmétique** : la fenêtre de log affichée à l'écran
reste un widget unique partagé - les messages détaillés de chaque
scheduler s'y mélangent (seules les lignes explicitement préfixées
`[Scheduler 2]` restent identifiables). Pas de perte de données, juste un
affichage moins lisible en direct. Le même principe de filtre par thread
s'appliquerait au `TextHandler` si besoin.

### Autres corrections trouvées en testant

- Import cassé : `perform_getstatus` avait migré vers `dwarf_utilsV2.py`
  côté bibliothèque, l'import n'avait pas suivi.
- `get_client_status` importé depuis `websockets_utils` (version globale)
  au lieu de `dwarf_session_socket` (version session-aware) -
  `run_toogle_lights()` corrigée pour capturer et propager `session`.
- `self.session_running` jamais initialisé dans `__init__` (seulement à
  l'intérieur de `run_scheduler()`) - `AttributeError` si
  `update_session_info()` tourne avant le tout premier démarrage du
  scheduler.
- `get_current_config_name` oublié dans un import.
- Fenêtre de sélection BLE (plusieurs Dwarf détectés) : cliquer Annuler
  affichait "Please enter a valid number" et rebouclait indéfiniment,
  faute de distinguer `None` (Cancel) d'une saisie hors bornes - corrigé
  côté `dwarf_python_api`.

## Audit final

Un audit systématique (script comparant chaque appel de fonction
session-aware connue de `dwarf_python_api` avec sa présence dans
`dwarf_session.py`/`astro_dwarf_scheduler.py`/`astro_dwarf_session_UI.py`)
a trouvé et corrigé 6 derniers oublis : lecture des identifiants
Bluetooth et de l'heure/fuseau/localisation dans `start_connection()`,
paramètres caméra du rapport de fin de session, et surtout
`finalize_close()` qui n'aurait déconnecté qu'un seul appareil sur deux à
la fermeture de l'application.

## Statut

Validé de bout en bout sur deux Dwarf physiques (D3 + Mini) : connexions
BLE simultanées, deux sessions planifiées (dont positionnement polaire et
EQ Solving) tournant réellement en parallèle, logs séparés sans aucune
contamination croisée, déconnexion complète des deux appareils à la
fermeture.

## Pistes pour la suite

- **Refonte visuelle** (décidée : migration vers NiceGUI plutôt que
  généraliser l'UI Tkinter actuelle au multi-dwarf complet) - écran de
  contrôle par session (sélecteur/combo, bandeau d'action en cours avec
  variante erreur, aperçu caméra intégré en flux web auto-rafraîchi) et
  écran multi-panneaux (grille 2-4 sessions, chacune avec sa propre
  miniature et son statut).
- Vraie exécution concurrente de plus de 2 schedulers si le besoin se
  confirme (généraliser le principe de `Scheduler 2` à un état par
  profil, cette fois en touchant vraiment `toggle_buttons`/
  `session_info_label`/les contrôles caméra partagés).
- Filtre par thread appliqué aussi au `TextHandler` de la fenêtre de log,
  si l'affichage mélangé devient gênant en usage réel.
