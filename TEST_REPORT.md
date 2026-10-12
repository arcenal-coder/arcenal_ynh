# Rapport de contrôle — Hermes Agent `0.21.0~ynh65`

## Candidate

- Source : Hermes `0aa764feddf00aed631019763ef777d38faf4335`.
- SHA-256 téléchargé et vérifié :
  `272c31c21e859394f512aa41bb20a1fa8ca45988fcb12fd3bdc971e3f5990cf8`.
- Identifiant YunoHost conservé : `arcenal`.
- État : candidate Preview ; publication autorisée par le client pour recette
  sur son YunoHost actuel. La qualification complète reste NON_EXÉCUTÉE.

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
| Tests du paquet | RÉUSSI | 14 tests, dont choix du Python d'amorçage, pins, refus de fallback et quiescence |
| Contraste AA des boutons principaux | RÉUSSI | Ratio texte/fond ≥ 4,5 pour les deux palettes |
| Diff Git | RÉUSSI | Pas d'erreur de whitespace |
| Revue indépendante | HISTORIQUE | Revue du socle ~ynh63 ; corrections ~ynh64/~ynh65 contrôlées localement |

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
