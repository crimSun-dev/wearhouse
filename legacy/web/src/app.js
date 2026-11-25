import {api, ApiError} from './api.js';
import {slots, slotNames, occasions, styles, cap, color, compose, today, shiftDay, weekDays, weekId, displayDate, scanTag} from './domain.js';
import {figure, garmentArt} from './avatar.js';

const main = document.querySelector('main');
const status = document.querySelector('#status');
const state = {day:today(),time:new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date()),occasion:'campus',slot:'top',swatch:'',items:[],wardrobe:[],saved:[],planned:[],route:'',angle:0,errors:{},scan:null,mode3d:true};
const e = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const action = (id,label,data='',extra='') => `<button type="button" data-action="${id}" data-value="${e(data)}" ${extra}>${label}</button>`;
const option = (value,label=cap(value),selected) => `<option value="${e(value)}"${selected===value?' selected':''}>${e(label)}</option>`;
const choice = (values,selected) => values.map(value => option(value,cap(value),selected)).join('');
const names = items => items.map(item => e(item.name)).join(' · ');
const currentClock = () => new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date())+' WIB';
let toastTimer, cleanupViewer, clockTimer, logTimer, cameraStream, cameraFrame, qrUrl;
let avatarSequence = 0;
let planningSequence = 0;
const dateLabel = day => displayDate(day,{weekday:'long',day:'numeric',month:'long',year:'numeric'});
function say(message) {
  clearTimeout(toastTimer);
  status.textContent = message;
  toastTimer = setTimeout(() => { status.textContent = ''; }, 6200);
}
function heading(title,sub='') {
  return `<header class="page-head"><div><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ''}</div><p class="clock" data-clock>${currentClock()}</p></header>`;
}
function week() {
  return `<div class="week" aria-label="Select a day">${weekDays(state.day).map(day => action('day',`<span>${displayDate(day,{weekday:'short'})}</span><b>${displayDate(day,{day:'numeric'})}</b>`,day,`aria-label="${e(dateLabel(day))}" aria-pressed="${day===state.day}"`)).join('')}</div>`;
}
function matchingWeather() {
  if (state.result) return state.result.weather;
  if (!state.forecast) return null;
  const when = Date.parse(state.day+'T'+state.time+':00+07:00');
  const timeFor = item => Date.parse(item.at && /(?:Z|[+-]\d{2}:\d{2})$/.test(item.at) ? item.at : item.at+'+07:00');
  const closest = [...state.forecast.slots].sort((a,b) => Math.abs(timeFor(a)-when)-Math.abs(timeFor(b)-when))[0];
  if (!closest || Math.abs(timeFor(closest)-when)>10800000) return {...state.forecast,source:'MANUAL_REQUIRED',description:'No forecast near the selected time'};
  return {...state.forecast,...closest};
}
function weatherBar() {
  const weather = matchingWeather();
  if (!weather) return `<div class="weather"><strong>Kemayoran, Jakarta</strong><p>${e(state.errors.forecast || 'Checking the forecast…')}</p><small>Weather data: BMKG</small>${state.errors.forecast?action('retry','Retry connection'):''}</div>`;
  const source = {LIVE:'Live forecast',CACHED:'Cached forecast',MANUAL:'Manual weather',MANUAL_REQUIRED:'Manual weather needed'}[weather.source] || weather.source;
  const fetched = weather.fetched_at && !Number.isNaN(Date.parse(weather.fetched_at)) ? new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit'}).format(new Date(weather.fetched_at)) : '';
  return `<div class="weather"><strong>${e(weather.description || source)}</strong><span>${e(source)}</span>${weather.t == null?'':`<span>${e(weather.t)} °C</span>`}${weather.humidity==null?'':`<span>${e(weather.humidity)}% humidity</span>`}${weather.rain?'<span>Rain</span>':''}${weather.hot?'<span>Hot</span>':''}<small>${e(weather.credit || (weather.source==='MANUAL'?'Weather entered manually':'Weather data: BMKG'))}</small>${weather.source==='CACHED'&&fetched?`<small>Fetched ${fetched} WIB</small>`:''}${weather.note?`<small>${e(weather.note)}</small>`:''}</div>`;
}
function slotButtons() {
  return [1,2,3].map(slot => action('load',String(slot),slot,`aria-label="Load saved outfit ${slot}" aria-pressed="${String(state.loaded||'')===String(slot)}"`)).join('');
}
function stage() {
  return `<section aria-labelledby="fitting-title"><div class="stage-tools"><h2 id="fitting-title">Fitting room</h2><div class="actions"><a href="#/register">Camera</a>${action('view',state.mode3d?'3D avatar':'Illustrated avatar','','aria-pressed="'+state.mode3d+'"')}</div></div><div class="stage" id="avatar-stage">${figure(state.items,state.avatar)}</div><p>${state.items.length ? names(state.items) : 'Choose a garment or try a recommended outfit.'}</p><div class="slots-row"><span>Saved outfits</span>${slotButtons()}${state.loaded?action('remove-slot','Remove saved outfit',state.loaded):''}</div><div class="actions">${action('rotate','Rotate avatar','',state.mode3d?'':'disabled')}${action('clear','Clear selection')}${saveActions(-1)}</div></section>`;
}
function saveActions(index) {
  return [1,2,3].map(slot => action('save-slot','Save to '+slot,index+':'+slot)).join('');
}
function garmentTile(garment) {
  return action('garment',`<span class="cloth-image">${garmentArt(garment)}</span><span>${e(garment.name)}</span>`,garment.id,`class="garment" aria-pressed="${state.items.some(item=>item.id===garment.id)}"`);
}
function picker() {
  const all = state.wardrobe.filter(item => item.slot===state.slot);
  const colors = [...new Set(all.map(item => color(item.attrs.color_hex)))];
  const list = state.swatch ? all.filter(item=>color(item.attrs.color_hex)===state.swatch) : all;
  return `<details class="chooser" ${state.pickerClosed?'':'open'}><summary>Choose garments</summary><div class="filters">${slots.map(slot=>action('slot',slotNames[slot],slot,`aria-pressed="${state.slot===slot}"`)).join('')}</div><p class="hint">Color &amp; variations</p><div class="swatches">${action('color','All colors','',`aria-pressed="${!state.swatch}"`)}${colors.map(tint=>action('color',`<span class="swatch" style="--color:${tint}"></span><span>${tint}</span>`,tint,`aria-pressed="${state.swatch===tint}"`)).join('')}</div><div class="garments">${list.map(garmentTile).join('')}</div>${list.length?'':`<p class="empty">${e(state.errors.wardrobe || 'No garments in this selection.')}</p>`}</details>`;
}
function manualCard() {
  if(state.result?.weather.source!=='MANUAL_REQUIRED') return '';
  return `<section class="manual"><h3>What’s it like outside?</h3><form class="form-stack" data-form="manual"><fieldset><legend>Rain</legend><label><input required type="radio" name="rain" value="rainy"> Rainy</label><label><input type="radio" name="rain" value="dry"> Dry</label></fieldset><fieldset><legend>Temperature</legend><label><input required type="radio" name="hot" value="hot"> Hot</label><label><input type="radio" name="hot" value="normal"> Normal</label></fieldset><button class="primary">Use these conditions</button></form></section>`;
}
function results() {
  const ranked = state.result?.outfits || [];
  const context = state.result?.context;
  return `<section class="results"><h2>Recommended looks</h2>${manualCard()}${state.errors.recommend?`<p class="notice" role="alert">${e(state.errors.recommend)}</p>`:''}${state.result?.message?`<p class="empty">${e(state.result.message)}</p>`:''}${state.result&&!ranked.length&&state.result.weather.source!=='MANUAL_REQUIRED'?'<a href="#/wardrobe">Add a garment</a>':''}${state.result?'':`<p class="empty">${state.checking?'Checking BMKG…':'Select Find outfits to see suggestions.'}</p>`}${ranked.map((look,index)=>{
    const why = [];
    if(context?.rain && look.items.some(item=>['footwear','outer'].includes(item.slot)&&item.attrs.rain_suitable)) why.push('Rain-ready');
    if(context?.hot && !look.items.some(item=>item.attrs.heavy)) why.push('Light layers');
    if(context && ['formal','worship','wedding'].includes(context.occasion)) why.push('Fits the dress code');
    return `<article class="result"><h3>${index===0?'Best match':'Look '+(index+1)}</h3><p>${names(look.items)}</p>${why.length?`<p>${why.join(' · ')}</p>`:''}<details><summary>Score breakdown</summary><p>Compatibility ${e(look.compat)} · Preference ${e(look.pref)} · Recency ${e(look.recency)}</p></details><div class="actions">${action('try','Try on',index)}${action('wear','Wear this',index)}${saveActions(index)}</div></article>`;
  }).join('')}</section>`;
}
function fitting() {
  return `${heading('Plan an outfit',dateLabel(state.day))}${week()}${weatherBar()}<div class="fitting">${stage()}<section><div class="controls"><form data-form="recommend"><label>Occasion<select name="occasion">${choice(occasions,state.occasion)}</select></label><label>Time (WIB)<input name="time" type="time" required value="${e(state.time)}"></label><button class="primary" ${state.checking?'disabled':''}>${state.checking?'Checking BMKG…':'Find outfits'}</button></form></div>${results()}${picker()}</section></div><details class="demo-box" id="integration"><summary>Integration log</summary><div data-log></div><a href="#/demo">Open demo controls</a></details>`;
}
function plan() {
  const list = state.planned.filter(outfit => outfit.planned_for===state.day);
  return `${heading('Week planner',dateLabel(state.day))}<div class="form-line">${action('week','Previous week',-7)}${action('week','Next week',7)}</div>${week()}${weatherBar()}<div class="two-cols"><section><h2>Planned looks</h2>${state.errors.planned?`<p class="notice">${e(state.errors.planned)}</p>`:''}${list.map(outfit=>`<article class="list-row"><h3>${e(outfit.label || 'Planned outfit')}</h3><p>${names(outfit.items)}</p><div class="actions">${action('try-saved','Try on',outfit.id)}${action('delete-outfit','Remove plan',outfit.id)}</div></article>`).join('') || '<p class="empty">Nothing planned for this day.</p>'}</section><section><h2>Plan your current look</h2><p class="empty">${names(state.items) || 'Choose a look in the fitting room first.'}</p><div class="actions"><a class="button" href="#/">Fitting room</a>${action('plan','Plan for this day','','class="primary"')}</div></section></div>`;
}
function wardrobe() {
  const filters = state.wardrobeFilters || {};
  const list = state.wardrobe.filter(item=>(!filters.slot || filters.slot===item.slot)&&(!filters.attribute || item.attrs[filters.attribute]));
  return `${heading('My wardrobe',state.wardrobe.length+' garments')}<div class="two-cols"><section><h2>Your garments</h2><form data-form="wardrobe-filter" class="form-line"><label>Category<select name="slot">${option('','All garments',filters.slot)}${slots.map(slot=>option(slot,slotNames[slot],filters.slot)).join('')}</select></label><label>Attribute<select name="attribute">${option('','All attributes',filters.attribute)}${Object.entries({rain_suitable:'Rain suitable',heavy:'Heavy',long_sleeve:'Long sleeve',long_bottom:'Long bottom'}).map(([key,label])=>option(key,label,filters.attribute)).join('')}</select></label><button>Apply filters</button></form>${state.errors.wardrobe?`<p class="notice">${e(state.errors.wardrobe)}</p>`:''}${list.map(garment=>`<article class="list-row"><h3><span class="swatch" style="--color:${color(garment.attrs.color_hex)}"></span>${e(garment.name)}</h3><p>${e(slotNames[garment.slot])} · Recommended ${e(garment.times_recommended)} · Worn ${e(garment.times_chosen)}${garment.last_worn_at?' · Last worn '+e(garment.last_worn_at):''}</p><div>${action('add-to-look','Select for fitting room',garment.id)} ${action('delete-garment','Remove',garment.id)}</div></article>`).join('') || '<p class="empty">No garments match these filters.</p>'}</section><section><h2>Add a garment</h2><form data-form="add" class="form-stack"><label>Name<input name="name" maxlength="120" required></label><label>Slot<select name="slot">${slots.map(slot=>option(slot,slotNames[slot])).join('')}</select></label><label>Color<input type="color" name="color_hex" value="#b9859a"></label><label>Style<select name="style">${choice(styles)}</select></label><label>Formality<select name="formality">${[1,2,3,4,5].map(level=>option(level,String(level))).join('')}</select></label><fieldset><legend>Garment attributes</legend><label><input type="checkbox" name="rain_suitable"> Rain suitable</label><label><input type="checkbox" name="heavy"> Heavy</label><label><input type="checkbox" name="long_sleeve"> Long sleeves</label><label><input type="checkbox" name="long_bottom"> Long bottom</label></fieldset><p data-form-error role="alert" class="notice" hidden></p><button class="primary">Add to wardrobe</button></form></section></div>`;
}
function register() {
  return `${heading('Register a garment','Scan a garment QR or enter its activation key. Either method adds it to your wardrobe.')}<div class="two-cols"><section><h2>Scan the tag</h2><div class="actions" style="margin-top:1rem">${action('camera','Start camera')}<a class="button" href="#/">Back to avatar</a></div><video hidden playsinline muted aria-label="QR scanner camera preview"></video><form data-form="scan" class="form-stack"><label>Or paste the tag link<input name="link" placeholder="/01/…/21/…" required></label><p data-form-error role="alert" class="notice" hidden></p><button>Add garment from QR</button></form>${state.scan?`<article class="list-row"><h3>${e(state.scan.name)}</h3><p>${e(state.scan.category || state.scan.slot)} · ${e(state.scan.style)}</p><p>Scanning registers this garment in your wardrobe.</p></article>`:''}</section><section><h2>Activate your garment</h2><form data-form="activate" class="form-stack"><label>Private activation code<input name="code" autocomplete="off" autocapitalize="characters" placeholder="XXXX-XXXX-XXXX-XXXX" minlength="19" maxlength="19" required></label><p data-form-error role="alert" class="notice" hidden></p><button class="primary">Activate garment</button></form>${state.activated?`<p class="notice">${e(state.activated.name)} was added. <a href="#/wardrobe">See my wardrobe</a></p>`:''}</section></div>`;
}
function demo() {
  const run = state.health;
  return `${heading('Integration demo','Inspect the server and step through the weather and registration flows.')}<p class="weather">${run?`<strong>${e(run.status)}</strong><span>Database ${e(run.db)}</span><span>Weather mode ${e(run.weather_mode)}</span><span>Fault ${e(run.fault)}</span>`:`<span>${e(state.errors.health || 'Checking the server…')}</span>`}</p><div class="two-cols"><section><h2>Weather controls</h2><p>Simulated faults expire after 10 minutes. Select None to restore live weather now.</p><form data-form="fault" class="form-stack"><label>Simulate a BMKG fault<select name="fault">${choice(['none','timeout','http500','malformed','missing_fields'],run?.fault)}</select></label><button>Apply fault</button></form><div class="actions">${action('cache','Clear weather cache')}${action('reset','Reset demo data')}</div></section><section><h2>Issue a tag code</h2><form data-form="issue" class="form-stack"><label>Product<select name="gtin" required><option value="">Select a product</option>${(state.products||[]).map(product=>option(product.gtin,product.name)).join('')}</select></label><button class="primary">Issue code</button></form>${state.errors.products?`<p class="notice">${e(state.errors.products)}</p>`:''}${state.issued?`<p class="notice">One-time code <strong>${e(state.issued.activation_code)}</strong></p><p>Serial ${e(state.issued.serial)}</p>${qrUrl?`<img class="qr" src="${e(qrUrl)}" alt="QR code for the issued garment tag">`:''}`:''}</section></div><section class="demo-box"><h2>Interface log</h2><label>Interface<select data-log-filter>${option('','All interfaces',state.logFilter)}${['I1','I2','I3','I4','I5','I6'].map(value=>option(value,value,state.logFilter)).join('')}</select></label><div data-log></div></section>`;
}

function stopCamera() {
  cancelAnimationFrame(cameraFrame);
  cameraStream?.getTracks().forEach(track=>track.stop());
  cameraStream = undefined;
}
function renderAvatar() {
  cleanupViewer?.();
  cleanupViewer = undefined;
  const stage = document.querySelector('#avatar-stage');
  if (!stage || !state.mode3d) return;
  const version = ++avatarSequence;
  import('./viewer.js').then(({mountViewer})=>{
    if (version!==avatarSequence || !stage.isConnected || !state.mode3d) return;
    cleanupViewer = mountViewer(stage,state.items,state.avatar,state.angle);
  }).catch(()=>{});
}
function render() {
  const active = document.activeElement;
  const control = active?.dataset.action;
  const value = active?.dataset.value;
  const screens = {'/':fitting,'/plan':plan,'/wardrobe':wardrobe,'/register':register,'/demo':demo};
  const logOpen = Boolean(document.querySelector('#integration')?.open);
  main.innerHTML = (screens[state.route] || fitting)();
  for (const link of document.querySelectorAll('.mast nav a')) {
    if (link.hash.slice(1)===state.route) link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  }
  if (logOpen && document.querySelector('#integration')) document.querySelector('#integration').open = true;
  if (control && document.body.contains(active)===false) {
    const replacement = [...main.querySelectorAll('[data-action]')].find(button=>button.dataset.action===control&&button.dataset.value===value);
    if (replacement) replacement.focus({preventScroll:true});
  }
  renderAvatar();
  if (state.route==='/demo' || logOpen) updateLogs();
}
function weatherRefresh() {
  return api.weather().then(forecast=>{state.forecast=forecast;delete state.errors.forecast;},error=>{state.errors.forecast=error.message;});
}
function wardrobeRefresh() {
  return api.wardrobe().then(wardrobe=>{state.wardrobe=wardrobe;delete state.errors.wardrobe;},error=>{state.errors.wardrobe=error.message;});
}
const savedRefresh = () => api.outfits().then(saved=>{state.saved=saved;});
async function plannedRefresh() {
  const sequence = ++planningSequence;
  try {
    const outfits = await api.outfits(weekId(state.day));
    if (sequence===planningSequence) {state.planned=outfits;delete state.errors.planned;}
  } catch(error) {
    if (sequence===planningSequence) state.errors.planned=error.message;
  }
}
const newestSlot = slot => state.saved.filter(outfit=>outfit.label===String(slot)).at(0);
async function demoRefresh() {
  await Promise.allSettled([
    api.health().then(health=>{state.health=health;delete state.errors.health;},error=>{state.errors.health=error.message;}),
    api.products().then(products=>{state.products=products;delete state.errors.products;},error=>{state.errors.products=error.message;})
  ]);
}
let logUpdating = false;
async function updateLogs() {
  const container = main.querySelector('[data-log]');
  if (!container || (state.route!=='/demo' && !document.querySelector('#integration')?.open) || document.hidden || logUpdating) return;
  logUpdating = true;
  try {
    const [rows,summary] = await Promise.all([api.log(state.logFilter),api.summary()]);
    if (!container.isConnected) return;
    container.innerHTML = `<p class="hint">BMKG calls in the last 24 hours: ${e(summary.bmkg_calls_last_24h)}</p>${rows.length?`<div class="table-wrap"><table><thead><tr><th scope="col">Time</th><th scope="col">Interface</th><th scope="col">Route</th><th scope="col">Status</th><th scope="col">Latency</th><th scope="col">Weather source</th><th scope="col">Note</th></tr></thead><tbody>${rows.map(row=>`<tr data-fault="${row.interface==='I2'&&(Number(row.status)>=400||/error|timeout|invalid/i.test(String(row.status)))}"><td>${e(row.at)}</td><td>${e(row.interface)}</td><td>${e(row.route)}</td><td>${e(row.status)}</td><td>${e(row.latency_ms)} ms</td><td>${e(row.weather_source)}</td><td>${e(row.note)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="empty">No interface events yet.</p>'}`;
  } catch(error) {
    if(container.isConnected) container.textContent = error.message;
  } finally { logUpdating=false; }
}
async function navigate() {
  stopCamera();
  const raw = location.hash.slice(1) || '/';
  state.route = ['/', '/plan','/wardrobe','/register','/demo'].includes(raw) ? raw : '/';
  const route = state.route;
  render();
  const jobs = route==='/demo' ? [demoRefresh()] : route==='/plan' ? [plannedRefresh(),weatherRefresh()] : route==='/wardrobe' ? [wardrobeRefresh()] : route==='/' ? [wardrobeRefresh(),weatherRefresh(),savedRefresh()] : [];
  await Promise.allSettled(jobs);
  if(state.route===route) render();
}
async function recommend(manual_weather) {
  if(state.checking) return;
  const when = state.day+'T'+state.time+':00';
  const occasion = state.occasion;
  state.checking = true;
  delete state.errors.recommend;
  state.result = undefined;
  render();
  try {
    const result = await api.recommend({occasion,when,...(manual_weather?{manual_weather}:{})});
    if (when===state.day+'T'+state.time+':00' && occasion===state.occasion) state.result=result;
  } catch(error) {state.errors.recommend=error.message;}
  finally {state.checking=false;render();}
}
async function selectSaved(outfit) {
  if (!outfit) throw new Error('This saved slot is empty.');
  state.items = outfit.items;
  state.loaded = /^[123]$/.test(outfit.label || '') ? outfit.label : null;
  state.avatar = undefined;
  render();
  const reference = state.items;
  try {
    const avatar = await api.avatar(outfit.id);
    if (state.items===reference) {state.avatar=avatar;render();}
  } catch {}
}
function payload(items,label) {
  if (!items.length) throw new Error('Choose at least one garment first.');
  return {items:items.map(item=>item.id),planned_for:state.day,occasion:state.occasion,...(label?{label}:{})};
}
function getLook(index) {
  return index===-1 ? state.items : state.result?.outfits[index]?.items || [];
}
async function saveSlot(index,slot) {
  await savedRefresh();
  const old = state.saved.filter(outfit=>outfit.label===slot);
  if (old.length && !confirm('Replace outfit '+slot+'?')) return;
  const saved = await api.save(payload(getLook(index),slot));
  const deletions = await Promise.allSettled(old.map(outfit=>api.deleteOutfit(outfit.id)));
  await savedRefresh();
  await selectSaved(saved);
  say(deletions.some(item=>item.status==='rejected')?'New outfit saved. One or more older copies could not be removed.':'Saved to outfit '+slot+'.');
}
async function wearLook(index) {
  const saved = await api.save(payload(getLook(index)));
  try { await api.wear(saved.id,state.day); }
  catch(error) {
    await savedRefresh().catch(()=>{});
    throw new Error('The outfit was saved. The server could not record wear: '+error.message);
  }
  await Promise.allSettled([wardrobeRefresh(),savedRefresh()]);
  await selectSaved(saved);
  say('Outfit saved and wear recorded.');
}
function pickGarment(value) {
  const garment = state.wardrobe.find(item=>item.id===value);
  if (!garment) return;
  state.items=compose(state.items,garment);
  state.loaded=null;
  state.avatar=null;
  state.pickerClosed=matchMedia('(max-width:759px)').matches;
}
async function removeGarment(value) {
  if (!confirm('Remove this garment from your wardrobe?')) return;
  try {await api.deleteGarment(value);}
  catch(error) {
    if (!(error instanceof ApiError) || error.status!==409) throw error;
    await savedRefresh();
    const used = state.saved.filter(outfit=>outfit.items.some(garment=>garment.id===value)).map(outfit=>outfit.label||outfit.planned_for||outfit.id);
    throw new Error(error.message+(used.length?' Saved outfits using it: '+used.join(', ')+'.':''));
  }
  state.items=state.items.filter(item=>item.id!==value);
  await wardrobeRefresh();
  say('Garment removed.');
}
async function readTag(link) {
  const [gtin,serial]=scanTag(link);
  state.activated=await api.registerScan(gtin,serial);
  state.scan=null;
  await wardrobeRefresh();
  say(state.activated.name+' added to your wardrobe.');
  stopCamera();
}
async function startCamera() {
  if(!isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('The camera needs HTTPS or localhost. You can paste a tag link instead.');
  if(!('BarcodeDetector' in globalThis)) throw new Error('This browser has no QR detector. Paste the tag link instead.');
  stopCamera();
  const detector = new BarcodeDetector({formats:['qr_code']});
  try {cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});}
  catch {throw new Error('Camera access is unavailable. You can paste a tag link instead.');}
  if(state.route!=='/register'){stopCamera();return;}
  const video = main.querySelector('video');
  video.srcObject = cameraStream;
  video.hidden = false;
  await video.play();
  let lastCheck = 0;
  async function scanFrame(time) {
    if (!video.isConnected || !cameraStream) {stopCamera();return;}
    if (video.readyState>=2 && time-lastCheck>250) {
      lastCheck=time;
      try {
        const tags=await detector.detect(video);
        if(tags[0]?.rawValue){await readTag(tags[0].rawValue);render();return;}
      } catch(error) {say(error.message || 'Could not read the QR code.');stopCamera();video.hidden=true;return;}
    }
    cameraFrame=requestAnimationFrame(scanFrame);
  }
  cameraFrame=requestAnimationFrame(scanFrame);
}
const handlers = {
  retry:async()=>{await Promise.allSettled([weatherRefresh(),wardrobeRefresh(),savedRefresh()]);},
  day:async value=>{state.day=value;state.result=undefined;if(state.route==='/plan')await plannedRefresh();},
  week:async value=>{state.day=shiftDay(state.day,Number(value));state.result=undefined;await plannedRefresh();},
  slot:value=>{state.slot=value;state.swatch='';state.pickerClosed=false;},
  color:value=>{state.swatch=value;state.pickerClosed=false;},
  garment:pickGarment,
  'add-to-look':value=>{pickGarment(value);location.hash='/';},
  'delete-garment':removeGarment,
  clear:()=>{state.items=[];state.loaded=null;state.avatar=null;},
  view:()=>{state.mode3d=!state.mode3d;},
  rotate:()=>{state.angle+=Math.PI/4;},
  try:value=>{state.items=getLook(Number(value));state.loaded=null;state.avatar=null;if(matchMedia('(max-width:759px)').matches) requestAnimationFrame(()=>document.querySelector('#fitting-title')?.scrollIntoView({block:'start'}));},
  'try-saved':async value=>{const outfit=state.planned.find(item=>item.id===value);await selectSaved(outfit);location.hash='/';},
  load:async slot=>{await savedRefresh();await selectSaved(newestSlot(slot));},
  'save-slot':value=>{const [index,slot]=value.split(':');return saveSlot(Number(index),slot);},
  'remove-slot':async value=>{if(confirm('Remove saved outfit '+value+'?')){await savedRefresh();await Promise.all(state.saved.filter(outfit=>outfit.label===value).map(outfit=>api.deleteOutfit(outfit.id)));await savedRefresh();state.loaded=null;say('Saved outfit removed.');}},
  wear:value=>wearLook(Number(value)),
  plan:async()=>{await api.save(payload(state.items));await Promise.allSettled([plannedRefresh(),savedRefresh()]);say('Look added to your week.');},
  'delete-outfit':async value=>{if(confirm('Remove this planned outfit?')){await api.deleteOutfit(value);await plannedRefresh();say('Plan removed.');}},
  camera:startCamera,
  cache:async()=>{await api.clearWeather();state.forecast=undefined;state.result=undefined;await demoRefresh();say('Weather cache cleared.');},
  reset:async()=>{if(!confirm('Reset the demo? Saved outfits, wear history and registrations will be erased.'))return;await api.reset();if(qrUrl)URL.revokeObjectURL(qrUrl);qrUrl=undefined;Object.assign(state,{items:[],saved:[],planned:[],scan:null,activated:null,issued:null,result:null,forecast:null,avatar:null,loaded:null});await demoRefresh();say('Demo data reset.');}
};
const forms = {
  recommend:values=>{state.time=values.time;state.occasion=values.occasion;return recommend();},
  manual:values=>recommend({rain:values.rain==='rainy',hot:values.hot==='hot'}),
  'wardrobe-filter':values=>{state.wardrobeFilters=values;},
  add:async values=>{
    const attrs={color_hex:values.color_hex,style:values.style,formality:Number(values.formality)};
    for(const attr of ['rain_suitable','heavy','long_sleeve','long_bottom']) attrs[attr]=values[attr]==='on';
    const garment=await api.add({name:values.name.trim(),slot:values.slot,attrs});await wardrobeRefresh();say(garment.name+' added.');
  },
  scan:values=>readTag(values.link),
  activate:async values=>{state.activated=await api.activate(values.code);await wardrobeRefresh();say(state.activated.name+' added to your wardrobe.');},
  fault:async values=>{await api.fault(values.fault);state.result=undefined;await demoRefresh();say('Weather fault updated.');},
  issue:async values=>{
    const [issued]=await api.issue(values.gtin);
    if(qrUrl)URL.revokeObjectURL(qrUrl);
    qrUrl=undefined;
    state.issued=issued;
    if(issued) {try {qrUrl=URL.createObjectURL(await api.qr(issued.serial));}catch(error){say(error.message);}}
  }
};
main.addEventListener('click',async event=>{
  const button=event.target.closest('button[data-action]');
  if(!button || button.disabled) return;
  const handler=handlers[button.dataset.action];
  if(!handler) return;
  button.disabled=true;
  try {await handler(button.dataset.value);if(button.dataset.action!=='camera') render();}
  catch(error){say(error.message);}
  finally{if(button.isConnected)button.disabled=false;}
});
main.addEventListener('submit',async event=>{
  const form=event.target;
  const handler=forms[form.dataset.form];
  if(!handler) return;
  event.preventDefault();
  const values=Object.fromEntries(new FormData(form));
  const submit=form.querySelector('button[type=submit],button:not([type])') || form.querySelector('button');
  const feedback=form.querySelector('[data-form-error]');
  if(feedback) feedback.hidden=true;
  for(const input of form.querySelectorAll('[aria-invalid=true]')) input.removeAttribute('aria-invalid');
  if(submit) submit.disabled=true;
  try {await handler(values);render();}
  catch(error){
    if(feedback) {feedback.hidden=false;feedback.textContent=error.status===429?'Too many attempts. Try again after the cooldown.':error.message;}
    else say(error.message);
    if(Array.isArray(error.detail)) for(const item of error.detail) {
      const input=form.elements.namedItem(item.loc.at(-1));
      if(input instanceof HTMLElement){input.setAttribute('aria-invalid','true');}
    }
  } finally {if(submit?.isConnected) submit.disabled=false;}
});
main.addEventListener('input',event=>{
  if(event.target.name==='code'){event.target.value=event.target.value.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,16).match(/.{1,4}/g)?.join('-')||'';}
});
main.addEventListener('change',event=>{
  if(event.target.matches('[data-log-filter]')) {state.logFilter=event.target.value;updateLogs();}
  if(event.target.name==='time'){state.time=event.target.value;state.result=undefined;}
  if(event.target.name==='occasion'){state.occasion=event.target.value;state.result=undefined;}
});
main.addEventListener('toggle',event=>{if(event.target.id==='integration'&&event.target.open)updateLogs();},true);
addEventListener('hashchange',()=>{navigate();window.scrollTo(0,0);main.focus({preventScroll:true});});
addEventListener('pagehide',()=>{stopCamera();cleanupViewer?.();clearInterval(clockTimer);clearInterval(logTimer);if(qrUrl)URL.revokeObjectURL(qrUrl);});
clockTimer=setInterval(()=>{const clock=document.querySelector('[data-clock]');if(clock)clock.textContent=currentClock();},15000);
logTimer=setInterval(updateLogs,3000);
navigate();
