import {afterEach, expect, test} from 'vitest';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawnSync} from 'node:child_process';

const scratch: string[] = [];
afterEach(() => { for (const dir of scratch.splice(0)) rmSync(dir, {recursive: true, force: true}); });

test('the gate fails for an unused operation and passes for a typed call in application code', () => {
  const root = mkdtempSync(join(tmpdir(), 'wearhouse-coverage-'));
  scratch.push(root);
  const client = join(root, 'apps/web/client');
  mkdirSync(join(client, 'src/api'), {recursive: true});
  mkdirSync(join(root, 'packages/contracts'), {recursive: true});
  writeFileSync(join(root, 'packages/contracts/openapi-v2.json'), JSON.stringify({
    paths: {'/api/v2/me': {get: {operationId: 'me'}}},
  }));
  writeFileSync(join(client, 'coverage-allowlist.json'), '{}');
  writeFileSync(join(client, 'tsconfig.json'), '{"include":["src"]}');
  writeFileSync(join(client, 'src/api/index.ts'), "export const api = {call(method: 'get', route: '/api/v2/me') {}};");
  const check = () => spawnSync(process.execPath, [resolve('scripts/check-coverage.mjs')], {cwd: client, encoding: 'utf8'});
  writeFileSync(join(client, 'src/feature.ts'), "// api.call('get', '/api/v2/me')");
  const missing = check();
  expect(missing.status).toBe(1);
  expect(missing.stdout).toContain('unused  GET /api/v2/me');
  writeFileSync(join(client, 'src/feature.ts'), "import {api} from './api/index'; api.call('get', '/api/v2/me');");
  const covered = check();
  expect(covered.status).toBe(0);
  expect(covered.stdout).toContain('used  GET /api/v2/me');
}, 30000);
