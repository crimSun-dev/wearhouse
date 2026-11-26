#!/usr/bin/env node
// Builds the BMKG location picker data from the Kemendagri region code list (Kepmendagri 300.2.2-2138/2025),
// via github.com/cahyadsn/wilayah (MIT). BMKG forecasts are keyed by the village (adm4) code.
//   node scripts/make-regions.mjs path/to/wilayah.sql
// Writes public/regions/index.json (provinces and cities) and public/regions/<city>.json (districts and villages).
import {mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'regions');
const sql = readFileSync(process.argv[2], 'utf8');
const rows = [...sql.matchAll(/\('([0-9.]{2,13})','([^']*(?:''[^']*)*)'\)/g)].map(m => [m[1], m[2].replace(/''/g, "'")]);
const byLevel = [[], [], [], []];
for (const [code, name] of rows) byLevel[code.split('.').length - 1].push([code, name]);
const sort = list => list.sort((a, b) => a[1].localeCompare(b[1], 'id'));
rmSync(OUT, {recursive: true, force: true}); mkdirSync(OUT, {recursive: true});
const index = {source: 'Kepmendagri No 300.2.2-2138 Tahun 2025 via github.com/cahyadsn/wilayah (MIT)',
  provinces: sort(byLevel[0]).map(([c, n]) => [c, n]),
  cities: sort(byLevel[1]).map(([c, n]) => [c, n])};
writeFileSync(join(OUT, 'index.json'), JSON.stringify(index));
let files = 0;
for (const [city] of byLevel[1]) {
  const districts = sort(byLevel[2].filter(([c]) => c.startsWith(city + '.'))).map(([c, n]) =>
    [c.slice(-2), n, sort(byLevel[3].filter(([v]) => v.startsWith(c + '.'))).map(([v, vn]) => [v.slice(-4), vn])]);
  writeFileSync(join(OUT, `${city}.json`), JSON.stringify(districts)); files++;
}
console.log(`${byLevel[0].length} provinces, ${byLevel[1].length} cities (${files} files), ${byLevel[2].length} districts, ${byLevel[3].length} villages`);
