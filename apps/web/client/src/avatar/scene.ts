// The 3D avatar renderer (task 5.2). Loaded lazily (dynamic import) so Three.js never blocks the page.
import {AmbientLight, Color, DirectionalLight, Group, HemisphereLight, Mesh, MeshStandardMaterial, PerspectiveCamera, Scene, WebGLRenderer,
  type Object3D} from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

export type Manifest = {bodies: Record<string, string>; slots: Record<string, {template: string; capacity: number; positions: string[]}>};
export type Worn = {slot: string; index: number; colour: string};
export type AvatarScene = {
  show: (worn: Worn[]) => Promise<void>;
  setBody: (body: string) => Promise<void>;
  rotate: (radians: number) => void;
  zoom: (delta: number) => void;
  /** Spins continuously (the frame-rate route); returns a stop function. */
  spin: (radiansPerSecond: number) => () => void;
  onFrame: (cb: (ms: number) => void) => () => void;
  dispose: () => void;
};

const base = () => `${import.meta.env.BASE_URL}avatar/`;

export async function createAvatarScene(canvas: HTMLCanvasElement, body: string): Promise<AvatarScene> {
  const manifest = await fetch(`${base()}manifest.json`).then(r => { if (!r.ok) throw new Error('avatar manifest ' + r.status); return r.json() as Promise<Manifest>; });
  const renderer = new WebGLRenderer({canvas, antialias: true, alpha: true, powerPreference: 'low-power'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new Scene();
  const camera = new PerspectiveCamera(30, 1, 0.1, 20);
  let distance = 4.2;
  const place = () => { camera.position.set(0, 1.05, distance); camera.lookAt(0, 0.95, 0); };
  place();
  scene.add(new HemisphereLight(0xffffff, 0x442233, 1.1), new AmbientLight(0xffffff, 0.35));
  const key = new DirectionalLight(0xffffff, 1.4); key.position.set(1.5, 3, 2.5); scene.add(key);
  const rig = new Group(); scene.add(rig);
  const loader = new GLTFLoader();
  const cache = new Map<string, Promise<Object3D>>();
  const model = (file: string) => {
    if (!cache.has(file)) cache.set(file, loader.loadAsync(base() + file).then(g => g.scene));
    return cache.get(file)!.then(s => s.clone(true));
  };
  let bodyNode: Object3D | null = null;
  const garments = new Group(); rig.add(garments);
  let worn: Worn[] = [];

  const resize = () => {
    const {clientWidth: w, clientHeight: h} = canvas;
    if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  };
  const frameListeners = new Set<(ms: number) => void>();
  let raf = 0, last = performance.now(), spinRate = 0, dirty = true;
  const loop = (now: number) => {
    raf = requestAnimationFrame(loop);
    const dt = now - last; last = now;
    if (spinRate) { rig.rotation.y += spinRate * dt / 1000; dirty = true; }
    if (!dirty && !frameListeners.size) return;
    resize(); renderer.render(scene, camera); dirty = false;
    for (const l of frameListeners) l(dt);
  };
  raf = requestAnimationFrame(loop);

  const attach = async () => {
    garments.clear();
    if (!bodyNode) return;
    for (const w of worn) {
      const spec = manifest.slots[w.slot];
      if (!spec) continue;
      const point = bodyNode.getObjectByName(spec.positions[Math.min(w.index, spec.positions.length - 1)]!);
      const garment = await model(spec.template);
      garment.traverse(o => { if ((o as Mesh).isMesh) (o as Mesh).material = new MeshStandardMaterial({color: new Color(w.colour), roughness: 0.85}); });
      if (point) garment.position.copy(point.position);
      garments.add(garment);
    }
    dirty = true;
  };
  const setBody = async (b: string) => {
    const file = manifest.bodies[b] ?? Object.values(manifest.bodies)[0]!;
    const next = await model(file);
    if (bodyNode) rig.remove(bodyNode);
    bodyNode = next; rig.add(next);
    await attach();
  };
  await setBody(body);
  return {
    show: async next => { worn = next; await attach(); },
    setBody,
    rotate: r => { rig.rotation.y += r; dirty = true; },
    zoom: d => { distance = Math.min(7, Math.max(2.2, distance + d)); place(); dirty = true; },
    spin: rate => { spinRate = rate; return () => { spinRate = 0; }; },
    onFrame: cb => { frameListeners.add(cb); return () => frameListeners.delete(cb); },
    dispose: () => { cancelAnimationFrame(raf); renderer.dispose(); scene.clear(); },
  };
}
