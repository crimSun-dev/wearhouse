// Only point this destructive smoke test at the dedicated Neon test branch.
import assert from 'node:assert/strict';
const base=process.env.TEST_API_URL;
if(!base?.includes('br-noisy-frog-bivp6wyg-'))throw new Error('Dedicated test branch required');
const key=process.env.TEST_API_KEY||'deployment-test-key';
async function call(method,path,value,status=200,auth=true){
  const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json',...(auth?{'X-API-Key':key}:{})},body:value===undefined?undefined:JSON.stringify(value)});
  const t=await r.text();let data;try{data=JSON.parse(t);}catch{data=t;}
  assert.equal(r.status,status,`${method} ${path}: ${JSON.stringify(data)}`);return data;
}
await call('POST','/api/v1/admin/reset',{});
assert.equal((await call('GET','/api/v1/health')).db,'neon');
assert.equal((await call('GET','/api/v1/wardrobe')).length,28);
await call('POST','/api/v1/outfits/recommend',{occasion:'campus'},401,false);
await call('POST','/api/v1/garments',{name:'bad',slot:'bogus'},422);
const preflight=await fetch(base+'/api/v1/wardrobe',{method:'OPTIONS',headers:{Origin:'https://crimsun-dev.github.io','Access-Control-Request-Headers':'content-type,x-api-key','Access-Control-Request-Method':'GET'}});
assert.equal(preflight.status,204);assert.equal(preflight.headers.get('access-control-allow-origin'),'https://crimsun-dev.github.io');
const rec=await call('POST','/api/v1/outfits/recommend',{occasion:'campus'});
assert.equal(rec.outfits.length,5);assert.equal(rec.weather.source,'LIVE');
const saved=await call('POST','/api/v1/outfits',{items:rec.outfits[0].items.map(g=>g.id),occasion:'campus',label:'smoke',planned_for:'2026-11-24'},201);
assert.ok((await call('GET','/api/v1/outfits?week=2026-W48')).some(o=>o.id===saved.id));
await call('DELETE','/api/v1/garments/'+saved.items[0].id,undefined,409);
await call('POST',`/api/v1/outfits/${saved.id}/wear`,{},204);
assert.equal((await call('GET','/api/v1/avatar/'+saved.id)).outfit_id,saved.id);
await call('DELETE','/api/v1/outfits/'+saved.id,undefined,204);
const g=await call('POST','/api/v1/garments',{name:'smoke garment',slot:'accessory'},201);
await call('DELETE','/api/v1/garments/'+g.id,undefined,204);
const [product]=await call('GET','/api/v1/admin/products');
const [tag]=await call('POST','/api/v1/admin/codes',{gtin:product.gtin},201);
const scan=await call('GET',`/api/v1/scan/01/${tag.gtin}/21/${tag.serial}`);assert.equal(scan.wishlist_only,false);
assert.match(await call('GET',`/api/v1/codes/${tag.serial}/qr.svg`),/<svg/);
assert.equal((await call('POST','/api/v1/garments/activate',{code:tag.activation_code},201)).serial,tag.serial);
await call('POST','/api/v1/garments/activate',{code:tag.activation_code},400);
const [qrTag]=await call('POST','/api/v1/admin/codes',{gtin:product.gtin},201);
assert.equal((await call('POST','/api/v1/garments/scan',{gtin:qrTag.gtin,serial:qrTag.serial},201,false)).serial,qrTag.serial);
await call('POST','/api/v1/garments/activate',{code:qrTag.activation_code},400);
await call('POST','/api/v1/garments/scan',{gtin:tag.gtin,serial:tag.serial},400,false);
const [raceTag]=await call('POST','/api/v1/admin/codes',{gtin:product.gtin},201);
const race=await Promise.all([
  fetch(base+'/api/v1/garments/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gtin:raceTag.gtin,serial:raceTag.serial})}),
  fetch(base+'/api/v1/garments/activate',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':key},body:JSON.stringify({code:raceTag.activation_code})}),
]);
assert.deepEqual(race.map(r=>r.status).sort(),[201,400]);
assert.equal((await call('GET','/api/v1/wardrobe')).filter(g=>g.serial===raceTag.serial).length,1);
await call('POST','/api/v1/admin/fault',{mode:'http500'});
assert.equal((await call('POST','/api/v1/outfits/recommend',{occasion:'campus'})).weather.source,'CACHED');
await call('POST','/api/v1/admin/weather/clear-cache',{});
assert.equal((await call('POST','/api/v1/outfits/recommend',{occasion:'campus'})).weather.source,'MANUAL_REQUIRED');
assert.equal((await call('POST','/api/v1/outfits/recommend',{occasion:'campus',manual_weather:{rain:true,hot:true}})).weather.source,'MANUAL');
assert.ok((await call('GET','/api/v1/metrics/interface-log')).length);
assert.ok((await call('GET','/api/v1/metrics/summary')).rows_per_interface.I1);
await call('POST','/api/v1/admin/reset',{});
console.log('Neon API smoke passed: CORS, authorization, recommendations, outfits, wear, wardrobe, registration, QR, weather fallback, metrics.');
