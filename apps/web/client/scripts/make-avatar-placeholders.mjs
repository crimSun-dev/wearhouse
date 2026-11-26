#!/usr/bin/env node
// Generates the avatar's low-poly placeholder models (task 5.1): one body per body option with named attachment
// points, one template per wardrobe slot, and public/avatar/manifest.json. Pure Node, no dependencies: it writes
// binary glTF 2.0 (GLB) directly. Replace any file in public/avatar/ by name with a real model; no code changes.
//   node scripts/make-avatar-placeholders.mjs
import {mkdirSync, writeFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'avatar');

// ---------- geometry (y up, metres, origin between the feet) ----------
function box(w, h, d, [x, y, z] = [0, 0, 0]) {
  const p = [], n = [], idx = [];
  const faces = [[[1, 0, 0], [0, 0, -1], [0, 1, 0]], [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], [[0, 1, 0], [1, 0, 0], [0, 0, -1]],
    [[0, -1, 0], [1, 0, 0], [0, 0, 1]], [[0, 0, 1], [1, 0, 0], [0, 1, 0]], [[0, 0, -1], [-1, 0, 0], [0, 1, 0]]];
  const half = [w / 2, h / 2, d / 2];
  for (const [normal, u, v] of faces) {
    const base = p.length / 3;
    for (const [su, sv] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      for (let k = 0; k < 3; k++) p.push([x, y, z][k] + (normal[k] + u[k] * su + v[k] * sv) * half[k]);
      n.push(...normal);
    }
    idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
  }
  return {p, n, idx};
}
function cylinder(rTop, rBottom, h, [x, y, z] = [0, 0, 0], seg = 10) {
  const p = [], n = [], idx = [];
  const slope = (rBottom - rTop) / h;
  for (let i = 0; i <= seg; i++) {
    const a = (i / seg) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a), len = Math.hypot(1, slope);
    p.push(x + rTop * c, y + h / 2, z + rTop * s, x + rBottom * c, y - h / 2, z + rBottom * s);
    n.push(c / len, slope / len, s / len, c / len, slope / len, s / len);
  }
  for (let i = 0; i < seg; i++) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  for (const [r, yy, ny] of [[rTop, y + h / 2, 1], [rBottom, y - h / 2, -1]]) {   // caps
    const centre = p.length / 3; p.push(x, yy, z); n.push(0, ny, 0);
    for (let i = 0; i <= seg; i++) { const a = (i / seg) * Math.PI * 2; p.push(x + r * Math.cos(a), yy, z + r * Math.sin(a)); n.push(0, ny, 0); }
    for (let i = 0; i < seg; i++) idx.push(...(ny > 0 ? [centre, centre + i + 2, centre + i + 1] : [centre, centre + i + 1, centre + i + 2]));
  }
  return {p, n, idx};
}
function sphere(r, [x, y, z] = [0, 0, 0], rings = 6, seg = 10) {
  const p = [], n = [], idx = [];
  for (let i = 0; i <= rings; i++) {
    const t = (i / rings) * Math.PI;
    for (let j = 0; j <= seg; j++) {
      const f = (j / seg) * Math.PI * 2, nx = Math.sin(t) * Math.cos(f), ny = Math.cos(t), nz = Math.sin(t) * Math.sin(f);
      p.push(x + r * nx, y + r * ny, z + r * nz); n.push(nx, ny, nz);
    }
  }
  for (let i = 0; i < rings; i++) for (let j = 0; j < seg; j++) {
    const a = i * (seg + 1) + j, b = a + seg + 1; idx.push(a, b, a + 1, b, b + 1, a + 1);
  }
  return {p, n, idx};
}
function merge(...parts) {
  const out = {p: [], n: [], idx: []};
  for (const g of parts) { const off = out.p.length / 3; out.p.push(...g.p); out.n.push(...g.n); out.idx.push(...g.idx.map(i => i + off)); }
  return out;
}

// ---------- GLB writer ----------
function glb(meshes, extraNodes = []) {
  const chunks = [], bufferViews = [], accessors = [], gltfMeshes = [], nodes = [];
  let offset = 0;
  const push = (typed, target) => {
    const bytes = new Uint8Array(typed.buffer, typed.byteOffset, typed.byteLength);
    const pad = (4 - (bytes.length % 4)) % 4;
    chunks.push(bytes, new Uint8Array(pad));
    bufferViews.push({buffer: 0, byteOffset: offset, byteLength: bytes.length, target});
    offset += bytes.length + pad;
    return bufferViews.length - 1;
  };
  for (const {name, geo, colour} of meshes) {
    const pos = Float32Array.from(geo.p), nor = Float32Array.from(geo.n), ind = Uint16Array.from(geo.idx);
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < pos.length; i += 3) for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k], pos[i + k]); max[k] = Math.max(max[k], pos[i + k]); }
    accessors.push({bufferView: push(pos, 34962), componentType: 5126, count: pos.length / 3, type: 'VEC3', min, max});
    accessors.push({bufferView: push(nor, 34962), componentType: 5126, count: nor.length / 3, type: 'VEC3'});
    accessors.push({bufferView: push(ind, 34963), componentType: 5123, count: ind.length, type: 'SCALAR'});
    const a = accessors.length;
    gltfMeshes.push({name, primitives: [{attributes: {POSITION: a - 3, NORMAL: a - 2}, indices: a - 1, material: gltfMeshes.length}]});
    nodes.push({name, mesh: gltfMeshes.length - 1});
    void colour;
  }
  const materials = meshes.map(m => ({name: `${m.name}-material`, pbrMetallicRoughness: {baseColorFactor: m.colour, metallicFactor: 0, roughnessFactor: 0.85}}));
  for (const e of extraNodes) nodes.push(e);
  const json = {asset: {version: '2.0', generator: 'wearhouse make-avatar-placeholders'}, scene: 0, scenes: [{nodes: nodes.map((_, i) => i)}],
    nodes, meshes: gltfMeshes, materials, accessors, bufferViews, buffers: [{byteLength: offset}]};
  let jsonBytes = new TextEncoder().encode(JSON.stringify(json));
  const jsonPad = (4 - (jsonBytes.length % 4)) % 4;
  jsonBytes = Uint8Array.from([...jsonBytes, ...Array(jsonPad).fill(0x20)]);
  const bin = new Uint8Array(offset); let o = 0;
  for (const c of chunks) { bin.set(c, o); o += c.length; }
  const total = 12 + 8 + jsonBytes.length + 8 + bin.length;
  const outBuf = new ArrayBuffer(total), view = new DataView(outBuf), u8 = new Uint8Array(outBuf);
  view.setUint32(0, 0x46546c67, true); view.setUint32(4, 2, true); view.setUint32(8, total, true);
  view.setUint32(12, jsonBytes.length, true); view.setUint32(16, 0x4e4f534a, true); u8.set(jsonBytes, 20);
  const binStart = 20 + jsonBytes.length;
  view.setUint32(binStart, bin.length, true); view.setUint32(binStart + 4, 0x004e4942, true); u8.set(bin, binStart + 8);
  return Buffer.from(outBuf);
}

// ---------- body options (proportions only; independent of gender identity) ----------
const SKIN = [0.83, 0.72, 0.66, 1];
const BODIES = {
  a: {shoulder: 0.21, hip: 0.11, torsoW: 0.42},
  b: {shoulder: 0.19, hip: 0.14, torsoW: 0.38},
};
export const ATTACH = {
  top: [0, 1.25, 0], outer: [0, 1.25, 0], bottom: [0, 0.72, 0], dress: [0, 1.02, 0], footwear: [0, 0.04, 0.03],
  headwear: [0, 1.74, 0], eyewear: [0, 1.61, 0.1], earrings: [0, 1.57, 0], necklace: [0, 1.44, 0.09], scarf: [0, 1.47, 0],
  tie: [0, 1.3, 0.12], belt: [0, 0.98, 0], bag: [0.3, 1.0, 0.02],
  wrist_l: [-0.31, 0.95, 0], wrist_r: [0.31, 0.95, 0], ring_l: [-0.32, 0.86, 0], ring_r: [0.32, 0.86, 0],
  accessory_1: [-0.17, 1.36, 0.12], accessory_2: [0.17, 1.36, 0.12], accessory_3: [0, 1.12, 0.13],
};
function body(opt) {
  const {shoulder, hip, torsoW} = BODIES[opt];
  const geo = merge(
    box(torsoW, 0.56, 0.22, [0, 1.24, 0]), cylinder(0.05, 0.055, 0.08, [0, 1.55, 0]), sphere(0.115, [0, 1.65, 0]),
    box(torsoW - 0.04 + (hip - 0.11), 0.16, 0.22, [0, 0.98, 0]),
    cylinder(0.045, 0.04, 0.56, [-(shoulder + 0.07), 1.2, 0]), cylinder(0.045, 0.04, 0.56, [shoulder + 0.07, 1.2, 0]),
    cylinder(0.075, 0.05, 0.9, [-hip + 0.01, 0.47, 0]), cylinder(0.075, 0.05, 0.9, [hip - 0.01, 0.47, 0]));
  const attach = Object.entries(ATTACH).map(([k, t]) => ({name: `attach_${k}`, translation: t}));
  return glb([{name: `body-${opt}`, geo, colour: SKIN}], attach);
}

// ---------- slot templates (centred on their attachment point) ----------
const NEUTRAL = [0.62, 0.58, 0.6, 1];
const TEMPLATES = {
  top: () => merge(box(0.46, 0.5, 0.26), cylinder(0.06, 0.055, 0.2, [-0.29, 0.13, 0]), cylinder(0.06, 0.055, 0.2, [0.29, 0.13, 0])),
  outer: () => merge(box(0.5, 0.62, 0.3, [0, -0.04, 0]), cylinder(0.065, 0.06, 0.52, [-0.29, -0.03, 0]), cylinder(0.065, 0.06, 0.52, [0.29, -0.03, 0])),
  bottom: () => merge(box(0.4, 0.18, 0.25, [0, 0.24, 0]), cylinder(0.09, 0.07, 0.7, [-0.1, -0.2, 0]), cylinder(0.09, 0.07, 0.7, [0.1, -0.2, 0])),
  dress: () => merge(cylinder(0.2, 0.36, 0.95, [0, -0.05, 0], 12), cylinder(0.06, 0.055, 0.16, [-0.26, 0.36, 0]), cylinder(0.06, 0.055, 0.16, [0.26, 0.36, 0])),
  footwear: () => merge(box(0.1, 0.08, 0.26, [-0.1, 0, 0]), box(0.1, 0.08, 0.26, [0.1, 0, 0])),
  headwear: () => merge(cylinder(0.2, 0.2, 0.02, [0, -0.03, 0], 14), cylinder(0.11, 0.125, 0.12, [0, 0.04, 0], 12)),
  eyewear: () => merge(box(0.22, 0.05, 0.02), box(0.02, 0.02, 0.12, [-0.11, 0, -0.06]), box(0.02, 0.02, 0.12, [0.11, 0, -0.06])),
  earrings: () => merge(sphere(0.018, [-0.12, 0, 0]), sphere(0.018, [0.12, 0, 0])),
  necklace: () => merge(cylinder(0.11, 0.11, 0.015, [0, 0.03, -0.08], 16), sphere(0.025, [0, -0.04, 0.01])),
  scarf: () => merge(cylinder(0.12, 0.13, 0.1, [0, 0, 0], 12), box(0.08, 0.3, 0.03, [0.06, -0.17, 0.11])),
  tie: () => box(0.07, 0.38, 0.02, [0, -0.1, 0]),
  belt: () => cylinder(0.24, 0.24, 0.05, [0, 0, 0], 14),
  bag: () => merge(box(0.24, 0.2, 0.08), box(0.02, 0.3, 0.02, [0, 0.22, 0])),
  wrist: () => cylinder(0.055, 0.055, 0.035, [0, 0, 0], 12),
  ring: () => cylinder(0.025, 0.025, 0.015, [0, 0, 0], 10),
  accessory: () => sphere(0.035),
};

// Capacities mirror GET /api/v2/wardrobe/slots; positions list every attachment point a slot may use.
const SLOTS = {top: 1, outer: 1, bottom: 1, dress: 1, footwear: 1, bag: 1, headwear: 1, eyewear: 1, earrings: 1, necklace: 1,
  tie: 1, scarf: 1, belt: 1, wrist: 2, ring: 2, accessory: 3};
const positions = slot => (slot === 'wrist' ? ['attach_wrist_l', 'attach_wrist_r'] : slot === 'ring' ? ['attach_ring_l', 'attach_ring_r']
  : slot === 'accessory' ? ['attach_accessory_1', 'attach_accessory_2', 'attach_accessory_3'] : [`attach_${slot}`]);

mkdirSync(OUT, {recursive: true});
for (const opt of Object.keys(BODIES)) writeFileSync(join(OUT, `body-${opt}.glb`), body(opt));
for (const [slot, make] of Object.entries(TEMPLATES)) writeFileSync(join(OUT, `${slot}.glb`), glb([{name: slot, geo: make(), colour: NEUTRAL}]));
const manifest = {
  version: 1,
  note: 'Placeholder low-poly templates generated by scripts/make-avatar-placeholders.mjs. Replace any file by name.',
  bodies: Object.fromEntries(Object.keys(BODIES).map(o => [o, `body-${o}.glb`])),
  slots: Object.fromEntries(Object.entries(SLOTS).map(([slot, capacity]) => [slot, {template: `${slot}.glb`, capacity, positions: positions(slot)}])),
};
writeFileSync(join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`wrote ${Object.keys(BODIES).length} bodies, ${Object.keys(TEMPLATES).length} slot templates and manifest.json to public/avatar/`);
