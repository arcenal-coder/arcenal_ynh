# Administration — Hermes Agent sur YunoHost

## Architecture

- Identifiant de l'application : `arcenal`, conservé pour l'upgrade en place.
- Code : `/var/www/arcenal/app`, propriété de root ; environnement Python et
  outils de base construits par le gestionnaire PM officiel Hermes.
- Données : `/var/www/arcenal/data` (`HERMES_HOME`), accessibles à l'utilisateur
  système `arcenal`, sans SSH, SFTP ni droits root.
- Service : `arcenal.service`, exécutant `hermes dashboard` sur boucle locale,
  avec le port alloué par YunoHost et le TUI construit pour le chat.
- Proxy : Nginx et SSOwat ; permission principale initialisée pour `admins`,
  normalisée à l'installation, à l'upgrade et à la restauration.

## Utilisation

Ouvrir la tuile Hermes Agent depuis le portail YunoHost avec un administrateur.
Configurer les fournisseurs, modèles et secrets dans le dashboard Hermes.
Le panneau YunoHost indique ce parcours et ne réécrit pas la configuration.

Le sélecteur de thèmes Hermes propose Gratitude Clair, Sombre et Système.
Les choix sont enregistrés par Hermes ; le mode Système suit la préférence du
navigateur via `prefers-color-scheme`.

## Exploitation

Les journaux sont dans `HERMES_HOME/logs` et dans le journal systemd du service.
Le fichier `install-stamp.json` désigne YunoHost comme propriétaire externe des
mises à jour : utiliser le cycle du paquet, pas `hermes update`.

Les gateways configurés dans Hermes restent des processus distincts du
dashboard. Ils doivent être arrêtés avant une sauvegarde si le paquet détecte
des écritures encore actives ; le paquet refuse une sauvegarde incohérente.

Les données ARC héritées sont conservées mais ne sont pas exposées par une
façade parallèle. Aucun helper sudo de supervision ARC n'est installé.

Voir `RECETTE.md` pour le premier upgrade, les sauvegardes de transition et les
conditions de retour arrière ; `TEST_REPORT.md` distingue les preuves locales
de la qualification YunoHost restant à effectuer.
