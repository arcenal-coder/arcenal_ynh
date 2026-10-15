# Recette Hermes Agent pour YunoHost

Candidate locale à publier en Preview : `0.22.2~ynh1`. Identifiant conservé : `arcenal`.

## Source exacte

- Hermes amont : release stable `v0.22.2`, commit `d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
- Archive : URL immutable par commit déclarée dans `manifest.toml`.
- SHA-256 : `616649f8ac7e3bb186999d000d77511e733b3930bd2b5921be4a85673320ef8b`.
- Rapport de préparation de la mise à jour : `UPDATE_V0.22.2.md`.
- Gratitude est fourni par le paquet sous forme de thèmes utilisateur Hermes,
  dans le sélecteur officiel : Clair, Sombre et Système.
- Les fournisseurs et secrets sont configurés depuis le dashboard Hermes.
- Python d'amorçage : CPython autonome issu des mêmes pins que `pm/lock.json`,
  téléchargé/vérifié/extrait par YunoHost avant de démarrer PM. Aucun changement
  du Python système ; filtres d'extraction de sécurité conservés.

## Conditions préalables

La qualification par `package_check` sur YunoHost reste à effectuer. Le client
a choisi la recette d'upgrade sur son serveur actuel ; installation fraîche,
désinstallation et restauration expérimentale n'y sont pas autorisées.

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

La révision `~ynh63` a refusé un upgrade immédiatement après l'arrêt des
services, sur présence de processus `arcenal`. La révision `~ynh64` attend
leur terminaison jusqu'à 30 secondes. Elle refuse toujours si des processus
persistent ou si le contrôle échoue, sans lancer de commande de terminaison.

La révision `~ynh64` a échoué à l'installation sur Python Bookworm ancien,
qui ne connaît pas `TarFile.extractall(filter=...)`. `~ynh65` utilise dès
l'amorçage le CPython épinglé par Hermes, fourni sous le code applicatif.

`~ynh66` initialise Gratitude même si PM a déjà créé la configuration générique.
La migration ne remplace pas un thème personnalisé ; un marqueur privé conserve
ensuite tous les choix manuels de thème. Après upgrade, recharger complètement
le navigateur puis ouvrir Sessions pour confirmer le parcours visible.

## Déblocage des versions déjà installées

`~ynh68` sélectionne le TUI précompilé au clic Chat. Après upgrade, recharger
complètement le navigateur puis ouvrir Chat et vérifier que le terminal affiche
son écran initial, avant d'envoyer un message ou de choisir un fournisseur.

`~ynh69` construit le frontend avec la base du chemin YunoHost afin de corriger
les préchargements CSS/JS de Chat. Dans le réseau du navigateur, les assets
doivent rester sous le chemin de l'application, par exemple `/arcenal/assets/`,
et ne pas partir vers `/assets/` puis la page SSO. Vérifier clic Chat et
rechargement direct de sa route après une actualisation complète du navigateur.

Si la sauvegarde refuse uniquement un manager `systemd` utilisateur et son
auxiliaire `(sd-pam)`, `~ynh67` corrige le filtre. La publication seule ne suffit
pas : la sauvegarde préalable exécute encore `_common.sh` du paquet installé.

Le réparateur `scripts/repair_process_check.py` nécessite une authentification
administrateur. Il accepte seulement les empreintes connues, vérifie celles du
correctif publié, sauvegarde l'original et change uniquement le filtre avec son
helper. Il ne modifie aucune donnée ni configuration Hermes, ne redémarre aucun
service et ne lance pas d'upgrade. Son exécution requiert l'autorisation du client.

Le rollback consiste à rétablir le fichier `_common.sh.before-process-fix-*`
créé avant réparation. Si le script installé est personnalisé, le réparateur
refuse de le remplacer ; diagnostiquer l'écart avant toute autre action.

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
