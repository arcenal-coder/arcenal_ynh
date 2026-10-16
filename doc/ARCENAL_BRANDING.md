# ARCenal Agent — marque et mises à jour gérées

Candidate locale : `0.22.2~ynh2`, basée sur Hermes stable v0.22.2.

## Résultat demandé

- Nom public : ARCenal Agent dans le manifeste, le panneau YunoHost, les
  descriptions de service, le titre du navigateur et les en-têtes du dashboard.
- Icône vectorielle ARCenal intégrée au build, servie sous le chemin de l'application.
- Marque CLI/TUI fournie par un skin natif `arcenal`, sans écraser un skin
  personnalisé. Les choix ultérieurs sont préservés par un marqueur de migration.
- Contrôles d'auto-mise à jour retirés de la navigation et de la page Système.
- Le backend reconnaît le propriétaire externe déclaré dans install-stamp.json
  et refuse les mises à jour locales du dashboard pour cette installation.

## Intégration

`conf/prepare_arcenal.py` applique les adaptations de distribution avant le build.
Les points d'adaptation sont contrôlés et l'exécution répétée est idempotente.
Le moteur, les identifiants de configuration Hermes, les crédits amont et les
parcours du dashboard restent ceux de la base publiée.

Le libellé YunoHost existant est migré seulement s'il vaut encore `Hermes Agent` ;
un libellé personnalisé est conservé. L'identifiant de l'application reste `arcenal`.

## Preuves locales

- Build TypeScript/Vite réel réussi sur une copie de la source v0.22.2 adaptée.
- 36 tests Python du paquet réussis avec les imports de la source adaptée, aucun
  test ignoré ; 1 test Node du moteur natif de bannière TUI réussi.
- Chrome headless sur backend local et proxy sous `/arcenal` : titre, en-tête et
  navigation ARCenal, aucun contrôle de mise à jour interne sur Sessions/Système.
- Test de propriété externe : rouge sur la source initiale, vert après adaptation.
- Chargement du skin natif et conservation des personnalisations vérifiés.
- Revue : les deux constats P2 sont corrigés et couverts. La migration lit
  `name` dans la réponse standard de `yunohost app info`, et ne modifie que le
  nom par défaut exact. Le skin définit `banner_logo` ; le rendu CLI large
  (140 colonnes) et le moteur TUI affichent `ARCenal Agent`.
- Ruff, ty sur le helper, syntaxe Bash, lecture TOML et `git diff --check` réussis.

Le test TUI s'exécute depuis le dossier du paquet avec Node ≥22.18 :

```sh
HERMES_SOURCE="/chemin/vers/la/source-hermes-v0.22.2-adaptee" \
  node --experimental-strip-types --test tests/test_branding_banner.mjs
```

Les derniers changements concernent le helper de configuration et le script
YunoHost ; le build web adapté précédemment validé est réutilisé par la recette
Chrome. Le test du moteur TUI ne constitue pas une conversation complète.

Publication et recette YunoHost réelle : EN ATTENTE. Aucune modification du
service ou de la configuration du serveur client n'est effectuée par ces tests.
