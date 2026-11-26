// Production build guard: the e2e AuthPort fake must never ship (add-wearhouse-accounts 8.4).
import {readdirSync, readFileSync} from 'node:fs';
import {join} from 'node:path';

const dir = process.argv[2] || 'dist';
const files = readdirSync(dir, {recursive: true}).filter(f => /\.(js|html)$/.test(String(f)));
const bad = files.filter(f => readFileSync(join(dir, String(f)), 'utf8').includes('WEARHOUSE_E2E_FAKE_AUTH'));
if (bad.length) {
  console.error(`BUILD GUARD: e2e AuthPort fake found in ${dir}: ${bad.join(', ')}`);
  process.exit(1);
}
const legacy = files.filter(f => /legacy\/web|DW_API_BASE/.test(readFileSync(join(dir, String(f)), 'utf8')));
if (legacy.length) {
  console.error(`BUILD GUARD: legacy code found in ${dir}: ${legacy.join(', ')}`);
  process.exit(1);
}
console.log(`build guard OK: ${files.length} files in ${dir}, no e2e fake, no legacy code`);
