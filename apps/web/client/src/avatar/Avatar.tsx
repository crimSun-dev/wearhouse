import {useEffect, useRef, useState} from 'react';
import {Minus, Plus, RotateCcw, RotateCw} from 'lucide-react';
import {useI18n} from '../i18n/index.tsx';
import {accentFor} from '../components/tiles.tsx';
import {Segmented} from '../components/ui.tsx';
import type {AvatarScene, Worn} from './scene.ts';
import './avatar.css';

/** Neutral garment colour for unknown colour names (the documented approximation: see components/tiles.tsx). */
export const NEUTRAL = '#9e959b';
const BODY_KEY = 'wearhouse.avatarBody';
const FALLBACK_KEY = 'wearhouse.avatarFallback';
type Mode = 'loading' | '3d' | '2d';
type Reason = 'noWebgl' | 'failed' | 'lowFps' | null;

export type AvatarPiece = {slot: string; colour: string | null | undefined};

function hasWebGL() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
}
function stored(key: string) { try { return window.localStorage.getItem(key); } catch { return null; } }
function store(key: string, value: string | null) {
  try { if (value === null) window.localStorage.removeItem(key); else window.localStorage.setItem(key, value); } catch { /* preference not persisted */ }
}
/** Pieces to render: each slot's items in order, so two wrist items land on the left and right wrist points. */
export function toWorn(pieces: AvatarPiece[]): Worn[] {
  const seen: Record<string, number> = {};
  return pieces.map(p => ({slot: p.slot, index: (seen[p.slot] = (seen[p.slot] ?? -1) + 1), colour: accentFor(p.colour) ?? NEUTRAL}));
}

/**
 * The fitting room avatar. 3D loads after the page is idle; until then, without WebGL, on a model failure or below
 * 30 fps, the 2D layered view renders the same look and a label says which view is shown and why.
 */
export function Avatar({pieces}: {pieces: AvatarPiece[]}) {
  const {t} = useI18n();
  const canvas = useRef<HTMLCanvasElement>(null);
  const scene = useRef<AvatarScene | null>(null);
  const [body, setBody] = useState(() => stored(BODY_KEY) ?? 'a');
  const [reason, setReason] = useState<Reason>(() => (stored(FALLBACK_KEY) === 'lowFps' ? 'lowFps' : null));
  const [mode, setMode] = useState<Mode>(() => (reason ? '2d' : 'loading'));
  const [attempt, setAttempt] = useState(0);
  const worn = toWorn(pieces);
  const wornKey = JSON.stringify(worn);

  useEffect(() => {
    if (reason) { setMode('2d'); return; }
    if (!hasWebGL()) { setReason('noWebgl'); setMode('2d'); return; }
    let cancelled = false; let stopFps = () => {};
    const idle = (cb: () => void) => ('requestIdleCallback' in window ? window.requestIdleCallback(cb, {timeout: 1500}) : globalThis.setTimeout(cb, 300));
    idle(() => {
      if (cancelled || !canvas.current) return;
      import('./scene.ts').then(m => m.createAvatarScene(canvas.current!, body)).then(s => {
        if (cancelled) { s.dispose(); return; }
        scene.current = s; setMode('3d');
        // Frame-rate guard: over the first 3 s of spinning frames, a median below 30 fps switches this device to 2D.
        const samples: number[] = []; const stopSpin = s.spin(0.6);
        stopFps = s.onFrame(ms => {
          samples.push(ms);
          if (samples.reduce((a, b) => a + b, 0) < 3000) return;
          stopFps(); stopSpin();
          const sorted = [...samples].sort((a, b) => a - b); const median = 1000 / sorted[Math.floor(sorted.length / 2)]!;
          if (median < 30) { store(FALLBACK_KEY, 'lowFps'); setReason('lowFps'); s.dispose(); scene.current = null; }
        });
      }).catch(() => { if (!cancelled) { setReason('failed'); setMode('2d'); } });
    });
    return () => { cancelled = true; stopFps(); scene.current?.dispose(); scene.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reason, attempt]);

  useEffect(() => { void scene.current?.show(worn); }, [wornKey, mode]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { store(BODY_KEY, body); void scene.current?.setBody(body); }, [body]);

  const label = mode === '3d' ? t('av.mode3d') : mode === 'loading' ? t('av.loading') : t('av.mode2d');
  const why = reason === 'noWebgl' ? t('av.noWebgl') : reason === 'failed' ? t('av.failed') : reason === 'lowFps' ? t('av.lowFps') : null;
  return <figure className={`avatar avatar-${mode}`} data-mode={mode}>
    <div className="avatar-stage">
      {mode !== '2d' && <canvas ref={canvas} className="avatar-canvas" tabIndex={0} aria-label={t('av.canvas')}
        onKeyDown={e => {
          if (e.key === 'ArrowLeft') { e.preventDefault(); e.stopPropagation(); scene.current?.rotate(-0.3); }
          else if (e.key === 'ArrowRight') { e.preventDefault(); e.stopPropagation(); scene.current?.rotate(0.3); }
          else if (e.key === '+' || e.key === '=') scene.current?.zoom(-0.4);
          else if (e.key === '-') scene.current?.zoom(0.4);
        }}
        onPointerDown={e => { (e.target as HTMLElement).setPointerCapture(e.pointerId); }}
        onPointerMove={e => { if (e.buttons) scene.current?.rotate(e.movementX * 0.01); }}
        onWheel={e => scene.current?.zoom(e.deltaY * 0.002)} />}
      {mode !== '3d' && <Flat worn={worn} />}
    </div>
    <figcaption className="avatar-caption">
      <span className="tag tag-quiet avatar-mode" role="status">{label}</span>
      {why && <span className="avatar-why">{why}</span>}
      {reason && reason !== 'noWebgl' && <button type="button" className="link-btn" onClick={() => { store(FALLBACK_KEY, null); setReason(null); setMode('loading'); setAttempt(a => a + 1); }}>{t('av.try3d')}</button>}
      <span className="muted small">{t('av.approx')}</span>
    </figcaption>
    <div className="avatar-controls">
      <Segmented label={t('av.body')} value={body} onChange={setBody} options={[{value: 'a', label: t('av.bodyA')}, {value: 'b', label: t('av.bodyB')}]} />
      {mode === '3d' && <span className="avatar-buttons">
        <button type="button" aria-label={t('av.rotateLeft')} onClick={() => scene.current?.rotate(-0.4)}><RotateCcw size={16} /></button>
        <button type="button" aria-label={t('av.rotateRight')} onClick={() => scene.current?.rotate(0.4)}><RotateCw size={16} /></button>
        <button type="button" aria-label={t('av.zoomIn')} onClick={() => scene.current?.zoom(-0.4)}><Plus size={16} /></button>
        <button type="button" aria-label={t('av.zoomOut')} onClick={() => scene.current?.zoom(0.4)}><Minus size={16} /></button>
      </span>}
    </div>
  </figure>;
}

/** 2D layered SVG: a body silhouette with one shape per worn slot, coloured by the same approximation table. */
const SHAPES: Record<string, (i: number) => string> = {
  top: () => 'M70 92 L130 92 L140 112 L132 118 L128 160 L72 160 L68 118 L60 112 Z',
  outer: () => 'M64 90 L136 90 L150 168 L136 170 L132 176 L68 176 L64 170 L50 168 Z',
  bottom: () => 'M72 160 L128 160 L132 262 L106 262 L100 196 L94 262 L68 262 Z',
  dress: () => 'M74 92 L126 92 L130 130 L150 230 L50 230 L70 130 Z',
  footwear: () => 'M66 262 L96 262 L98 276 L60 276 Z M104 262 L134 262 L140 276 L102 276 Z',
  headwear: () => 'M76 34 Q100 10 124 34 L132 40 L68 40 Z',
  eyewear: () => 'M84 52 h12 v6 h-12 Z M104 52 h12 v6 h-12 Z M96 54 h8 v2 h-8 Z',
  earrings: () => 'M78 62 a3 3 0 1 0 0.1 0 Z M122 62 a3 3 0 1 0 0.1 0 Z',
  necklace: () => 'M86 86 Q100 104 114 86 L112 86 Q100 100 88 86 Z',
  scarf: () => 'M82 80 L118 80 L120 92 L112 92 L112 124 L104 124 L104 92 L80 92 Z',
  tie: () => 'M97 92 L103 92 L106 140 L100 148 L94 140 Z',
  belt: () => 'M70 156 L130 156 L131 164 L69 164 Z',
  bag: () => 'M138 150 L162 150 L164 182 L136 182 Z M142 150 Q150 128 158 150',
  wrist: i => (i === 0 ? 'M50 164 h12 v6 h-12 Z' : 'M138 164 h12 v6 h-12 Z'),
  ring: i => (i === 0 ? 'M54 182 a3 3 0 1 0 0.1 0 Z' : 'M146 182 a3 3 0 1 0 0.1 0 Z'),
  accessory: i => ['M84 104 a4 4 0 1 0 0.1 0 Z', 'M116 104 a4 4 0 1 0 0.1 0 Z', 'M100 138 a4 4 0 1 0 0.1 0 Z'][i] ?? '',
};
const ORDER = ['bottom', 'dress', 'top', 'outer', 'belt', 'tie', 'scarf', 'necklace', 'footwear', 'bag', 'wrist', 'ring', 'accessory', 'earrings', 'eyewear', 'headwear'];

function Flat({worn}: {worn: Worn[]}) {
  const sorted = [...worn].sort((a, b) => ORDER.indexOf(a.slot) - ORDER.indexOf(b.slot));
  return <svg className="avatar-flat" viewBox="0 0 200 290" role="img" aria-hidden>
    <g className="avatar-body">
      <circle cx="100" cy="56" r="20" /><rect x="92" y="74" width="16" height="12" rx="4" />
      <path d="M72 88 L128 88 L136 160 L64 160 Z" /><path d="M64 92 L52 172 L60 174 L72 104 Z M136 92 L148 172 L140 174 L128 104 Z" />
      <path d="M72 160 L98 160 L96 266 L76 266 Z M102 160 L128 160 L124 266 L104 266 Z" />
    </g>
    {sorted.map(w => <path key={`${w.slot}-${w.index}`} className={`avatar-piece avatar-${w.slot}`} d={SHAPES[w.slot]?.(w.index) ?? ''} fill={w.colour} />)}
  </svg>;
}
