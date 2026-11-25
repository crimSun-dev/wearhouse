// Fails if src/schema.d.ts is not exactly what the pinned generator produces from openapi-v2.json.
// (The Python side checks openapi-v2.json against the live app declarations: tools/contracts.py check.)
import {execFileSync} from 'node:child_process';
import {mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const dir = mkdtempSync(join(tmpdir(), 'wearhouse-contracts-'));
const out = join(dir, 'schema.d.ts');
try {
  const bin = join(root, 'node_modules', 'openapi-typescript', 'bin', 'cli.js');
  execFileSync(process.execPath, [bin, join(root, 'openapi-v2.json'), '-o', out], {stdio: 'pipe'});
  const norm = s => s.replace(/\r\n/g, '\n');
  if (norm(readFileSync(out, 'utf8')) !== norm(readFileSync(join(root, 'src', 'schema.d.ts'), 'utf8'))) {
    console.error('packages/contracts/src/schema.d.ts is stale. Regenerate: python tools/contracts.py generate');
    process.exit(1);
  }
  console.log('schema.d.ts matches openapi-v2.json');
} finally {
  rmSync(dir, {recursive: true, force: true});
}
