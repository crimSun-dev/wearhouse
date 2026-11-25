import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';

// Relocation guard: the adapter's relative JSON imports must resolve from legacy/neon.
// Importing creates a lazy pg.Pool only; no connection is opened without a query.
test('adapter module graph resolves from legacy/neon', async () => {
  for (const rel of ['../python/fixtures/bmkg_real_sample.json', '../contracts/openapi-v1.json', './seed.json']) {
    assert.ok(existsSync(new URL('../' + rel, import.meta.url)), rel + ' is missing');
  }
  process.env.DATABASE_URL ||= 'postgresql://nobody@127.0.0.1:1/unreachable';
  const mod = await import('../index.mjs');
  assert.equal(typeof mod.default.fetch, 'function');
});
