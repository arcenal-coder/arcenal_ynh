# Rapport de contrôle — ARCenal Agent `0.22.2~ynh2`

## Candidate

- Source stable : Hermes `v0.22.2`, commit `d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
- SHA-256 téléchargé et vérifié :
  `616649f8ac7e3bb186999d000d77511e733b3930bd2b5921be4a85673320ef8b`.
- Identifiant YunoHost conservé : `arcenal`.
- État : candidate locale de marque ARCenal Agent ; publication en attente.
- Nouveau lot de marque et politique de mises à jour : `doc/ARCENAL_BRANDING.md`.
- Preuves actuelles et compatibilité : `doc/UPDATE_V0.22.2.md`.
- Les incidents `~ynh63` à `~ynh69` décrits ci-dessous sont HISTORIQUES et
  documentent les adaptations conservées, pas une nouvelle recette client v0.22.2.

## Contrôles locaux

| Contrôle | Résultat | Portée |
| --- | --- | --- |
| Syntaxe des scripts Bash | RÉUSSI | Tous les scripts du paquet |
| Lecture TOML | RÉUSSI | Manifeste, panneau de configuration et tests |
| Python d'amorçage | RÉUSSI | Archives amd64/arm64 téléchargées, SHA-256 et chemins vérifiés ; pins conformes à pm/lock.json |
| Ruff | RÉUSSI | Configuration du paquet et tests Python |
| ty | RÉUSSI | Helper de configuration avec source/runtime Hermes |
| Environnement Python PM | RÉUSSI | Construction isolée avec dépendances verrouillées |
| Dashboard web | RÉUSSI | TypeScript et build de la source Hermes |
| TUI embarqué | RÉUSSI | Build amont nécessaire au chat |
| Tests du paquet | RÉUSSI | 36 tests Python sans omission + 1 test Node ; libellés YunoHost, bannières CLI/TUI, propriété externe et Chrome réel |
| Build avec base `/arcenal/` | RÉUSSI | Compilateur Hermes réel, TypeScript et Vite sur une copie de la source épinglée |
| Préchargement Chat sous SSO strict | RÉUSSI | Échec reproduit avant correction, interface et flux PTY après ; aucun asset demandé hors `/arcenal` |
| Contraste AA des boutons principaux | RÉUSSI | Ratio texte/fond ≥ 4,5 pour les deux palettes |
| Diff Git | RÉUSSI | Pas d'erreur de whitespace |
| Revue indépendante | HISTORIQUE | Revue du socle ~ynh63 ; corrections ~ynh64/~ynh65 contrôlées localement |

Lot de marque `~ynh2` : les deux constats P2 de la revue indépendante sont
corrigés et vérifiés localement : lecture du champ `name` pour le libellé
YunoHost et `banner_logo` natif pour les grandes bannières CLI/TUI.
Les derniers changements n'affectent pas le frontend compilé ; le build adapté
déjà validé est utilisé par le test Chrome rejoué avec les 36 tests Python.

Les tests de snapshots exécutent les scripts et `tar` sur un dossier temporaire
avec SQLite. Les appels YunoHost et systemd sont simulés. Le smoke test démarre
un vrai serveur Hermes local, sans credentials, et vérifie le préfixe, le
catalogue des thèmes et le refus d'une API protégée sans jeton.

## Contrôles de livraison

| Contrôle | Résultat | Motif |
| --- | --- | --- |
| Installation YunoHost amd64/arm64 | NON_EXÉCUTÉ | Aucune instance jetable ni package_check/Incus local |
| Nginx, SSOwat administrateur, systemd | NON_EXÉCUTÉ | Nécessite YunoHost réel |
| Chat, reprise, fournisseurs, WebSocket/SSE | NON_EXÉCUTÉ | Recette fonctionnelle complète requise |
| Upgrade et rollback depuis le paquet ARC | NON_EXÉCUTÉ | Ancien backup incomplet ; transition à qualifier |
| Backup/restore hors ligne avec helpers réels | NON_EXÉCUTÉ | Les tests locaux ne couvrent pas le moteur YunoHost |
| Accessibilité et responsive visuels | NON_EXÉCUTÉ | Le ratio d'un bouton ne prouve pas toute WCAG 2.2 AA |
| Publication Store Development/Preview | NON_EXÉCUTÉ | Autorisation et qualification préalables |
| Promotion Stable | NON_EXÉCUTÉ | Recette client et autorisation séparée requises |

## Conclusion

Cause confirmée par la console client : les préchargements Vite demandent
`/assets/ChatPage-*.js` et `/assets/xterm-*.css`, hors du sous-chemin protégé.
SSOwat renvoie du HTML et le navigateur refuse ces types MIME. Le test strict
reproduit `Unable to preload CSS` et la disparition complète de l'interface.
Les premiers proxys de diagnostic acceptaient trop largement les URLs racine.

`~ynh69` adapte la seule propriété de base du fichier de configuration Vite
avant compilation au chemin alloué par YunoHost. Aucun changement à SSOwat,
aucune route publique `/assets`, aucun filtre MIME désactivé. Le frontend
reconstruit conserve l'interface et reçoit le flux PTY avec le même proxy strict.
La source de test est une copie temporaire du commit épinglé ; ni le code du
serveur actuel ni les sessions utilisateur n'ont été remplacés par ce test.

Diagnostic Chat : terminal monté, connexion WebSocket acceptée (101), aucun
octet d'affichage reçu pendant l'observation ; aucune exception JavaScript.
L'environnement du service ne contient pas `HERMES_TUI_DIR`. Le lanceur utilise
alors la fraîcheur d'un build source, qui exige un Node PM installé, puis peut
entrer dans la préparation/reconstruction au runtime.

`~ynh68` déclare explicitement le TUI construit via `HERMES_TUI_DIR`. Une
régression exécutant le vrai lanceur reproduit le chemin rebuild avant le
correctif puis prouve qu'il n'appelle plus la fraîcheur ni la préparation.
La recette d'affichage réel du TUI après upgrade reste à confirmer ; aucun
message utilisateur n'a été envoyé pendant le diagnostic.

Échec de sauvegarde avant upgrade : le journal Root montre uniquement `systemd`
et son enfant `(sd-pam)` sous l'utilisateur applicatif. L'attente ne résout pas
ce faux positif. `~ynh67` ignore ces managers seulement si leur exécutable est
le binaire système attendu et leur filiation est valide. Les processus inconnus,
les imposteurs et les contrôles illisibles restent bloquants.

Le backup préalable utilise les scripts du paquet installé : le nouveau paquet
ne répare pas rétroactivement ce script. `scripts/repair_process_check.py` prépare
une réparation administrateur bornée, avec empreintes des révisions connues,
conservation du fichier original, contrôle du correctif téléchargé et remplacement
de la seule fonction. Aucune réparation distante n'a encore été exécutée.
Revue indépendante ciblée : aucun constat significatif dans le filtre/réparateur ;
huit tests ciblés revérifiés. Le retour arrière de la réparation est manuel.

Diagnostic `~ynh65` après installation : service actif ; assets, profils,
sessions et catalogue des thèmes accessibles. Les thèmes Gratitude sont présents
mais le thème actif est `default`, car PM a déjà créé config.yaml avant le helper.
`~ynh66` initialise Gratitude une seule fois lorsqu'aucun thème personnalisé n'est
actif. Les choix suivants sont conservés, y compris un retour à Hermes Teal.
Le test du fichier précréé reproduit le défaut sur `~ynh65` et passe après correction.

La page Sessions rend ses statistiques dans un Chrome de diagnostic connecté
au backend via SSH et un proxy reproduisant le sous-chemin. Cela ne reproduit
pas la session SSO du navigateur client ; la zone vide de sa capture reste à
confirmer après rechargement complet. Aucune modification du code Hermes ni
des sessions utilisateur n'a été effectuée pour ce diagnostic.

Recette `~ynh64` : ÉCHEC d'installation sur Bookworm, car le Python système
ne supporte pas `TarFile.extractall(filter=...)`. `~ynh65` extrait d'abord,
avec les helpers YunoHost, le CPython autonome épinglé par Hermes. PM et le
marquage de version sont lancés avec cet interpréteur. Le Python système reste
inchangé et les filtres de sécurité PM ne sont pas désactivés.

Les tests d'amorçage simulent les helpers et vérifient la commande invoquée ;
ils ne constituent pas une installation Linux complète. Les archives réelles
amd64/arm64 sont vérifiées séparément. La sélection de Node utilise aussi
explicitement le runtime YunoHost, pas le Node global du serveur.

Recette `~ynh63` : ÉCHEC sur YunoHost 12.1.40.1, lors du contrôle immédiat
des processus après arrêt des trois services. La correction `~ynh64` ajoute
une attente bornée et conserve le refus en présence de processus persistants.
Le test du processus transitoire échoue sur `~ynh63`, avant correction.

Candidate préparée pour qualification sur une instance jetable.
**Pas prête pour une installation de production ni une promotion Stable.**
Le scénario et les prérequis sont détaillés dans `doc/RECETTE.md`.
