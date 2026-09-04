# ARCenal Agent — état, décisions et feuille de route

Dernière revue : **2026-09-04**. Ce document est le point de reprise commun pour
Damien et les autres contributeurs. Il décrit l'état observé dans les dépôts,
les décisions déjà prises et l'ordre de réalisation. Une case ne doit être
cochée qu'après validation sur une YunoHost propre.

### Journal de validation

- **2026-09-04 — YunoHost 12.1.41.2, Debian 12 ARM64, VM Lima :** première
  installation arrêtée lors de `uv sync`, car son répertoire courant était le
  dossier temporaire privé de YunoHost. Correction publiée dans
  `0.21.0~ynh3` avec `uv sync --directory "$install_dir"`. Le nettoyage a
  ensuite identifié l'ancien helper `ynh_safe_remove`, retiré dans
  `0.21.0~ynh4` au profit de la déprovision automatique des ressources v2. Le
  pipe d'installation de `uv` exécutait son côté droit sous root ; `0.21.0~ynh5`
  place désormais l'ensemble du pipeline sous l'utilisateur applicatif et
  épingle `uv` 0.12.9. Le second essai a détecté une version Python non conforme
  à PEP 440 ; le tag `v0.21.0-arcenal3` utilise désormais
  `0.21.0+arcenal.3`, validé dans la VM avec `uv lock --check`, et est livré par
  le paquet `0.21.0~ynh6`. Le troisième essai a validé l'environnement Python
  complet, puis détecté que le lockfile npm est à la racine du monorepo. Le
  paquet `0.21.0~ynh7` utilise la ressource Node.js 22.22 de YunoHost et exécute
  `npm ci` / `npm run build` sur le workspace `web` depuis la racine. Ce build a
  révélé un import TypeScript devenu inutilisé pendant le rebranding ; il est
  retiré dans `v0.21.0-arcenal4`, livré par `0.21.0~ynh8`. Avant le quatrième
  essai, `0.21.0~ynh9` corrige aussi le dossier `HOME` du service et utilise
  l'action `start` attendue par le helper systemd YunoHost. Le quatrième essai
  valide le build web et conduit `0.21.0~ynh10` à fournir au helper le nom exact
  du modèle `arcenal.service`. L'installation complète révèle enfin que la
  commande `serve` est volontairement limitée au backend : `0.21.0~ynh11`
  lance `dashboard`, transmet le préfixe YunoHost et construit les ressources
  web pour le chemin choisi lors de l'installation. Le premier test de mise à
  niveau corrige dans `0.21.0~ynh12` l'appel au helper de sauvegarde v2, dont le
  chemin est un argument positionnel. Pour permettre un accès local sans DNS
  système pendant les tests, `0.21.0~ynh13` rend la permission configurable ;
  elle reste réservée aux administrateurs par défaut.

## 1. État des lieux

### Dépôts

| Composant | État observé | Référence |
|---|---|---|
| `arcenal-agent` | Fork d'Hermes, branche `arcenal`, avec une surcouche ARCenal volontairement limitée | `aacb727df`, tag `v0.21.0-arcenal2` |
| Écart au code upstream | Rebranding web centralisé, garde d'exécution YunoHost et désactivation des mises à jour internes | `web/src/brand.ts`, `arcenal_runtime.py`, `hermes_cli/main.py` |
| `arcenal_ynh` | Scaffold packaging v2, propre et poussé, mais jamais validé sur YunoHost | `4eee4d8`, version `0.21.0~ynh1` |
| Source livrée | Archive GitHub immuable + SHA-256 | `v0.21.0-arcenal2` |

### Architecture cible retenue

```text
Navigateur
   │ HTTPS + contrôle d'accès SSOwat
   ▼
nginx YunoHost  ──►  127.0.0.1:$port
                         │
                         ▼
                  service systemd arcenal
                  `arcenal serve --no-open --skip-build`
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        $install_dir             $data_dir
        code + venv + SPA        config, secrets,
        remplaçable              mémoire, skills
                                persistant/sauvegardé
```

- Le processus tourne exclusivement sous l'utilisateur système `$app`, jamais
  sous `root` ou `www-data`.
- nginx est la seule entrée publique ; le serveur FastAPI écoute sur loopback.
- YunoHost possède le cycle de vie : installation, configuration, sauvegarde,
  restauration et mise à niveau. `arcenal update` reste désactivé.
- Le web UI est le seul périmètre de la première version. La passerelle de
  messagerie sera une évolution séparée, avec sa propre unité systemd.
- Les données persistantes et les secrets sont séparés des sources
  remplaçables. Aucun secret ne doit apparaître dans les arguments de processus
  ou les journaux.

### Bloquants constatés dans le paquet actuel

1. Le manifeste emploie `[resources.systemuser]`, alors que la ressource v2 est
   `[resources.system_user]`. Il ne déclare ni `install_dir`, ni `data_dir`, ni
   `permissions`; les variables utilisées par les scripts ne sont donc pas
   garanties et la permission SSOwat principale n'est pas définie.
2. Le manifeste doit déclarer `helpers_version` et adopter les ressources v2
   comme source de vérité. Les chemins `/var/www/arcenal/...` codés en dur
   empêchent aussi une évolution propre du paquet.
3. Le build SPA produit `hermes_cli/web_dist/` (`web/vite.config.ts`), tandis
   que l'unité pointe vers `web/dist`. En l'état, `--skip-build` ne trouvera pas
   l'interface ; le modèle systemd doit être corrigé puis vérifié par un build.
4. Le pipeline `curl | sh` de `uv` ajoute une dépendance réseau non épinglée et
   son environnement n'est appliqué qu'au côté droit du pipe. Installation,
   upgrade et restore ne suivent pas la même procédure ; restore suppose même
   que `uv` existe déjà dans une source fraîche.
5. `backup` ne sauvegarde que les données, mais `restore` tente de télécharger
   et reconstruire l'application. Il faut choisir et tester une stratégie
   symétrique ; la restauration doit fonctionner sans état résiduel.
6. L'unité autorise l'écriture dans `$install_dir`, ce qui affaiblit la
   séparation code/données. Le backend terminal `local` permet volontairement
   l'exécution de commandes : son périmètre système doit être testé, documenté
   et, si nécessaire, remplacé par un backend conteneurisé avant publication.
7. Le panneau affiche un interrupteur gateway sans unité correspondante. Cette
   option doit être retirée de la v1 plutôt que produire un avertissement après
   application.
8. Il manque `tests.toml`, `change_url`, une sonde de disponibilité, les tests
   d'upgrade/backup-restore et une validation réelle du fonctionnement sous un
   sous-chemin nginx.

## 2. Décisions partagées

| ID | Décision | Statut |
|---|---|---|
| D-01 | Maintenir deux dépôts : fork applicatif minimal et paquet YunoHost ; aucun code de packaging dans le fork. | Adoptée |
| D-02 | Garder les modules et alias `hermes*` internes pour réduire le coût des merges upstream ; `arcenal*` est l'identité publique. | Adoptée |
| D-03 | Épingler chaque livraison à un tag ARCenal immuable et à son SHA-256 ; aucune branche mobile dans le manifeste. | Adoptée |
| D-04 | Configurer l'application par fichiers générés, sans wizard, avec secrets dans un fichier mode `0600`. | Adoptée |
| D-05 | Réserver la v1 au web UI. Retirer le contrôle gateway tant que l'unité, la configuration et les tests associés n'existent pas. | Adoptée |
| D-06 | Accès privé par défaut, limité au groupe `admins`; nginx/SSOwat constitue le contrôle d'accès externe. | Adoptée |
| D-07 | Le backend terminal `local` est acceptable uniquement pour un jalon de test privé. La décision publication = local durci ou conteneur isolé reste à trancher après un test de menace. | À trancher |
| D-08 | Supporter l'installation sur sous-chemin seulement si le SPA et les API passent l'E2E ; sinon exiger un domaine dédié et l'indiquer dans le manifeste/doc. | À valider |
| D-09 | Ne pas annoncer `arm64` avant un build/install réussi sur cette architecture ou la validation de toutes les dépendances natives. | Adoptée |
| D-10 | Le rebranding est une surcouche de présentation centralisée. Les modules, API, variables `HERMES_*`, formats de données et structures internes restent alignés sur upstream. | Adoptée |
| D-11 | Une exécution ARCenal de production exige le marqueur créé par le paquet YunoHost. Seul `ARCENAL_DEV_MODE=1` permet le travail local sur les sources. | Adoptée |

## 3. Feuille de route ordonnée

### P0 — rendre le paquet installable et reproductible

- [ ] Corriger le manifeste : `helpers_version`, `system_user`, `install_dir`,
  `data_dir`, `permissions.main.url = "/"`, port interne et architectures
  effectivement vérifiées.
- [ ] Utiliser exclusivement `$install_dir`, `$data_dir`, `$port`, `$domain` et
  `$path` fournis par YunoHost dans scripts et modèles.
- [ ] Centraliser installation Python/uv et build web dans `_common.sh`, avec
  versions épinglées et comportement identique pour install/upgrade/restore.
- [ ] Vérifier le répertoire réel du bundle SPA et corriger `HERMES_WEB_DIST`.
- [ ] Générer `config.yaml` via un template ou un outil YAML sûr. Préserver les
  réglages et secrets existants pendant upgrade ; gérer correctement le
  changement de fournisseur sans conserver une clé sous un mauvais nom.
- [ ] Retirer le toggle gateway de `config_panel.toml` pour la première release.
- [ ] Ajouter `change_url` et valider la configuration nginx après chaque
  opération.

**Sortie P0 :** installation non interactive réussie sur une VM YunoHost 12.1+
propre, service actif après redémarrage, page et API accessibles via l'URL
choisie, aucun secret dans les logs.

### P1 — service, proxy et sécurité

- [ ] Ajouter une sonde de santé locale et faire échouer l'installation si le
  service ne devient pas prêt.
- [ ] Journaliser vers journald ou vers un fichier effectivement créé et géré ;
  aligner la déclaration `yunohost service add` sur ce choix.
- [ ] Durcir l'unité à partir du profil YunoHost actuel : périphériques,
  capacités, familles d'adresses, namespaces, noyau et appels système, sans
  casser les fonctions explicitement supportées.
- [ ] Rendre `$install_dir` en lecture seule au runtime ; n'autoriser en écriture
  que `$data_dir` et les emplacements temporaires indispensables.
- [ ] Tester que SSOwat refuse un visiteur, autorise un membre du groupe choisi,
  et protège aussi WebSocket/API. Ne faire confiance à aucun en-tête identité
  provenant directement du client.
- [ ] Vérifier CSRF, cookies, origine WebSocket, téléchargements, taille des
  requêtes et absence d'exposition directe du port.
- [ ] Réaliser le test de menace D-07 : commandes disponibles, lecture réseau et
  filesystem, persistance, secrets YunoHost accessibles. Décider ensuite du
  backend terminal livré.

**Sortie P1 :** revue de menace écrite, tests d'accès négatifs/positifs verts,
unité analysée avec `systemd-analyze security`, absence d'accès en écriture au
code installé.

### P2 — cycle de vie fiable

- [ ] Définir la procédure upstream : fetch, revue du changelog et des
  migrations, merge sur une branche dédiée, tests upstream, résolution minimale,
  tag `vX.Y.Z-arcenalN`, archive et SHA-256, puis bump `X.Y.Z~ynhN`.
- [ ] Ajouter un journal `UPSTREAM.md` indiquant pour chaque livraison : commit
  upstream, conflits, patches ARCenal conservés et résultats de tests.
- [ ] Garantir un upgrade transactionnel : sauvegarde YunoHost automatique,
  arrêt court, remplacement complet des sources, dépendances verrouillées,
  migration de config explicite, redémarrage et sonde.
- [ ] Rendre backup/restore symétriques : données, configurations système et tout
  artifact nécessaire ; restaurer sur une machine propre et vérifier les droits.
- [ ] Tester remove et purge : les ressources gérées par le manifeste sont
  supprimées par YunoHost ; les données suivent la sémantique officielle de
  purge, sans chemins codés en dur.

**Sortie P2 :** upgrade depuis la version publiée précédente et restauration
sur instance vierge sans perte de configuration, mémoire, skills ou secrets.

### P3 — E2E et publication

- [ ] Ajouter `tests.toml` avec au minimum : install racine/sous-chemin selon
  D-08, accès privé, upgrade courant et précédent, backup/restore, remove et
  change-url.
- [ ] Ajouter un test applicatif sans coût fournisseur : page, endpoint de santé,
  WebSocket/session et lecture de configuration, avec fournisseur factice si
  nécessaire.
- [ ] Ajouter un test optionnel avec un vrai fournisseur et un secret injecté
  par CI, sans jamais imprimer ce secret.
- [ ] Exécuter le linter YunoHost puis `package_check` dans un environnement LXC
  propre ; conserver les rapports dans les tickets ou releases.
- [ ] Tester explicitement reboot, indisponibilité réseau, clé invalide, manque
  de mémoire au build et rollback d'un upgrade échoué.
- [ ] Compléter documentation, licence du paquet, description bilingue,
  notifications et captures avant demande d'intégration au catalogue.

**Sortie P3 :** zéro erreur linter, matrice `package_check` verte pour tous les
scénarios annoncés et installation manuelle validée par une seconde personne.

## 4. Tableau de reprise

| Prochaine action | Responsable | État | Preuve attendue |
|---|---|---|---|
| Corriger les ressources du manifeste et retirer gateway | Non assigné | En cours : ressources corrigées, gateway restant | diff + validation du schéma |
| Uniformiser install/upgrade/restore | Non assigné | À faire | trois parcours sur VM propre |
| Valider le chemin du bundle SPA et le sous-chemin | Non assigné | Chemin corrigé, build/E2E restant | build + requêtes HTTP/E2E |
| Faire la revue de menace du backend terminal | Damien + mainteneur | À planifier | décision D-07 mise à jour |
| Installer sur une VM YunoHost 12.1+ | Damien | Bloqué tant que P0 n'est pas corrigé | URL, statut service, journal d'installation |
| Ajouter et exécuter `tests.toml`/package_check | Non assigné | À faire après P0/P1 | rapport complet |

## 5. Règles de collaboration

- Une décision modifiée reçoit une nouvelle ligne ou un statut explicite ; ne
  pas effacer l'historique utile.
- Toute case cochée doit pointer dans le commit ou le ticket vers une preuve de
  test. « Fonctionne chez moi » n'est pas un critère de sortie.
- Les changements upstream restent séparés des changements de packaging pour
  faciliter revue, bisect et retour arrière.
- Ne jamais tester en premier sur le serveur de production. Utiliser une VM ou
  un conteneur YunoHost jetable, puis faire valider par une seconde personne.
