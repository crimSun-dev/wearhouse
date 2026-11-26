import {useEffect, useRef, useState} from 'react';
import {useSearchParams} from 'react-router';
import {useI18n} from '../../i18n/index.tsx';
import {Button} from '../../components/ui.tsx';
import {toWorn} from '../../avatar/Avatar.tsx';
import type {AvatarScene} from '../../avatar/scene.ts';
import '../../avatar/avatar.css';

/** Every slot worn at once: the heaviest look the avatar can show. */
const FULL_LOOK = ['outer', 'top', 'bottom', 'footwear', 'headwear', 'eyewear', 'earrings', 'necklace', 'scarf', 'belt', 'bag',
  'wrist', 'wrist', 'ring', 'ring', 'accessory', 'accessory', 'accessory'].map((slot, i) => ({slot, colour: ['Beige', 'White', 'Black', 'Navy', 'Red', 'Gold'][i % 6]}));

function device() {
  const c = document.createElement('canvas'); const gl = c.getContext('webgl2') ?? c.getContext('webgl');
  const ext = gl?.getExtension('WEBGL_debug_renderer_info');
  const nav = navigator as Navigator & {deviceMemory?: number};
  return {userAgent: navigator.userAgent, cores: navigator.hardwareConcurrency, memoryGb: nav.deviceMemory ?? null,
    gpu: gl ? String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : 'no WebGL',
    screen: `${screen.width}×${screen.height} @${devicePixelRatio}x`};
}

/** #/dev/avatar-fps: rotates a full look for 60 s (or ?s=N) and reports the median frame rate and the device. */
export function AvatarFpsRoute() {
  const {t} = useI18n();
  const [params] = useSearchParams();
  const seconds = Number(params.get('s') ?? 60);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [left, setLeft] = useState<number | null>(null);
  const [result, setResult] = useState<{median: number; frames: number; device: ReturnType<typeof device>} | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scene = useRef<AvatarScene | null>(null);
  useEffect(() => () => scene.current?.dispose(), []);
  const run = async () => {
    setResult(null); setError(null);
    try {
      const {createAvatarScene} = await import('../../avatar/scene.ts');
      scene.current?.dispose();
      const s = await createAvatarScene(canvas.current!, 'a');
      scene.current = s;
      await s.show(toWorn(FULL_LOOK));
      const samples: number[] = []; const start = performance.now();
      const stopSpin = s.spin(Math.PI * 2 / 8);
      const timer = setInterval(() => setLeft(Math.max(0, Math.ceil(seconds - (performance.now() - start) / 1000))), 250);
      const stop = s.onFrame(ms => {
        if (performance.now() - start < 500) return;      // skip the first frames (shader compile)
        samples.push(ms);
        if (performance.now() - start >= seconds * 1000) {
          stop(); stopSpin(); clearInterval(timer); setLeft(null);
          const sorted = [...samples].sort((a, b) => a - b);
          const median = Math.round(10000 / sorted[Math.floor(sorted.length / 2)]!) / 10;
          if (median < 30) try { window.localStorage.setItem('wearhouse.avatarFallback', 'lowFps'); } catch { /* not persisted */ }
          setResult({median, frames: samples.length, device: device()});
        }
      });
    } catch (e) { setError(String(e)); }
  };
  return <section className="page page-read">
    <h1>{t('av.fpsTitle')}</h1>
    <div className="avatar-stage" style={{maxWidth: 420}}><canvas ref={canvas} className="avatar-canvas" /></div>
    <Button variant="primary" onClick={() => void run()} disabled={left !== null}>{left !== null ? t('av.fpsRunning', {s: left}) : t('av.fpsStart')}</Button>
    {error && <p className="form-error" role="alert">{error}</p>}
    {result && <div data-testid="fps-result" data-median={result.median}>
      <p><strong>{t('av.fpsResult', {fps: result.median, frames: result.frames})}</strong></p>
      {result.median < 30 && <p className="form-error">{t('av.fpsBelow')}</p>}
      <h2>{t('av.fpsDevice')}</h2><pre className="small">{JSON.stringify(result.device, null, 2)}</pre>
    </div>}
  </section>;
}
