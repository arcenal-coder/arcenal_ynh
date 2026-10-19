import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';

test('native menu opens the isolated console without sharing an opener', () => {
  const home = mkdtempSync(path.join(tmpdir(), 'arcenal-menu-'));
  const root = fileURLToPath(new URL('..', import.meta.url));
  try {
    execFileSync(process.env.PYTHON ?? 'python3', ['-c',
      'from pathlib import Path; import sys; sys.path.insert(0,sys.argv[1]); from arcenal_connectors.provision import install_plugins; install_plugins(Path(sys.argv[1])/"hermes-plugins",Path(sys.argv[2]),"https://server.test:9443")',
      path.join(root, 'connectors'), home]);
    let component;
    vm.runInNewContext(readFileSync(path.join(home, 'plugins/arcenal-connectors/dashboard/dist/index.js'), 'utf8'), {
      window: {
        __HERMES_BASE_PATH__: '/arcenal',
        __HERMES_PLUGIN_SDK__: { React: { createElement: (tag, props, ...children) => ({ tag, props, children }) } },
        __HERMES_PLUGINS__: { register(name, value) { assert.equal(name, 'arcenal-connectors'); component = value; } },
      },
    });
    const tree = component();
    const link = tree.children.find(node => node?.tag === 'a');
    assert.equal(link.props.href, 'https://server.test:9443/arcenal/');
    assert.equal(link.props.target, '_blank');
    assert.match(link.props.rel, /noopener/);
    assert.match(link.props.rel, /noreferrer/);
    assert.match(link.children[0], /console sécurisée/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
