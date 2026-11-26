// @vitest-environment node
import {describe, expect, it} from 'vitest';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import type {Object3D} from 'three';
import {planEquip} from '../src/routes/wardrobe/Fitting.tsx';

const dir = join(process.cwd(), 'public', 'avatar');
const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json'), 'utf8')) as {
  bodies: Record<string, string>; slots: Record<string, {template: string; capacity: number; positions: string[]}>;
};
const load = (file: string) => new Promise<Object3D>((resolve, reject) => {
  const buf = readFileSync(join(dir, file));
  new GLTFLoader().parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), '', g => resolve(g.scene), reject);
});

describe('avatar placeholders', () => {
  it('every body loads and carries every attachment point the manifest names', async () => {
    const points = new Set(Object.values(manifest.slots).flatMap(s => s.positions));
    for (const file of Object.values(manifest.bodies)) {
      const scene = await load(file);
      for (const p of points) expect(scene.getObjectByName(p), `${file} ${p}`).toBeTruthy();
    }
  });
  it('every slot template loads as a mesh', async () => {
    for (const {template} of Object.values(manifest.slots)) {
      let meshes = 0;
      (await load(template)).traverse(o => { if ((o as {isMesh?: boolean}).isMesh) meshes++; });
      expect(meshes, template).toBeGreaterThan(0);
    }
  });
  it('the manifest lists every registry slot with its capacity, and two wrist and two ring positions', () => {
    const registry = {top: 1, outer: 1, bottom: 1, dress: 1, footwear: 1, bag: 1, headwear: 1, eyewear: 1, earrings: 1, necklace: 1,
      tie: 1, scarf: 1, belt: 1, wrist: 2, ring: 2, accessory: 3};
    for (const [slot, capacity] of Object.entries(registry)) {
      expect(manifest.slots[slot]?.capacity, slot).toBe(capacity);
      expect(manifest.slots[slot]!.positions.length, slot).toBe(capacity);
    }
  });
});

describe('fitting room equip rules', () => {
  const registry = {slots: [{slot: 'top', capacity: 1}, {slot: 'bottom', capacity: 1}, {slot: 'dress', capacity: 1}, {slot: 'wrist', capacity: 2}],
    exclusions: [['dress', 'top'], ['dress', 'bottom']]};
  it('a dress displaces the top and the bottom', () => {
    const plan = planEquip({top: ['t'], bottom: ['b']}, 'dress', 'd', registry);
    expect(plan.removed.sort()).toEqual(['b', 't']);
    expect(plan.next).toEqual({dress: ['d']});
  });
  it('two wrist items fit; a third displaces the oldest', () => {
    expect(planEquip({wrist: ['w1']}, 'wrist', 'w2', registry).removed).toEqual([]);
    expect(planEquip({wrist: ['w1', 'w2']}, 'wrist', 'w3', registry)).toEqual({next: {wrist: ['w2', 'w3']}, removed: ['w1']});
  });
});
