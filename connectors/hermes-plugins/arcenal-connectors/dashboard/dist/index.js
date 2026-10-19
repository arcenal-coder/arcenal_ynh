(function () {
  'use strict';
  const { React } = window.__HERMES_PLUGIN_SDK__;
  const h = React.createElement;
  const origin = "__ARCENAL_CONSOLE_ORIGIN__";
  function Connectors() {
    const base = window.__HERMES_BASE_PATH__ || '';
    return h('section', { className: 'arcenal-connectors ac-card' },
      h('h1', null, 'Connecteurs'),
      h('p', null, 'Configurez Dolibarr, Nextcloud et YunoHost dans la console centrale réservée aux administrateurs.'),
      h('p', null, 'La console utilise une origine HTTPS distincte afin que l’agent ne puisse pas approuver ses propres demandes.'),
      h('a', { href: origin + base + '/', target: '_blank', rel: 'noopener noreferrer', className: 'ac-console-link' }, 'Ouvrir la console sécurisée des connecteurs'));
  }
  window.__HERMES_PLUGINS__.register('arcenal-connectors', Connectors);
})();
