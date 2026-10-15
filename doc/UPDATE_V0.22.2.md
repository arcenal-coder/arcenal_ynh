# Préparation Hermes v0.22.2 pour YunoHost

Statut : candidate `0.22.2~ynh1`, publication Preview validée par le client.

## Références

- Dernier paquet Preview publié : `0.21.0~ynh69`, commit
  `0bb84cf188d2a30dcb2e04af2619e321821150fc`.
- Ancienne source Hermes : `0aa764feddf00aed631019763ef777d38faf4335`.
- Nouvelle release stable : https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.2
- Commit exact : `d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
- Archive épinglée : `https://codeload.github.com/NousResearch/hermes-agent/tar.gz/d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
- SHA-256 téléchargé : `616649f8ac7e3bb186999d000d77511e733b3930bd2b5921be4a85673320ef8b`.

L'ancienne source est un ancêtre de cette release. La candidate reprend le
dernier paquet publié et ses corrections, sans incorporer les modifications
administrateur non publiées du worktree de développement.

## Compatibilité vérifiée

- Bootstrap CPython amd64/arm64 : mêmes URLs et empreintes que les pins PM v0.22.2.
- Dashboard officiel, thème utilisateur Gratitude et runtime non root conservés.
- Base Vite du chemin YunoHost et TUI précompilé conservés.
- Données persistantes et mécanismes de snapshots/restauration conservés.
- Marquage d'installation externe avec base `0.22.2`, révision exacte et version
  affichée `0.22.2~ynh1` ; l'upgrade demeure géré par YunoHost.
- Mise à jour amont des dépendances via le lock publié, dont httpx2 2.12.0.

## Contrôles exécutés

| Contrôle | Résultat |
| --- | --- |
| Installation des dépendances npm verrouillées web/TUI | RÉUSSI, audit automatique : 0 vulnérabilité sur l'union installée |
| Construction de l'environnement Python par PM | RÉUSSI |
| Lint frontend | RÉUSSI, 0 erreur et 28 avertissements amont |
| TypeScript frontend | RÉUSSI |
| Tests frontend Chat, accessibilité, Sessions et thèmes | RÉUSSI, 34 tests |
| Build dashboard avec base `/arcenal/` | RÉUSSI |
| Build TUI | RÉUSSI |
| Tests Python amont via scripts/run_tests.sh | RÉUSSI, 10 tests handshake/configuration |
| Tests du paquet avec les vrais imports v0.22.2 | RÉUSSI, 29 tests |
| Syntaxe Bash et TOML, Ruff, ty | RÉUSSI |
| Compatibilité du travail administrateur en cours | RÉUSSI, 2 tests profil natif et 3 tests de provisionnement simulé |

Les builds ont utilisé temporairement la ligne de base Vite produite par
l'adaptateur du paquet. Le worktree source a ensuite été remis exactement sur
le tag ; l'adaptateur sera appliqué par le paquet lors de son installation.

## Réserves de recette

- Cycle complet install/upgrade/backup/restore et SSO réel sur YunoHost :
  NON_EXÉCUTÉ pour cette candidate.
- Échange modèle et reprise d'une conversation client : à confirmer.
- Problème connu signalé par l'amont : les sessions ayant tourné avec le gateway
  v0.22.1 peuvent ne pas être supprimables dans v0.22.2. Ce point n'a pas été
  reproduit sur les données client ; aucune suppression n'a été tentée.

## Suite de livraison

Publier cette candidate en Preview, puis reprendre la recette YunoHost avec une
sauvegarde complète. La publication ne vaut pas déploiement serveur ni création
de compte administrateur ; aucune promotion Stable n'est incluse.
