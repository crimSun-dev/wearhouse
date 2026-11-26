import {readFileSync} from 'node:fs';
import {gzipSync} from 'node:zlib';

const manifest = JSON.parse(readFileSync('dist/.vite/manifest.json', 'utf8'));
const visited = new Set();
function size(key) {
  if (visited.has(key)) return 0;
  visited.add(key);
  const chunk = manifest[key];
  return gzipSync(readFileSync('dist/' + chunk.file)).length +
    (chunk.imports ?? []).reduce((sum, child) => sum + size(child), 0);
}
// Initial JS, including eager vendor imports. Lazy routes have separate budgets.
const budget = 200 * 1024;
const bytes = size('app/index.html');
console.log('App entry and static imports: ' + bytes + ' gzip bytes of ' + budget);
if (bytes > budget) process.exitCode = 1;
