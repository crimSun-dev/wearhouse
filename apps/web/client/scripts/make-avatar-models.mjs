#!/usr/bin/env node
// Generates the fitting-room avatar models (owner request 2026-11-26: human-looking, decently defined, per gender).
//
// Each body is ONE continuous surface: anatomical forms (ellipsoids and tapered capsules for the ribcage, pelvis,
// muscles, joints, face) are blended with smooth unions into a signed distance field, then meshed (surface nets,
// projected back onto the surface) and simplified. Garments are cut from the same field (the body offset outward,
// clipped to the garment's region), so every piece fits its body exactly. Bodies follow the avatar_gender setting:
// female, male, unspecified (in between). Output: public/avatar/*.glb (quantised, meshopt-compressed) + manifest.json.
//   node scripts/make-avatar-models.mjs [female|male|unspecified]
import {mkdirSync, readdirSync, rmSync, writeFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import * as THREE from 'three';
import {mergeGeometries} from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import {Document, NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {meshopt, quantize, simplify, weld} from '@gltf-transform/functions';
import {MeshoptEncoder, MeshoptSimplifier} from 'meshoptimizer';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'avatar');
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const mix3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const add3 = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const norm3 = v => { const l = Math.hypot(...v); return [v[0] / l, v[1] / l, v[2] / l]; };

// ---------------------------------------------------------------- distance-field primitives
const smin = (a, b, k) => { const h = Math.max(k - Math.abs(a - b), 0) / k; return Math.min(a, b) - h * h * k * 0.25; };
const smax = (a, b, k) => -smin(-a, -b, k);
function ell(c, r) {
  const [cx, cy, cz] = c, [rx, ry, rz] = r;
  const f = (x, y, z) => {
    const X = x - cx, Y = y - cy, Z = z - cz;
    const k0 = Math.hypot(X / rx, Y / ry, Z / rz), k1 = Math.hypot(X / (rx * rx), Y / (ry * ry), Z / (rz * rz));
    return k1 < 1e-12 ? -Math.min(rx, ry, rz) : k0 * (k0 - 1) / k1;
  };
  f.c = c; f.R = Math.max(rx, ry, rz);
  return f;
}
/** Tapered capsule from a (radius r1) to b (radius r2): Inigo Quilez's round cone. */
function cone(a, b, r1, r2) {
  const bx = b[0] - a[0], by = b[1] - a[1], bz = b[2] - a[2];
  const l2 = bx * bx + by * by + bz * bz, rr = r1 - r2, a2 = l2 - rr * rr, il2 = 1 / l2;
  const f = (x, y, z) => {
    const px = x - a[0], py = y - a[1], pz = z - a[2];
    const yy = px * bx + py * by + pz * bz, zz = yy - l2;
    const qx = px * l2 - bx * yy, qy = py * l2 - by * yy, qz = pz * l2 - bz * yy;
    const x2 = qx * qx + qy * qy + qz * qz, y2 = yy * yy * l2, z2 = zz * zz * l2;
    const k = Math.sign(rr) * rr * rr * x2;
    if (Math.sign(zz) * a2 * z2 > k) return Math.sqrt(x2 + z2) * il2 - r2;
    if (Math.sign(yy) * a2 * y2 < k) return Math.sqrt(x2 + y2) * il2 - r1;
    return (Math.sqrt(x2 * a2 * il2) + yy * rr) * il2 - r1;
  };
  f.c = mix3(a, b, 0.5); f.R = Math.sqrt(l2) / 2 + Math.max(r1, r2);
  return f;
}
/** Rounded box centred at c with half sizes h and corner radius r. */
function rbox(c, h, r) {
  const f = (x, y, z) => {
    const qx = Math.abs(x - c[0]) - h[0] + r, qy = Math.abs(y - c[1]) - h[1] + r, qz = Math.abs(z - c[2]) - h[2] + r;
    return Math.hypot(Math.max(qx, 0), Math.max(qy, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qy, qz), 0) - r;
  };
  f.c = c; f.R = Math.hypot(...h);
  return f;
}
/** Smooth union of primitives, with a bounding-sphere shortcut far from the group (keeps meshing fast). */
function group(prims, k) {
  const c = prims.reduce((s, p) => add3(s, p.c), [0, 0, 0]).map(v => v / prims.length);
  const R = Math.max(...prims.map(p => Math.hypot(p.c[0] - c[0], p.c[1] - c[1], p.c[2] - c[2]) + p.R));
  const f = (x, y, z) => {
    const dc = Math.hypot(x - c[0], y - c[1], z - c[2]) - R;
    if (dc > 0.09) return dc;
    let d = prims[0](x, y, z);
    for (let i = 1; i < prims.length; i++) d = smin(d, prims[i](x, y, z), k);
    return d;
  };
  f.c = c; f.R = R;
  return f;
}
/** Squash a primitive along z around zc (flat things: tie blades, scarf tails). */
const flatZ = (prim, zc, s) => { const f = (x, y, z) => prim(x, y, zc + (z - zc) * s) / s; f.c = prim.c; f.R = prim.R; return f; };

// ---------------------------------------------------------------- body parameters (metres; feet on y = 0)
const FEMALE = {H: 1.68, shoulderX: 0.158, hipX: 0.09, ribW: 0.118, ribD: 0.09, ribH: 0.128, waistW: 0.106, waistD: 0.085, pelvisW: 0.168,
  pelvisD: 0.104, pelvisH: 0.098, glute: [0.074, 0.082, 0.068], delt: 0.039, neckR: 0.04, uArm: [0.037, 0.028],
  fArm: [0.03, 0.02], thigh: [0.088, 0.05], calf: 0.05, ankle: 0.025, pec: 0, bust: 1, headS: 0.94, jaw: 0.7, brow: 0.45, hand: 0.92,
  foot: 0.235, skin: '#d4a184', lip: '#b56a68', hair: 'long', hairColour: '#2b1b15'};
const MALE = {H: 1.78, shoulderX: 0.19, hipX: 0.086, ribW: 0.142, ribD: 0.104, ribH: 0.148, waistW: 0.134, waistD: 0.1, pelvisW: 0.15,
  pelvisD: 0.1, pelvisH: 0.094, glute: [0.066, 0.072, 0.058], delt: 0.05, neckR: 0.054, uArm: [0.046, 0.034],
  fArm: [0.038, 0.025], thigh: [0.086, 0.052], calf: 0.053, ankle: 0.028, pec: 1, bust: 0, headS: 1, jaw: 1, brow: 1, hand: 1,
  foot: 0.262, skin: '#c38968', lip: '#a8655c', hair: 'short', hairColour: '#1f1512'};
function between(a, b, t) {
  const out = {};
  for (const k of Object.keys(a)) out[k] = typeof a[k] === 'number' ? lerp(a[k], b[k], t) : Array.isArray(a[k]) ? a[k].map((v, i) => lerp(v, b[k][i], t)) : a[k];
  return out;
}
const UNSPECIFIED = {...between(FEMALE, MALE, 0.5), bust: 0, pec: 0.25, hair: 'bob', skin: '#cb9576', lip: '#ad6862', hairColour: '#2a1c17'};
const BODIES = {female: FEMALE, male: MALE, unspecified: UNSPECIFIED};

// ---------------------------------------------------------------- anatomy
function anatomy(P) {
  const H = P.H, hs = P.headS, sc = H / 1.78;
  const Y = {shoulder: 0.818 * H, chest: 0.722 * H, waist: 0.612 * H, pelvis: 0.535 * H, hip: 0.512 * H, crotch: 0.472 * H, knee: 0.283 * H, ankle: 0.043 * H};
  const hc = [0, H - 0.1 * hs, 0];
  const side = s => {
    const S = [s * P.shoulderX, Y.shoulder - 0.018, -0.008];
    const L1 = 0.172 * H, L2 = 0.145 * H, a1 = 0.16, a2 = 0.11;
    const E = add3(S, [s * Math.sin(a1) * L1, -Math.cos(a1) * L1, -0.012]);
    const W = add3(E, [s * Math.sin(a2) * L2, -Math.cos(a2) * L2, 0.022]);
    const hsz = sc * P.hand;
    const upper = group([cone(S, E, P.uArm[0], P.uArm[1]),
      ell(add3(mix3(S, E, 0.45), [0, 0, 0.01]), [P.uArm[0] * 0.92, L1 * 0.28, P.uArm[0] * 0.95]),
      ell(add3(S, [s * 0.002, -0.03, 0]), [P.delt * 0.92, P.delt * 1.3, P.delt * 1.02])], 0.035);
    const fore = group([cone(E, W, P.fArm[0], P.fArm[1]), ell(add3(mix3(E, W, 0.26), [s * 0.002, 0, 0.004]), [P.fArm[0] * 1.08, L2 * 0.28, P.fArm[0] * 0.98]),
      ell(add3(E, [0, 0, -0.022]), [0.016, 0.02, 0.014].map(v => v * sc))], 0.028);
    const knuckle = W[1] - 0.088 * hsz;
    const fingers = [[0.025, 0.074], [0.009, 0.082], [-0.007, 0.077], [-0.022, 0.062]].map(([dz, len]) => {
      const base = [W[0] + s * 0.001, knuckle + 0.012 * hsz, W[2] + dz * hsz];
      return cone(base, add3(base, [-s * 0.012 * hsz, -len * hsz, 0.008 * hsz]), 0.0092 * hsz, 0.0072 * hsz);
    });
    const thumbBase = [W[0] - s * 0.008 * hsz, W[1] - 0.026 * hsz, W[2] + 0.03 * hsz];
    const hand = group([ell([W[0] - s * 0.002, W[1] - 0.048 * hsz, W[2] + 0.002], [0.0145 * hsz, 0.05 * hsz, 0.041 * hsz]),
      ...fingers, cone(thumbBase, add3(thumbBase, [-s * 0.014 * hsz, -0.058 * hsz, 0.018 * hsz]), 0.0128 * hsz, 0.0095 * hsz)], 0.009);
    const Hj = [s * P.hipX, Y.hip, 0], K = [s * (P.hipX - 0.008), Y.knee, 0.012], A = [s * (P.hipX - 0.014), Y.ankle, -0.015];
    const thigh = group([cone(add3(Hj, [0, 0.03, 0]), K, P.thigh[0], P.thigh[1]),
      ell(add3(mix3(Hj, K, 0.42), [-s * 0.004, 0, 0.022]), [P.thigh[0] * 0.74, 0.14 * sc, P.thigh[0] * 0.72]),
      ell(add3(K, [0, 0.008, 0.034]), [0.027, 0.031, 0.02].map(v => v * sc))], 0.04);
    const shin = group([cone(K, A, P.thigh[1] * 0.95, P.ankle), ell(add3(mix3(K, A, 0.27), [0, 0, -0.024]), [P.calf * 0.95, 0.1 * sc, P.calf * 0.95])], 0.035);
    const heel = [A[0], 0.034 * sc, A[2] - 0.036 * sc], ball = [A[0] + s * 0.012, 0.024 * sc, A[2] + P.foot - 0.075], toe = [A[0] + s * 0.016, 0.018 * sc, A[2] + P.foot - 0.048];
    const footG = group([cone(heel, ball, 0.036 * sc, 0.033 * sc), cone(ball, toe, 0.032 * sc, 0.022 * sc), ell(A, [0.031, 0.036, 0.036].map(v => v * sc)),
      cone(A, ball, 0.03 * sc, 0.024 * sc)], 0.03);
    const foot = (x, y, z) => smax(footG(x, y, z), -y, 0.006);
    foot.c = footG.c; foot.R = footG.R;
    return {S, E, W, Hj, K, A, heel, toe, upper, fore, hand, thigh, shin, foot, s,
      arm: (x, y, z) => smin(smin(upper(x, y, z), fore(x, y, z), 0.03), hand(x, y, z), 0.016),
      leg: (x, y, z) => smin(smin(thigh(x, y, z), shin(x, y, z), 0.045), foot(x, y, z), 0.028)};
  };
  const L = side(-1), R = side(1);
  const torsoPrims = [
    ell([0, Y.pelvis, -0.005], [P.pelvisW, P.pelvisH, P.pelvisD]),
    ell([0, Y.waist, 0.006], [P.waistW, 0.135 * sc, P.waistD]),
    ell([0, Y.chest + 0.02, -0.006], [P.ribW, P.ribH, P.ribD]),
    ell([0, Y.shoulder - 0.034, -0.022], [P.shoulderX * 0.86, 0.04 * sc, 0.068 * sc]),
    cone([0, Y.pelvis + 0.02, -0.008], [0, Y.chest + 0.04, -0.008], (P.waistW + P.pelvisW) * 0.45, P.ribW * 0.85),
    ...[-1, 1].map(s => ell([s * 0.058, Y.pelvis - 0.022, -0.055], P.glute)),
  ];
  if (P.pec > 0.1) for (const s of [-1, 1]) torsoPrims.push(ell([s * 0.062, Y.chest + 0.032, P.ribD * 0.5], [0.07 * P.pec, 0.05 * P.pec, 0.042 * P.pec]));
  if (P.bust > 0.1) for (const s of [-1, 1]) torsoPrims.push(ell([s * 0.058, Y.chest - 0.008, P.ribD * 0.56], [0.06, 0.058, 0.056].map(v => v * P.bust)));
  const torso = group(torsoPrims, 0.085);
  const neck = cone([0, Y.shoulder - 0.03, -0.016], [0, hc[1] - 0.07 * hs, -0.008], P.neckR * 1.1, P.neckR * 0.92);
  const H_ = v => v.map(n => n * hs);
  const at = (x, y, z) => [x * hs, hc[1] + y * hs, z * hs];
  const headMass = group([ell(at(0, 0.008, -0.01), H_([0.078, 0.094, 0.094])), ell(at(0, -0.03, 0.02), H_([0.066, 0.066, 0.066])),
    ell(at(0, -0.068, 0.028), H_([0.048 + 0.012 * P.jaw, 0.03, 0.054])), ell(at(0, -0.092, 0.06), H_([0.021 + 0.005 * P.jaw, 0.018, 0.019])),
    ...[-1, 1].map(s => ell(at(s * 0.045, -0.016, 0.054), H_([0.026, 0.021, 0.023])))], 0.026);
  const features = [ell(at(0, 0.031, 0.074), H_([0.056, 0.009 + 0.003 * P.brow, 0.016])),
    cone(at(0, 0.017, 0.088), at(0, -0.022, 0.108), 0.0066 * hs, 0.0102 * hs),
    ...[-1, 1].map(s => ell(at(s * 0.0105, -0.026, 0.097), H_([0.0095, 0.0072, 0.0085]))),
    ell(at(0, -0.0495, 0.0905), H_([0.0175, 0.0052, 0.0072])), ell(at(0, -0.0585, 0.0885), H_([0.016, 0.006, 0.0075])),
    ...[-1, 1].map(s => ell(at(s * 0.08, -0.006, -0.002), H_([0.01, 0.027, 0.018])))];
  // Eyes sit in shallow sockets under lids: the upper lid covers the top of the eye, as at rest (no wide stare).
  const eyeAt = s => at(s * 0.031, 0.006, 0.073), EYE_R = 0.0118 * hs;
  const sockets = [-1, 1].map(s => ell(add3(eyeAt(s), [0, 0.0015, 0.011 * hs]), H_([0.0175, 0.0135, 0.012])));
  const lids = [-1, 1].flatMap(s => { const e = eyeAt(s), up = ell(e, [EYE_R + 0.0014, EYE_R + 0.0016, EYE_R + 0.0014]), lo = ell(e, [EYE_R + 0.0011, EYE_R + 0.001, EYE_R + 0.0011]);
    return [(x, y, z) => Math.max(up(x, y, z), e[1] + 0.0032 * hs - y + 0.9 * (x - e[0]) ** 2 / hs), (x, y, z) => Math.max(lo(x, y, z), y - (e[1] - 0.0072 * hs))]; });
  // A gentle smile: the mouth line rises towards the corners.
  const smile = [-1, 1].map(s => cone(at(0, -0.0542, 0.0975), at(s * 0.018, -0.0512, 0.0905), 0.0014 * hs, 0.0016 * hs));
  const head = (x, y, z) => {
    let d = headMass(x, y, z);
    if (d > 0.06) return d;
    for (const f of features) d = smin(d, f(x, y, z), 0.007);
    for (const s of sockets) d = smax(d, -s(x, y, z), 0.008);
    for (const l of lids) d = smin(d, l(x, y, z), 0.0015);
    for (const m of smile) d = smax(d, -m(x, y, z), 0.002);
    return d;
  };
  const body = (x, y, z) => {
    let d = smin(torso(x, y, z), neck(x, y, z), 0.04);
    d = smin(d, head(x, y, z), 0.028);
    d = smin(d, L.arm(x, y, z), 0.035); d = smin(d, R.arm(x, y, z), 0.035);
    d = smin(d, L.leg(x, y, z), 0.05); return smin(d, R.leg(x, y, z), 0.05);
  };
  const eyes = [-1, 1].map(eyeAt);
  return {P, H, hs, sc, Y, hc, at, L, R, torso, neck, head, headMass, body, eyes, EYE_R, sides: [L, R]};
}

/** Where the surface of f is, marching along z from the front (dir 1) or back (dir -1) at (x, y). */
function surfaceZ(f, x, y, dir = 1) {
  let z = 0.45 * dir, prev = f(x, y, z);
  for (let i = 0; i < 300; i++) {
    const nz = z - dir * 0.003, v = f(x, y, nz);
    if (v < 0 && prev >= 0) { let a = nz, b = z; for (let j = 0; j < 20; j++) { const m = (a + b) / 2; if (f(x, y, m) < 0) a = m; else b = m; } return (a + b) / 2; }
    z = nz; prev = v;
  }
  return 0;
}
/** Distance from the vertical axis to the surface of f at height y, along a horizontal ray at angle θ (0 = front). */
function surfaceRay(f, y, theta) {
  const dx = Math.sin(theta), dz = Math.cos(theta);
  let r = 0.3;
  for (let i = 0; i < 200 && f(dx * r, y, dz * r) > 0; i++) r -= 0.002;
  return r;
}

// ---------------------------------------------------------------- meshing (surface nets, projected onto the surface)
function surfaceNets(f, min, max, h) {
  const nx = Math.ceil((max[0] - min[0]) / h) + 1, ny = Math.ceil((max[1] - min[1]) / h) + 1, nz = Math.ceil((max[2] - min[2]) / h) + 1;
  const v = new Float32Array(nx * ny * nz);
  const id = (i, j, k) => i + nx * (j + ny * k);
  for (let k = 0; k < nz; k++) for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) v[id(i, j, k)] = f(min[0] + i * h, min[1] + j * h, min[2] + k * h);
  const cell = new Int32Array(nx * ny * nz).fill(-1);
  const pos = [];
  const EDGES = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
  const c = new Float64Array(8);
  for (let k = 0; k < nz - 1; k++) for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
    let inside = 0;
    for (let b = 0; b < 8; b++) { c[b] = v[id(i + (b & 1), j + ((b >> 1) & 1), k + ((b >> 2) & 1))]; if (c[b] < 0) inside++; }
    if (inside === 0 || inside === 8) continue;
    let sx = 0, sy = 0, sz = 0, n = 0;
    for (const [a, b] of EDGES) {
      if ((c[a] < 0) === (c[b] < 0)) continue;
      const t = c[a] / (c[a] - c[b]);
      sx += (a & 1) + t * ((b & 1) - (a & 1)); sy += ((a >> 1) & 1) + t * (((b >> 1) & 1) - ((a >> 1) & 1)); sz += ((a >> 2) & 1) + t * (((b >> 2) & 1) - ((a >> 2) & 1)); n++;
    }
    cell[id(i, j, k)] = pos.length / 3;
    pos.push(min[0] + (i + sx / n) * h, min[1] + (j + sy / n) * h, min[2] + (k + sz / n) * h);
  }
  const idx = [];
  const quad = (a, b, c2, d, flip) => {
    if (a < 0 || b < 0 || c2 < 0 || d < 0) return;
    if (flip) idx.push(a, d, c2, a, c2, b); else idx.push(a, b, c2, a, c2, d);
  };
  for (let k = 1; k < nz - 1; k++) for (let j = 1; j < ny - 1; j++) for (let i = 1; i < nx - 1; i++) {
    const s0 = v[id(i, j, k)] < 0;
    if (s0 !== (v[id(i + 1, j, k)] < 0)) quad(cell[id(i, j - 1, k - 1)], cell[id(i, j, k - 1)], cell[id(i, j, k)], cell[id(i, j - 1, k)], !s0);
    if (s0 !== (v[id(i, j + 1, k)] < 0)) quad(cell[id(i - 1, j, k - 1)], cell[id(i - 1, j, k)], cell[id(i, j, k)], cell[id(i, j, k - 1)], !s0);
    if (s0 !== (v[id(i, j, k + 1)] < 0)) quad(cell[id(i - 1, j - 1, k)], cell[id(i, j - 1, k)], cell[id(i, j, k)], cell[id(i - 1, j, k)], !s0);
  }
  // Project each vertex onto the true surface and take the field's gradient as its normal.
  const P = new Float32Array(pos), N = new Float32Array(pos.length), e = h * 0.25;
  for (let p = 0; p < P.length; p += 3) {
    let x = P[p], y = P[p + 1], z = P[p + 2], gx = 0, gy = 0, gz = 1;
    for (let it = 0; it < 3; it++) {
      gx = f(x + e, y, z) - f(x - e, y, z); gy = f(x, y + e, z) - f(x, y - e, z); gz = f(x, y, z + e) - f(x, y, z - e);
      const l = Math.hypot(gx, gy, gz) || 1; gx /= l; gy /= l; gz /= l;
      const d = f(x, y, z);
      if (Math.abs(d) > h) break;
      x -= d * gx; y -= d * gy; z -= d * gz;
    }
    P[p] = x; P[p + 1] = y; P[p + 2] = z; N[p] = gx; N[p + 1] = gy; N[p + 2] = gz;
  }
  return {position: P, normal: N, index: new Uint32Array(idx)};
}
const meshField = (f, min, max, h) => surfaceNets(f, min, max, h);
function merged(geos) {
  const g = mergeGeometries(geos.map(x => (x.index ? x : x)), false);
  if (!g.attributes.normal) g.computeVertexNormals();
  return {position: new Float32Array(g.attributes.position.array), normal: new Float32Array(g.attributes.normal.array),
    index: new Uint32Array(g.index ? g.index.array : [...Array(g.attributes.position.count).keys()])};
}

// ---------------------------------------------------------------- colour
const linear = hex => { const c = new THREE.Color(hex); return [c.r, c.g, c.b]; };   // THREE.Color stores linear values
function bodyColours(A, position) {
  const {P, hs, hc} = A, skin = linear(P.skin), lip = linear(P.lip), brow = linear(P.hairColour), blush = linear('#d98576');
  const thick = P.brow > 0.7 ? 0.0068 : 0.0056;
  const out = new Float32Array(position.length);
  for (let i = 0; i < position.length; i += 3) {
    const x = position[i], y = (position[i + 1] - hc[1]) / hs, z = position[i + 2] / hs, ax = Math.abs(x) / hs;
    let c = skin;
    const curve = 0.0026 * (ax / 0.02) ** 2;                         // lips follow the smile line up to the corners
    const lipD = Math.min(Math.hypot(ax / 0.019, (y + 0.0495 - curve) / 0.0062, (z - 0.0905) / 0.0095), Math.hypot(ax / 0.0175, (y + 0.0585 - curve * 0.6) / 0.0072, (z - 0.0885) / 0.0095));
    if (lipD < 1.2) c = mix3(skin, lip, clamp((1.2 - lipD) / 0.3) * 0.9);
    if (z > 0.058 && ax > 0.011 && ax < 0.056) {                      // eyebrow: a filled arch, thicker inside, tapering out
      const t = (ax - 0.011) / 0.045, archY = 0.0228 + 0.0062 * Math.sin(Math.PI * Math.min(1, t * 1.1)) - 0.0015 * t;
      const half = thick * (1 - 0.55 * t), dist = Math.abs(y - archY);
      if (dist < half) c = mix3(c, brow, 0.82 * clamp((half - dist) / (half * 0.45)));
    }
    const ch = Math.hypot((ax - 0.045) / 0.022, (y + 0.022) / 0.02, (z - 0.06) / 0.03);
    if (ch < 1 && z > 0) c = mix3(c, blush, 0.16 * (1 - ch));
    out[i] = c[0]; out[i + 1] = c[1]; out[i + 2] = c[2];
  }
  return out;
}

// ---------------------------------------------------------------- hair
function hairField(A) {
  const {P, hs, hc, at} = A, Y = A.Y;
  const strands = (x, y, z) => 0.0011 * Math.sin(Math.atan2(x, -z) * 34);
  const cut = (d, y, z, ax) => {
    const line = hc[1] + (0.049 + 0.2 * Math.min(ax / hs, 0.07)) * hs;                     // soft curtain fringe: lowest at the centre
    d = smax(d, -Math.max(0.034 * hs - z, y - line), 0.016);
    if (P.hair !== 'short') d = smax(d, -Math.max(0.03 * hs - z, ax - 0.07 * hs, y - line), 0.01);  // face stays clear
    return d;
  };
  if (P.hair === 'short') {
    const cap = ell(at(0, 0.012, -0.014), [0.074 + 0.011, 0.095 + 0.01, 0.096 + 0.011].map(v => v * hs));
    return (x, y, z) => {
      let d = cap(x, y, z) + strands(x, y, z) * 0.6;
      const edge = hc[1] + (0.012 - 0.07 * clamp((0.02 * hs - z) / (0.12 * hs))) * hs;
      d = smax(d, edge - y, 0.01);
      return cut(d, y, z, Math.abs(x));
    };
  }
  const cap = ell(at(0, 0.012, -0.016), [0.074 + 0.014, 0.095 + 0.013, 0.096 + 0.014].map(v => v * hs));
  const curtain = ell(at(0, -0.04, -0.022), [0.09, 0.085, 0.1].map(v => v * hs));
  const back = P.hair === 'long' ? group([ell([0, hc[1] - 0.12 * hs, -0.07 * hs], [0.085 * hs, 0.15 * hs, 0.042 * hs]),
    ell([0, Y.shoulder - 0.07, -0.075], [0.075, 0.07, 0.035])], 0.05) : null;
  const lower = P.hair === 'long' ? Y.shoulder - 0.11 : hc[1] - 0.075 * hs;
  return (x, y, z) => {
    let d = smin(cap(x, y, z), curtain(x, y, z), 0.03);
    if (back) d = smin(d, back(x, y, z), 0.05);
    d += strands(x, y, z);
    d = smax(d, lower - y, 0.02);
    return cut(d, y, z, Math.abs(x));
  };
}

// ---------------------------------------------------------------- garments cut from the body field
function garments(A) {
  const {P, Y, hc, hs, L, R, torso, sc} = A;
  const sides = [L, R];
  const plane = (pt, dir) => (x, y, z) => (x - pt[0]) * dir[0] + (y - pt[1]) * dir[1] + (z - pt[2]) * dir[2];
  const front = (x, y) => surfaceZ(A.body, x, y, 1);
  const drape = P.bust > 0.1 ? ell([0, Y.chest - 0.006, P.ribD * 0.5], [0.105, 0.064, 0.058]) : null;
  const torsoCloth = (x, y, z) => drape ? smin(torso(x, y, z), drape(x, y, z), 0.03) : torso(x, y, z);
  const neckHole = (extra, depth) => ell([0, Y.shoulder + 0.035, 0.012], [P.neckR + extra, 0.05 + depth, P.neckR + extra + 0.004]);
  const out = {};

  // T-shirt: torso band from just below the waist to the shoulders, short sleeves cut square.
  const tee = 0.009, teeHem = Y.waist - 0.075, teeNeck = neckHole(0.026, 0);
  const sleeve = (side, frac, t) => { const dir = norm3([side.E[0] - side.S[0], side.E[1] - side.S[1], side.E[2] - side.S[2]]);
    const cutP = plane(mix3(side.S, side.E, frac), dir); return (x, y, z) => Math.max(side.upper(x, y, z) - t, cutP(x, y, z)); };
  const sl = sides.map(s => sleeve(s, 0.48, tee + 0.003));
  out.top = {f: (x, y, z) => {
    let d = Math.max(torsoCloth(x, y, z) - tee, teeHem - y, y - (Y.shoulder + 0.09));
    d = smin(d, smin(sl[0](x, y, z), sl[1](x, y, z), 0.01), 0.02);
    return smax(d, -teeNeck(x, y, z), 0.006);
  }, box: [[-P.shoulderX - 0.12, teeHem - 0.02, -0.2], [P.shoulderX + 0.12, Y.shoulder + 0.11, 0.22]]};

  // Jacket: looser torso to the hip, full sleeves to the wrist, stand collar, open V front with a centre seam.
  const jt = y => 0.02 + 0.012 * clamp((Y.chest - y) / (Y.chest - Y.crotch));
  const jHem = Y.crotch + 0.025, yV = Y.chest - 0.03;
  const jSleeve = sides.map(s => { const dir = norm3([s.W[0] - s.E[0], s.W[1] - s.E[1], s.W[2] - s.E[2]]); const cutP = plane(mix3(s.E, s.W, 0.9), dir);
    return (x, y, z) => Math.max(smin(s.upper(x, y, z), s.fore(x, y, z), 0.03) - 0.017, cutP(x, y, z)); });
  const collarY = Y.shoulder + 0.032, collarR = P.neckR + 0.03, jNeck = neckHole(0.034, 0.01);
  out.outer = {f: (x, y, z) => {
    let d = Math.max(torsoCloth(x, y, z) - jt(y), jHem - y, y - (Y.shoulder + 0.1));
    d = smin(d, smin(jSleeve[0](x, y, z), jSleeve[1](x, y, z), 0.01), 0.025);
    d = smax(d, -jNeck(x, y, z), 0.006);
    const collar = Math.hypot(Math.hypot(x, (z + 0.005) * 1.12) - collarR, y - collarY) - 0.014;
    d = Math.min(d, Math.max(collar, -(Math.abs(x) - 0.03 - Math.max(0, z) * 0.4)));
    const vee = Math.max(Math.abs(x) - Math.max(0, y - yV) * 0.62, -z);
    d = smax(d, -vee, 0.004);
    d = Math.max(d, -Math.max(Math.abs(x) - 0.002, -z, y - yV));                          // centre opening below the V
    return d;
  }, box: [[-P.shoulderX - 0.2, jHem - 0.02, -0.22], [P.shoulderX + 0.2, Y.shoulder + 0.12, 0.24]]};

  // Trousers: hip section from the waist, legs to just above the ankle, slightly wider towards the hem; waistband.
  const lt = y => 0.012 + 0.014 * clamp((Y.knee - y) / (Y.knee - Y.ankle));
  const pantsTop = Y.waist - 0.005, pantsHem = Y.ankle + 0.035, wb = Y.waist - 0.024;
  out.bottom = {f: (x, y, z) => {
    let d = Math.max(torso(x, y, z) - 0.012, y - pantsTop);
    d = smin(d, Math.max(smin(L.thigh(x, y, z), L.shin(x, y, z), 0.045) - lt(y), pantsHem - y), 0.03);
    d = smin(d, Math.max(smin(R.thigh(x, y, z), R.shin(x, y, z), 0.045) - lt(y), pantsHem - y), 0.03);
    return Math.min(d, Math.max(torso(x, y, z) - 0.017, Math.abs(y - wb) - 0.019));
  }, box: [[-0.3, pantsHem - 0.02, -0.2], [0.3, pantsTop + 0.03, 0.2]]};

  // Dress: fitted bodice with straps, flared knee-length skirt with soft pleats.
  const hem = Y.knee + 0.035, top = Y.chest + 0.062;
  const prof = [[Y.waist, P.waistW + 0.012, P.waistD + 0.014], [Y.pelvis, P.pelvisW + 0.024, P.pelvisD + 0.06], [Y.crotch, P.pelvisW + 0.05, P.pelvisD + 0.075], [hem, P.pelvisW + 0.13, P.pelvisD + 0.13]];
  const radii = y => { for (let i = 1; i < prof.length; i++) if (y >= prof[i][0]) { const t = (prof[i - 1][0] - y) / (prof[i - 1][0] - prof[i][0]); return [lerp(prof[i - 1][1], prof[i][1], t), lerp(prof[i - 1][2], prof[i][2], t)]; } return [prof.at(-1)[1], prof.at(-1)[2]]; };
  const straps = [-1, 1].map(s => { const fx = s * 0.068, fz = front(fx, top + 0.004) + 0.006, bz = surfaceZ(A.body, fx, top + 0.01, -1) - 0.006, t = [s * 0.074, Y.shoulder + 0.012, -0.012];
    return group([cone([fx, top, fz], t, 0.0065, 0.0065), cone(t, [fx, top + 0.01, bz], 0.0065, 0.0065)], 0.004); });
  out.dress = {f: (x, y, z) => {
    let d = Math.max(torsoCloth(x, y, z) - 0.008, Y.pelvis - y, y - top);
    const [rx, rz] = radii(y), pleat = 0.009 * clamp((Y.pelvis - y) / (Y.pelvis - hem));
    const skirt = Math.max((Math.hypot(x / rx, (z + 0.008) / rz) - 1) * Math.min(rx, rz) - pleat * Math.sin(Math.atan2(x, z) * 11), y - Y.waist, hem - y);
    d = smin(d, skirt, 0.03);
    return Math.min(d, straps[0](x, y, z), straps[1](x, y, z));
  }, box: [[-0.36, hem - 0.02, -0.34], [0.36, Y.shoulder + 0.04, 0.34]]};

  // Shoes: the foot offset with a raised sole rim, collar just under the ankle bone.
  out.footwear = {f: (x, y, z) => {
    let d = Infinity;
    for (const s of sides) {
      const shell = Math.max(s.foot(x, y, z) - 0.007, y - (Y.ankle + 0.006));
      const sole = Math.max(s.foot(x, y, z) - 0.011, y - 0.016 * sc);
      d = Math.min(d, smin(shell, sole, 0.004));
    }
    return Math.max(d, -y - 0.004);
  }, box: [[-0.26, -0.01, -0.12], [0.26, Y.ankle + 0.05, 0.28]]};

  // Beanie over the hair, folded cuff above the brow.
  const crown = ell(A.at(0, 0.014, -0.016), [0.074 + 0.026, 0.095 + 0.024, 0.096 + 0.026].map(v => v * hs));
  const cuffY = hc[1] + 0.046 * hs;
  out.headwear = {f: (x, y, z) => {
    const d = Math.max(crown(x, y, z), hc[1] + 0.03 * hs - y);
    return Math.min(d, Math.max(crown(x, y, z) - 0.006, Math.abs(y - cuffY) - 0.016 * hs));
  }, box: [[-0.14, hc[1] + 0.0, -0.16], [0.14, hc[1] + 0.16, 0.14]]};

  // Scarf: wrapped around the neck with two flat tails down the front.
  const scarfLo = Y.shoulder - 0.012, scarfHi = Y.shoulder + 0.075;
  const tails = [-1, 1].map((s, i) => { const x0 = s * 0.028, x1 = s * (0.045 + 0.012 * i), ym = Y.chest + 0.01, y1 = Y.chest - 0.11 - 0.04 * i;
    const z0 = front(x0, Y.shoulder - 0.01) + 0.03, zm = front(x1, ym) + 0.02, z1 = front(x1, y1) + 0.02;
    return group([flatZ(cone([x0, Y.shoulder - 0.005, z0], [x1, ym, zm], 0.024, 0.028), (z0 + zm) / 2, 3),
      flatZ(cone([x1, ym, zm], [x1, y1, z1], 0.028, 0.03), (zm + z1) / 2, 3)], 0.01); });
  out.scarf = {f: (x, y, z) => {
    const wrap = Math.max(smin(A.neck(x, y, z), torso(x, y, z) + 0.01, 0.04) - 0.026, scarfLo - y, y - scarfHi);
    return smin(wrap, Math.min(tails[0](x, y, z), tails[1](x, y, z)), 0.02);
  }, box: [[-0.16, Y.chest - 0.14, -0.14], [0.16, scarfHi + 0.03, 0.22]]};

  // Tie: knot under the collar, blade following the chest.
  const tieYs = [Y.shoulder - 0.005, Y.chest + 0.02, Y.waist + 0.03];
  const tiePts = tieYs.map(y => [0, y, front(0, y) + 0.017]);
  const tieW = [0.018, 0.034, 0.042];
  const blade = [0, 1].map(i => flatZ(cone(tiePts[i], tiePts[i + 1], tieW[i], tieW[i + 1]), (tiePts[i][2] + tiePts[i + 1][2]) / 2, 5));
  const knot = ell(add3(tiePts[0], [0, 0.016, 0.002]), [0.016, 0.015, 0.011]);
  out.tie = {f: (x, y, z) => Math.min(smin(blade[0](x, y, z), blade[1](x, y, z), 0.01), knot(x, y, z)),
    box: [[-0.08, Y.waist - 0.03, -0.05], [0.08, Y.shoulder + 0.05, 0.26]]};

  // Belt: a band over the trousers' waistband with a front buckle.
  const by = Y.waist - 0.034, bz = front(0, by);
  const buckle = rbox([0, by, bz + 0.024], [0.022, 0.019, 0.005], 0.003);
  out.belt = {f: (x, y, z) => Math.min(Math.max(torso(x, y, z) - 0.022, Math.abs(y - by) - 0.017), buckle(x, y, z)),
    box: [[-0.28, by - 0.04, -0.2], [0.28, by + 0.04, 0.22]]};

  // Crossbody bag: pouch at the front hip, strap over the left shoulder.
  const bagC = [0.12, Y.pelvis - 0.01, 0]; bagC[2] = front(0.12, bagC[1]) + 0.032;
  const pouch = rbox(bagC, [0.085, 0.07, 0.026], 0.018);
  out.bag = {f: pouch, box: [[0.0, bagC[1] - 0.1, bagC[2] - 0.06], [0.24, bagC[1] + 0.1, bagC[2] + 0.06]],
    extra: () => {
      const strap = (n, end, dir, off) => { const pts = [];
        for (let i = 0; i <= n; i++) { const t = i / n; const x = lerp(-P.shoulderX * 0.55, end[0], t), y = lerp(Y.shoulder + 0.03, end[1], t);
          pts.push(new THREE.Vector3(x, y, surfaceZ(A.body, x, y, dir) + off)); }
        return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), n * 5, 0.0055, 8); };
      return [strap(14, [bagC[0] + 0.07, bagC[1] + 0.06], 1, 0.012), strap(10, [bagC[0] + 0.1, bagC[1] + 0.05], -1, -0.012)];
    }};
  // Default modest layer (always worn unless underwear is equipped): fitted tank and boxer-briefs.
  const scoop = ell([0, Y.shoulder + 0.03, 0.02], [P.neckR + 0.035, 0.07, P.neckR + 0.05]);
  const tank = (x, y, z) => smax(Math.max(torsoCloth(x, y, z) - 0.0045, Y.waist - 0.04 - y, y - (Y.shoulder + 0.02)), -scoop(x, y, z), 0.006);
  const armholes = sides.map(s => ell(add3(s.S, [s.s * 0.012, -0.03, 0]), [0.05, 0.085, 0.07]));
  const tankCut = (x, y, z) => Math.max(tank(x, y, z), -Math.min(armholes[0](x, y, z), armholes[1](x, y, z)));
  // Lower garments follow the full body surface (hip joints included), kept clear of the hanging hands.
  const hipW = P.hipX + P.thigh[0] + 0.045;
  const lower = (x, y, z) => smin(smin(torso(x, y, z), L.leg(x, y, z), 0.05), R.leg(x, y, z), 0.05);
  const shorts = (x, y, z) => Math.max(lower(x, y, z) - 0.006, y - (Y.waist - 0.045), (Y.crotch - 0.1) - y, Math.abs(x) - hipW);
  const briefs = (x, y, z) => Math.max(lower(x, y, z) - 0.005, y - (Y.pelvis - 0.008), (Y.crotch - 0.028) - y + 0.06 * Math.max(0, Math.abs(x) - 0.03), Math.abs(x) - hipW);
  const bra = (x, y, z) => Math.max(torsoCloth(x, y, z) - 0.005, Y.chest - 0.065 - y, y - (Y.chest + 0.05));
  const box = [[-0.32, Y.crotch - 0.14, -0.22], [0.32, Y.shoulder + 0.08, 0.24]];
  // Two parts, so clothing hides only the part it covers (base-top under tops/dresses, base-bottom under bottoms/dresses).
  out.base = {f: tankCut, box, part: 'base-top', more: {name: 'base-bottom', f: shorts}};
  out.underwear = {f: P.bust > 0.1 ? (x, y, z) => Math.min(bra(x, y, z), briefs(x, y, z))
    : P.pec > 0.5 ? (x, y, z) => Math.min(tankCut(x, y, z) + 0.0005, shorts(x, y, z) + 0.0005)
    : (x, y, z) => Math.min(Math.max(bra(x, y, z), y - (Y.chest + 0.04)), briefs(x, y, z)), box};
  return out;
}

/** Small hardware built as plain geometry (too fine for the field's resolution). */
function hardware(A) {
  const {hs, hc, Y, eyes} = A;
  const ey = eyes[0][1], ez = eyes[0][2] + 0.024 * hs;
  const lens = s => { const g = new THREE.TorusGeometry(0.019 * hs, 0.0026, 10, 48); g.scale(1.15, 0.85, 1); g.translate(s * 0.032 * hs, ey, ez); return g; };
  const temple = s => { const g = new THREE.CylinderGeometry(0.0022, 0.0022, 0.1 * hs, 8); g.rotateX(Math.PI / 2); g.translate(s * 0.074 * hs, ey + 0.004, ez - 0.05 * hs); return g; };
  const bridge = new THREE.CylinderGeometry(0.0022, 0.0022, 0.02 * hs, 8); bridge.rotateZ(Math.PI / 2); bridge.translate(0, ey + 0.004, ez + 0.002);
  const eyewear = [lens(-1), lens(1), temple(-1), temple(1), bridge];
  const ear = s => [s * (0.078 * hs + 0.004), hc[1] - 0.03 * hs, -0.002 * hs];
  const earrings = [-1, 1].flatMap(s => { const p = ear(s); const hoop = new THREE.TorusGeometry(0.009, 0.0016, 8, 32); hoop.rotateY(Math.PI / 2); hoop.translate(p[0], p[1] - 0.009, p[2]);
    const stud = new THREE.SphereGeometry(0.0032, 12, 8); stud.translate(...p); return [hoop, stud]; });
  const chain = [];
  for (let i = 0; i < 48; i++) { const th = (i / 48) * Math.PI * 2; const y = Y.shoulder + 0.022 - 0.045 * Math.max(0, Math.cos(th)) ** 1.5;
    const r = surfaceRay(A.body, y, th) + 0.004; chain.push(new THREE.Vector3(Math.sin(th) * r, y, Math.cos(th) * r)); }
  const low = chain[0];
  const pendant = new THREE.SphereGeometry(0.0075, 16, 12); pendant.scale(1, 1.25, 0.55); pendant.translate(low.x, low.y - 0.011, low.z + 0.003);
  const necklace = [new THREE.TubeGeometry(new THREE.CatmullRomCurve3(chain, true), 128, 0.0019, 6, true), pendant];
  return {eyewear, earrings, necklace};
}

/** Point accessories, sized to this body and centred on their attachment point. */
function pointTemplates(A) {
  const {P, sc} = A;
  const axisTo = (g, dir) => { g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(...dir))); return g; };
  const band = axisTo(new THREE.TorusGeometry(P.fArm[1] + 0.006, 0.0055, 12, 48), norm3([0, -Math.cos(0.11), 0.1]));
  const face = new THREE.CylinderGeometry(0.016, 0.016, 0.008, 32); face.rotateX(Math.PI / 2); face.translate(0, 0, P.fArm[1] + 0.009);
  const ring = axisTo(new THREE.TorusGeometry(0.0092 * sc * P.hand + 0.0012, 0.0016, 8, 32), [0, -1, 0]);
  const pin = new THREE.CylinderGeometry(0.014, 0.014, 0.005, 32); pin.rotateX(Math.PI / 2);
  const gem = new THREE.SphereGeometry(0.0065, 16, 12); gem.scale(1, 1, 0.7); gem.translate(0, 0, 0.004);
  return {wrist: [band, face], ring: [ring], accessory: [pin, gem]};
}

function attachPoints(A) {
  const {Y, hc, hs, L, R, P} = A, front = (x, y, extra) => [x, y, surfaceZ(A.body, x, y, 1) + extra];
  const ringAt = s => [s.W[0] - s.s * 0.008, s.W[1] - 0.088 * A.sc * P.hand - 0.004, s.W[2] - 0.007 * A.sc * P.hand];
  const wristAt = s => add3(s.W, [0, 0.026, -0.003]);
  return {
    top: [0, Y.chest, 0], outer: [0, Y.chest, 0], underwear: [0, Y.pelvis, 0], bottom: [0, Y.waist, 0], dress: [0, Y.waist, 0], footwear: [0, 0, 0.05],
    headwear: [0, hc[1] + 0.1 * hs, 0], eyewear: A.eyes[0], earrings: [0, hc[1] - 0.03 * hs, 0], necklace: [0, Y.shoulder, 0],
    scarf: [0, Y.shoulder, 0], tie: [0, Y.chest, 0], belt: [0, Y.waist, 0], bag: [0.12, Y.pelvis, 0],
    wrist_l: wristAt(L), wrist_r: wristAt(R), ring_l: ringAt(L), ring_r: ringAt(R),
    accessory_1: front(-0.085, Y.chest + 0.065, 0.03), accessory_2: front(0.085, Y.chest + 0.065, 0.03), accessory_3: front(0, Y.waist + 0.02, 0.036),
  };
}

// ---------------------------------------------------------------- glTF output
const CAPACITY = {top: 1, outer: 1, bottom: 1, dress: 1, footwear: 1, underwear: 1, bag: 1, headwear: 1, eyewear: 1, earrings: 1, necklace: 1,
  tie: 1, scarf: 1, belt: 1, wrist: 2, ring: 2, accessory: 3};
const POSITIONS = {wrist: ['attach_wrist_l', 'attach_wrist_r'], ring: ['attach_ring_l', 'attach_ring_r'],
  accessory: ['attach_accessory_1', 'attach_accessory_2', 'attach_accessory_3']};
const POINT = new Set(['wrist', 'ring', 'accessory']);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder': MeshoptEncoder});
await MeshoptEncoder.ready; await MeshoptSimplifier.ready;

async function glb(meshes, points = {}, {ratio = 0.4, error = 0.00035} = {}) {
  const doc = new Document(), buffer = doc.createBuffer(), scene = doc.createScene();
  for (const m of meshes) {
    const prim = doc.createPrimitive()
      .setAttribute('POSITION', doc.createAccessor().setType('VEC3').setArray(m.position).setBuffer(buffer))
      .setAttribute('NORMAL', doc.createAccessor().setType('VEC3').setArray(m.normal).setBuffer(buffer))
      .setIndices(doc.createAccessor().setType('SCALAR').setArray(m.index).setBuffer(buffer))
      .setMaterial(doc.createMaterial(m.material).setBaseColorFactor([...linear(m.colour ?? '#9e959b'), 1]).setRoughnessFactor(m.roughness ?? 0.8).setMetallicFactor(0));
    if (m.color) prim.setAttribute('COLOR_0', doc.createAccessor().setType('VEC3').setArray(m.color).setBuffer(buffer));
    scene.addChild(doc.createNode(m.name).setMesh(doc.createMesh(m.name).addPrimitive(prim)));
  }
  for (const [name, p] of Object.entries(points)) scene.addChild(doc.createNode(`attach_${name}`).setTranslation(p));
  const steps = [weld()];
  if (ratio < 1) steps.push(simplify({simplifier: MeshoptSimplifier, ratio, error}));
  steps.push(quantize({quantizeNormal: 10, quantizePosition: 14, quantizeColor: 8}), meshopt({encoder: MeshoptEncoder, level: 'medium'}));
  await doc.transform(...steps);
  return Buffer.from(await io.writeBinary(doc));
}

mkdirSync(OUT, {recursive: true});
const only = process.argv[2];
if (!only) for (const f of readdirSync(OUT)) if (f.endsWith('.glb')) rmSync(join(OUT, f));
let bytes = 0;
const write = (file, buf) => { writeFileSync(join(OUT, file), buf); bytes += buf.length; console.log(`  ${file} ${Math.round(buf.length / 1024)} KB`); };
for (const [key, P] of Object.entries(BODIES)) {
  if (only && only !== key) continue;
  const A = anatomy(P), H = P.H, t0 = Date.now();
  console.log(`${key}:`);
  const neckCut = A.hc[1] - 0.15 * A.hs;
  const torsoMesh = meshField(A.body, [-0.42, -0.004, -0.2], [0.42, neckCut + 0.012, 0.3], 0.004);
  const headMesh = meshField(A.body, [-0.12, neckCut - 0.012, -0.13], [0.12, H + 0.01, 0.14], 0.0016);
  const skin = {position: new Float32Array([...torsoMesh.position, ...headMesh.position]), normal: new Float32Array([...torsoMesh.normal, ...headMesh.normal]),
    index: new Uint32Array([...torsoMesh.index, ...headMesh.index.map(i => i + torsoMesh.position.length / 3)])};
  skin.color = bodyColours(A, skin.position);
  const hair = meshField(hairField(A), [-0.13, A.Y.shoulder - 0.16, -0.17], [0.13, H + 0.03, 0.14], 0.0028);
  const eyes = merged(A.eyes.map(c => { const g = new THREE.SphereGeometry(A.EYE_R, 32, 24); g.translate(...c); return g; }));
  const irises = merged(A.eyes.map(c => { const g = new THREE.SphereGeometry(0.0072 * A.hs, 24, 16); g.scale(1, 1, 0.42); g.translate(c[0], c[1] - 0.0006, c[2] + A.EYE_R - 0.0016); return g; }));
  const pupils = merged(A.eyes.map(c => { const g = new THREE.SphereGeometry(0.0034 * A.hs, 16, 12); g.scale(1, 1, 0.4); g.translate(c[0], c[1] - 0.0006, c[2] + A.EYE_R + 0.0002); return g; }));
  console.log(`  meshed body in ${Date.now() - t0} ms (${skin.position.length / 3} vertices)`);
  write(`body-${key}.glb`, await glb([
    {name: `body-${key}`, material: 'skin', colour: '#ffffff', roughness: 0.6, ...skin},
    {name: 'hair', material: 'hair', colour: P.hairColour, roughness: 0.72, ...hair},
    {name: 'eyes', material: 'eyes', colour: '#f2ebe5', roughness: 0.2, ...eyes},
    {name: 'iris', material: 'iris', colour: '#6b4630', roughness: 0.12, ...irises},
    {name: 'pupil', material: 'pupil', colour: '#120b09', roughness: 0.08, ...pupils},
  ], attachPoints(A), {ratio: 0.32, error: 0.00025}));
  for (const [slot, g] of Object.entries(garments(A))) {
    const h = slot === 'base' || slot === 'underwear' ? 0.0035 : 0.0045, colour = slot === 'base' ? '#8c7f88' : undefined;
    const parts = [{name: g.part ?? slot, material: slot, colour, ...meshField(g.f, ...g.box, h)}];
    if (g.more) parts.push({name: g.more.name, material: slot, colour, ...meshField(g.more.f, ...g.box, h)});
    if (g.extra) parts.push({name: `${slot}-strap`, material: slot, ...merged(g.extra())});
    write(`${slot}-${key}.glb`, await glb(parts));
  }
  for (const [slot, geos] of [...Object.entries(hardware(A)), ...Object.entries(pointTemplates(A))])
    write(`${slot}-${key}.glb`, await glb([{name: slot, material: slot, ...merged(geos)}], {}, {ratio: 1}));
  console.log(`  ${key} done in ${Math.round((Date.now() - t0) / 1000)} s`);
}
const manifest = {
  version: 3,
  note: 'Generated by scripts/make-avatar-models.mjs. One body per avatar_gender setting; every template is fitted to its body ({body}); point accessories hang on the body\'s attach_* nodes. Meshopt-compressed: load with GLTFLoader.setMeshoptDecoder.',
  bodies: Object.fromEntries(Object.keys(BODIES).map(k => [k, `body-${k}.glb`])),
  base: 'base-{body}.glb',
  slots: Object.fromEntries(Object.entries(CAPACITY).map(([slot, capacity]) => [slot,
    {template: `${slot}-{body}.glb`, anchor: POINT.has(slot) ? 'point' : 'body', capacity, positions: POSITIONS[slot] ?? [`attach_${slot}`]}])),
};
writeFileSync(join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`total ${Math.round(bytes / 1024)} KB`);
