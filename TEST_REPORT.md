# Rapport de contrôle — Hermes Agent `0.21.0~ynh64`

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
| Ruff | RÉUSSI | Configuration du paquet et tests Python |
| ty | RÉUSSI | Helper de configuration avec source/runtime Hermes |
| Environnement Python PM | RÉUSSI | Construction isolée avec dépendances verrouillées |
| Dashboard web | RÉUSSI | TypeScript et build de la source Hermes |
| TUI embarqué | RÉUSSI | Build amont nécessaire au chat |
| Tests du paquet | RÉUSSI | 11 tests, dont processus transitoire, processus persistant et erreur du contrôle |
| Contraste AA des boutons principaux | RÉUSSI | Ratio texte/fond ≥ 4,5 pour les deux palettes |
| Diff Git | RÉUSSI | Pas d'erreur de whitespace |
| Revue indépendante | RÉUSSI | Constats P1 corrigés après trois passes ciblées |

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

Recette `~ynh63` : ÉCHEC sur YunoHost 12.1.40.1, lors du contrôle immédiat
des processus après arrêt des trois services. La correction `~ynh64` ajoute
une attente bornée et conserve le refus en présence de processus persistants.
Le test du processus transitoire échoue sur `~ynh63`, avant correction.

Candidate préparée pour qualification sur une instance jetable.
**Pas prête pour une installation de production ni une promotion Stable.**
Le scénario et les prérequis sont détaillés dans `doc/RECETTE.md`.
