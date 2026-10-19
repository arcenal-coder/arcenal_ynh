import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { cpSync, mkdirSync } from 'node:fs';

const source = process.argv[2];
if (!source) throw new Error('Source Hermes requise');
const { build } = createRequire(path.join(path.resolve(source), 'package.json'))('esbuild');
const here = path.dirname(fileURLToPath(import.meta.url));
// L'artefact est livré dans le paquet. Il n'est JAMAIS compilé avec les
// dépendances modifiables par l'utilisateur Hermes sur le serveur cible.
const output = process.argv[3] || path.join(source, 'arcenal_connectors', 'ui');
mkdirSync(output, { recursive: true });
await build({
  entryPoints: [path.join(here, 'ui/index.js')], outfile: path.join(output, 'app.js'),
  bundle: true, format: 'iife', minify: true, sourcemap: false,
  nodePaths: [path.join(source, 'node_modules')],
  define: { 'process.env.NODE_ENV': '"production"' },
});
cpSync(path.join(here, 'ui/index.html'), path.join(output, 'index.html'));
await build({ entryPoints: [path.join(here, 'ui/style.css')], outfile: path.join(output, 'style.css'), bundle: true, minify: true });
for (const name of ['react', 'react-dom', 'scheduler']) {
  cpSync(path.join(source, 'node_modules', name, 'LICENSE'), path.join(output, name + '-LICENSE.txt'));
}
