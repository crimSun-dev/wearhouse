import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {color} from './domain.js';

const templates = {top:'top_shirt.glb',outer:'outer_jacket.glb',dress:'dress.glb',footwear:'footwear_sneaker.glb'};
const models = import.meta.env.BASE_URL + 'models/';
const loader = new GLTFLoader();
let pending;
function dispose(object) {
  object.traverse(child => {
    child.geometry?.dispose();
    for (const material of Array.isArray(child.material) ? child.material : [child.material]) {
      material?.map?.dispose();
      material?.dispose();
    }
  });
}
function limbs(group, material, points) {
  for (const [x,y,z,a,b,c] of points) {
    const mesh = new T.Mesh(new T.BoxGeometry(a,b,c), material.clone());
    mesh.position.set(x,y,z);
    group.add(mesh);
  }
  material.dispose();
}
export function mountViewer(stage, items, avatar, angle) {
  pending?.();
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(31, 1, .1, 30);
  camera.position.set(0,1.6,5);
  camera.lookAt(0,1.35,0);
  const renderer = new T.WebGLRenderer({alpha:true,antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  const figure = new T.Group();
  figure.rotation.y = angle;
  scene.add(figure, new T.HemisphereLight('#fff5ee','#836174',2));
  const key = new T.DirectionalLight('#fff4ed',2.1);
  key.position.set(3,6,5);
  scene.add(key);
  const material = tint => new T.MeshStandardMaterial({color:tint,roughness:.86});
  const skin = material('#bd826f');
  const hair = material('#34242b');
  const head = new T.Mesh(new T.SphereGeometry(.18,20,16),skin.clone());
  const hairMesh = new T.Mesh(new T.SphereGeometry(.187,20,16,0,Math.PI*2,0,Math.PI*.55),hair);
  head.position.set(0,2.34,0);
  hairMesh.position.copy(head.position);
  const body = new T.Group();
  body.add(head,hairMesh);
  limbs(body,skin,[[0,2.1,0,.13,.17,.12],[0,1.76,0,.41,.55,.23],[-.28,1.66,0,.12,.66,.15],[.28,1.66,0,.12,.66,.15],[-.12,.77,0,.135,1,.16],[.12,.77,0,.135,1,.16]]);
  figure.add(body);
  const drawn = new Map();
  const volumes = {
    top:[[0,1.81,.01,.47,.54,.27],[-.26,1.91,0,.15,.31,.19],[.26,1.91,0,.15,.31,.19]],
    bottom:[[-.12,.78,0,.221,1.11,.25],[.12,.78,0,.221,1.11,.25]],
    skirt:[[0,1.12,.01,.51,.54,.27]],
    outer:[[0,1.86,-.065,.52,.58,.23],[-.19,1.78,.085,.15,.62,.18],[.19,1.78,.085,.15,.62,.18],[-.3,1.72,0,.142,.64,.19],[.3,1.72,0,.142,.64,.19]],
    dress:[[0,1.68,.02,.44,.8,.28],[0,1.11,.02,.55,.61,.3]],
    footwear:[[-.12,.26,.06,.19,.15,.36],[.12,.26,.06,.19,.15,.36]],
    accessory:[[.27,1.4,.15,.21,.28,.12]],
  };
  function render() {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width,height,false);
    renderer.render(scene,camera);
  }
  let closed = false;
  function replace(url, proxy, tint, texture) {
    loader.load(models + url, gltf => {
      if (closed) { dispose(gltf.scene); return; }
      if (tint) gltf.scene.traverse(mesh => {
        if (!mesh.isMesh) return;
        for (const target of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
          target.color?.set(tint);
          if (texture && texture.startsWith('/')) new T.TextureLoader().load(texture, map => {
            if (closed) { map.dispose(); return; }
            map.colorSpace = T.SRGBColorSpace;
            target.map = map;
            target.needsUpdate = true;
            render();
          }, undefined, () => {});
        }
      });
      figure.remove(proxy);
      dispose(proxy);
      figure.add(gltf.scene);
      render();
    }, undefined, () => {});
  }
  const dress = items.some(item => item.slot === 'dress');
  for (const item of items) {
    if (dress && ['top','bottom'].includes(item.slot)) continue;
    const kind = item.slot === 'bottom' && !item.attrs.long_bottom ? 'skirt' : item.slot;
    if (!volumes[kind]) continue;
    const remote = avatar?.slots?.[item.slot];
    const tint = color(remote?.tint || item.attrs.color_hex);
    const template = remote?.template || templates[kind] || (kind === 'bottom' ? 'bottom_pants.glb' : kind === 'skirt' ? 'bottom_skirt.glb' : null);
    const garment = new T.Group();
    limbs(garment, material(tint), volumes[kind]);
    figure.add(garment);
    drawn.set(garment, {template: /^(top_shirt|bottom_pants|bottom_skirt|outer_jacket|dress|footwear_sneaker)\.glb$/.test(template || '') ? template : null,tint,texture:remote?.texture});
  }
  renderer.domElement.setAttribute('aria-hidden','true');
  renderer.domElement.addEventListener('webglcontextlost', () => pending?.(), {once:true});
  stage.append(renderer.domElement);
  const observer = new ResizeObserver(render);
  observer.observe(stage);
  render();
  if (import.meta.env.VITE_AVATAR_MODELS === 'true') {
    const bodyName = avatar?.body?.model === 'male_base.glb' ? 'male_base.glb' : 'female_base.glb';
    replace(bodyName,body);
    for (const [garment, data] of drawn) if (data.template) replace(data.template,garment,data.tint,data.texture);
  }
  pending = () => {
    closed = true;
    observer.disconnect();
    renderer.domElement.remove();
    dispose(scene);
    renderer.dispose();
    pending = undefined;
  };
  return pending;
}
