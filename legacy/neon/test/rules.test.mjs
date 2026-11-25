import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {recommend,garment,allowed} from '../rules.mjs';
const read=name=>JSON.parse(readFileSync(new URL('../'+name,import.meta.url),'utf8'));
const wardrobe=read('seed.json').garments.map(g=>garment({...g,times_chosen:0,times_recommended:0,last_worn_at:null}));
// Reference outputs generated from legacy/python/app/scoring.py, not this implementation.
for(const {ctx,expected} of read('scoring-reference.json')){
  test(`Python parity ${JSON.stringify(ctx)}`,()=>{
    const results=recommend(wardrobe,ctx,'2026-11-24');
    assert.deepEqual(results.map(r=>({ids:r.items.map(g=>g.id),score:r.score})),expected);
    assert.ok(results.every(r=>allowed(r.items,ctx)));
  });
}
