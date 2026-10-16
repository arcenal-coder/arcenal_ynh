// Node >=22.18 : HERMES_SOURCE désigne la copie de la source épinglée.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import test from 'node:test'

test('the native TUI logo renderer uses the packaged ARCenal skin', async () => {
  assert.ok(process.env.HERMES_SOURCE, 'HERMES_SOURCE is required')
  const home = mkdtempSync(path.join(tmpdir(), 'arcenal-skin-'))
  try {
    const helper = fileURLToPath(new URL('../conf/configure.py', import.meta.url))
    execFileSync(process.env.PYTHON ?? 'python3', ['-c',
      'import pathlib,runpy,sys; runpy.run_path(sys.argv[1])["install_arcenal_skin"](pathlib.Path(sys.argv[2]))',
      helper, home])
    const skin = JSON.parse(readFileSync(path.join(home, 'skins/arcenal.yaml'), 'utf8'))
    const { logo } = await import(pathToFileURL(path.join(process.env.HERMES_SOURCE, 'ui-tui/src/banner.ts')))
    const rendered = logo({}, skin.banner_logo).map(([, text]) => text).join('\n')
    assert.equal(rendered, skin.branding.agent_name)
    assert.equal(rendered, 'ARCenal Agent')
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
})
