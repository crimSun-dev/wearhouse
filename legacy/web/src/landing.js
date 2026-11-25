import {api} from './api.js';
const scenes = [
  { key: 'clear', temp: '28°', name: 'Cerah Berawan', time: 'Day 1 · 08:00 WIB', text: 'A breathable layer and everyday sandals for a clear start.', shirt: 'Pink Oxford shirt', layer: 'Everyday sandals' },
  { key: 'rain', temp: '27°', name: 'Hujan Ringan', time: 'Day 1 · 14:00 WIB', text: 'Light rain calls for a clear raincoat and rubber rain sandals.', shirt: 'Clear lightweight raincoat', layer: 'Rubber rain sandals' },
  { key: 'heat', temp: '33°', name: 'Cerah', time: 'Day 2 · 12:00 WIB', text: 'A light shirt is enough for the hottest part of the day.', shirt: 'Light cotton shirt', layer: 'Everyday sandals' },
];
const byId = id => document.getElementById(id);
const slider = byId('slots');
const chapter = byId('forecast');
chapter.classList.add('has-timeline');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
let current = -1;
let locked = false;
function select(index) {
  if (index === current) return;
  current = index;
  const scene = scenes[index];
  slider.value = String(index);
  slider.setAttribute('aria-valuetext', scene.time + ', ' + scene.name + ', ' + scene.temp);
  document.querySelector('.forecast-visual').dataset.scene = scene.key;
  for (const [id, key] of Object.entries({'scene-temp':'temp','scene-name':'name','scene-time':'time','scene-description':'text','scene-shirt':'shirt','scene-layer':'layer'})) byId(id).textContent = scene[key];
}
select(0);
slider.addEventListener('input', () => { locked = true; select(Number(slider.value)); });
slider.addEventListener('blur', () => { locked = false; });
let queued = false;
addEventListener('scroll', () => {
  if (queued || motion.matches || locked || innerWidth < 760) return;
  queued = true;
  requestAnimationFrame(() => {
    queued = false;
    const bounds = chapter.getBoundingClientRect();
    const travel = Math.max(1, bounds.height - innerHeight);
    select(Math.min(2, Math.max(0, Math.floor((-bounds.top / travel) * 3))));
  });
}, {passive:true});
api.weather().then(forecast => {
  const now = Date.now();
  const slot = forecast.slots.filter(item => Number.isFinite(Date.parse(item.at))).sort((a,b) => Math.abs(Date.parse(a.at)-now)-Math.abs(Date.parse(b.at)-now))[0];
  if (!slot || !forecast.credit || Math.abs(Date.parse(slot.at)-now) > 3 * 3600000) return;
  byId('hero-weather').textContent = [forecast.source, slot.t + ' °C', slot.description].join(' · ');
  byId('hero-credit').textContent = forecast.credit;
}).catch(() => {});
