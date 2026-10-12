# Recette Hermes Agent pour YunoHost

Candidate locale : `0.21.0~ynh63`. Identifiant conservé : `arcenal`.

## Source exacte

- Hermes amont : `0aa764feddf00aed631019763ef777d38faf4335`.
- Archive : URL immutable par commit déclarée dans `manifest.toml`.
- SHA-256 : `272c31c21e859394f512aa41bb20a1fa8ca45988fcb12fd3bdc971e3f5990cf8`.
- Gratitude est fourni par le paquet sous forme de thèmes utilisateur Hermes,
  dans le sélecteur officiel : Clair, Sombre et Système.
- Les fournisseurs et secrets sont configurés depuis le dashboard Hermes.

## Conditions préalables

La candidate n'est pas publiée dans ARCenal Store et n'a pas encore été
qualifiée par `package_check` sur YunoHost. Ne pas effectuer de recette
destructive sur l'unique serveur en ligne.

L'ancien paquet ne sauvegardait que les données. Avant sa première mise à
niveau, une sauvegarde indépendante doit inclure code, environnement Python,
données, configuration Nginx/systemd et artefacts privilégiés ARC afin de
permettre le retour au paquet précédent. Le nouveau script de sauvegarde ne
peut pas corriger rétroactivement une ancienne archive.

L'upgrade produit aussi un instantané complet de transition, protégé en `0600`
dans `/var/cache/yunohost/appconfbackup/arcenal-native-transition/`, avant le
remplacement du code. Il inclut les deux artefacts privilégiés anciens s'ils
existent. Ce filet de récupération manuelle ne remplace pas la preuve d'un
rollback automatique sur instance jetable.

Les nouvelles sauvegardes embarquent un instantané figé des données dans la
sauvegarde du code, même si YunoHost exclut la copie ordinaire des données.
Un gateway détaché encore actif fait échouer la sauvegarde : arrêter les
gateways via Hermes avant de réessayer. Le dashboard reprend après sauvegarde.
La restauration conserve le dossier remplacé à côté des données comme copie
de récupération, sans l'exposer par Nginx.

## Recette sur instance jetable

1. Installer la candidate via YunoHost ; vérifier l'absence de commande manuelle
   post-installation et un service démarré sous l'utilisateur `arcenal`.
2. Vérifier l'accès après SSO avec un administrateur, puis le refus avec un
   non-administrateur et une session anonyme, y compris les API et WebSockets.
3. Ouvrir la tuile, puis recharger directement une route du dashboard sous
   `/arcenal/` et à la racine ; contrôler les assets, WebSockets et réponses SSE.
4. Configurer un fournisseur dans Hermes, converser, recharger et reprendre
   la conversation. Tester une erreur fournisseur et un changement de modèle.
5. Sélectionner Gratitude Clair, Sombre et Système ; vérifier la persistance,
   le changement du système, les contrastes, le clavier et le responsive.
6. Contrôler `NoNewPrivileges`, `UMask=0077`, code non inscriptible par le
   runtime et données/configuration/secrets en `0700/0600`.
7. Tester installation, sauvegarde/restauration, upgrade depuis le commit
   historique défini dans `tests.toml`, rollback après échec et retrait/purge.
8. Vérifier que conversations, mémoire, compétences et tâches restent
   accessibles ; les données ARC sans équivalent restent présentes et privées.
9. Vérifier que `hermes update` refuse de remplacer le code géré par YunoHost,
   et qu'aucun secret n'apparaît dans les journaux.

## Publication

Publier la révision du paquet et l'inscrire en Development requiert une
autorisation séparée. La promotion Preview puis Stable exige les preuves de
recette ; la seule présence du numéro `~ynh63` ne rend pas la mise à jour
disponible dans le Store.
