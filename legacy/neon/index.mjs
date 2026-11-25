import { Hono } from 'hono';
import pg from 'pg';
import { attachDatabasePool } from '@neon/functions';
import { randomUUID, randomBytes, createHash, timingSafeEqual } from 'node:crypto';
import QRCode from 'qrcode';
import { z } from 'zod';
import seed from './seed.json' with {type:'json'};
import fixture from '../python/fixtures/bmkg_real_sample.json' with {type:'json'};
import openapi from '../contracts/openapi-v1.json' with {type:'json'};
import {slots,occasions,defaults,garment,recommend} from './rules.mjs';

pg.types.setTypeParser(1082,v=>v);
const pool=new pg.Pool({connectionString:process.env.DATABASE_URL,max:5,connectionTimeoutMillis:15000});
attachDatabasePool(pool);
const query=async(sql,args=[],db=pool)=>(await db.query(sql,args)).rows;
const user=seed.user_id, origin='https://crimsun-dev.github.io';
const credit='Weather data: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id';
const bmkg='https://api.bmkg.go.id/publik/prakiraan-cuaca';
const app=new Hono();
class ApiError extends Error {constructor(status,message){super(message);this.status=status;}}
const fail=(status,message)=>{throw new ApiError(status,message);};
const uuid=z.uuid();
const attrSchema=z.object({color_hex:z.string().regex(/^#[0-9a-fA-F]{6}$/).default('#808080'),style:z.enum(['casual','smart','formal','modest','sporty','street']).default('casual'),rain_suitable:z.boolean().default(false),heavy:z.boolean().default(false),long_sleeve:z.boolean().default(false),long_bottom:z.boolean().default(false),formality:z.number().int().min(1).max(5).default(1)}).strict();
const adm4Schema=z.string().regex(/^\d{2}\.\d{2}\.\d{2}\.\d{4}$/);
const dateSchema=z.iso.date();
const faults=['none','timeout','http500','malformed','missing_fields'];
const body=async(c,schema)=>{let value;try{value=await c.req.json();}catch{fail(422,'invalid JSON body');}const r=schema.safeParse(value);if(!r.success)fail(422,r.error.issues);return r.data;};
const id=c=>{const r=uuid.safeParse(c.req.param('id'));if(!r.success)fail(422,'invalid UUID');return r.data;};
async function transaction(fn){const db=await pool.connect();try{await db.query('BEGIN');const result=await fn(db);await db.query('COMMIT');return result;}catch(e){await db.query('ROLLBACK');throw e;}finally{db.release();}}
let initialized;
async function init(){if(!initialized)initialized=query('CREATE TABLE IF NOT EXISTS neon_demo_state (key text PRIMARY KEY, value jsonb NOT NULL)').catch(e=>{initialized=null;throw e;});await initialized;}
async function state(key){return (await query('SELECT value FROM neon_demo_state WHERE key=$1',[key]))[0]?.value;}
async function activeFault(){const value=await state('fault');return typeof value==='string'?value:value?.expires>Date.now()?value.mode:'none';}
async function put(key,value){await query('INSERT INTO neon_demo_state(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=excluded.value',[key,JSON.stringify(value)]);}
async function log(iface,route,status,ms,source=null,note=null){try{await query('INSERT INTO interface_log(at,interface,route,status,latency_ms,weather_source,note) VALUES(now(),$1,$2,$3,$4,$5,$6)',[iface,route,status,ms,source,note]);}catch{ /* logging does not take down API */ }}
app.use('*',async(c,next)=>{
  const requested=c.req.header('Origin');
  if(requested===origin||/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(requested||''))c.header('Access-Control-Allow-Origin',requested);
  c.header('Vary','Origin');c.header('Access-Control-Allow-Methods','GET,POST,DELETE,OPTIONS');c.header('Access-Control-Allow-Headers','Content-Type,X-API-Key,X-Interface');
  if(c.req.method==='OPTIONS')return c.body(null,204);
  await init(); const start=performance.now(); await next();
  if((c.req.path.startsWith('/api/')||c.req.path.startsWith('/01/'))&&c.req.path!=='/api/v1/metrics/interface-log'){
    const iface=c.req.header('X-Interface')==='I6'?'I6':c.req.path.includes('/scan/')||c.req.path.endsWith('/garments/scan')||c.req.path.startsWith('/01/')?'I5':'I1';
    await log(iface,c.req.method+' '+c.req.path,c.res.status,performance.now()-start,c.get('weather_source')??null);
  }
});
app.use('/api/v1/*',async(c,next)=>{
  if(c.req.path==='/api/v1/garments/scan' && c.req.method==='POST'){await next();return;}
  if(c.req.method!=='GET'||c.req.path.includes('/admin/')||c.req.path.endsWith('/qr.svg')){
    const expected=process.env.DEMO_API_KEY;
    const a=Buffer.from(c.req.header('X-API-Key')||''),b=Buffer.from(expected||'');
    if(!expected||a.length!==b.length||!timingSafeEqual(a,b))return c.json({detail:'missing or wrong X-API-Key'},401);
  }
  await next();
});
app.onError((e,c)=>{
  if(e instanceof ApiError)return c.json({detail:e.message},e.status);
  if(e.code==='23503')return c.json({detail:'item is referenced by a saved record'},409);
  if(e.code==='23505')return c.json({detail:'record already exists'},409);
  if(e.code==='22P02')return c.json({detail:'invalid input'},422);
  console.error('API error',e.code||e.name);return c.json({detail:'server error'},500);
});

const wardrobe=async(db=pool)=>(await query('SELECT * FROM garment WHERE owner_id=$1',[user],db)).map(garment).sort((a,b)=>slots.indexOf(a.slot)-slots.indexOf(b.slot)||a.name.localeCompare(b.name));
async function outfit(id,db=pool){const row=(await query('SELECT * FROM outfit WHERE id=$1 AND owner_id=$2',[id,user],db))[0];if(!row)fail(404,'outfit not found');const items=(await query('SELECT g.* FROM garment g JOIN outfit_item i ON i.garment_id=g.id WHERE i.outfit_id=$1',[id],db)).map(garment).sort((a,b)=>slots.indexOf(a.slot)-slots.indexOf(b.slot));return {id:row.id,label:row.label,planned_for:row.planned_for,occasion:row.occasion,items};}
app.get('/',c=>c.json({service:'Digital Wardrobe Neon API',frontend:origin+'/LIVE-DEMO/'}));
app.get('/api/v1/health',async c=>{await query('SELECT 1');return c.json({status:'ok',db:'neon',runtime:'neon-functions',weather_mode:process.env.WEATHER_MODE||'live',fault:await activeFault(),weather_cache:{persistent:true}});});
app.get('/openapi.json',c=>c.json({...openapi,servers:[{url:new URL(c.req.url).origin}]}));
app.get('/docs',c=>c.html('<!doctype html><title>Digital Wardrobe API</title><div id="swagger-ui"></div><link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script><script>SwaggerUIBundle({url:"/openapi.json",dom_id:"#swagger-ui"})</script>'));
app.get('/api/v1/wardrobe',async c=>c.json(await wardrobe()));
app.post('/api/v1/garments',async c=>{const b=await body(c,z.object({name:z.string().trim().min(1).max(120),slot:z.enum(slots),attrs:attrSchema.default(defaults)}));const rows=await query('INSERT INTO garment(id,owner_id,name,slot,attrs,times_recommended,times_chosen,created_at) VALUES($1,$2,$3,$4,$5,0,0,now()) RETURNING *',[randomUUID(),user,b.name,b.slot,JSON.stringify(b.attrs)]);return c.json(garment(rows[0]),201);});
app.delete('/api/v1/garments/:id',async c=>{const gid=id(c);const rows=await query('DELETE FROM garment WHERE id=$1 AND owner_id=$2 RETURNING id',[gid,user]);if(!rows.length)fail(404,'garment not found');return c.body(null,204);});
app.get('/api/v1/outfits',async c=>{
  let rows;const week=c.req.query('week');
  if(week){const m=/^(\d{4})-W(\d{2})$/.exec(week);if(!m||+m[2]<1||+m[2]>53)fail(422,'week must look like 2026-W48');const date=new Date(Date.UTC(+m[1],0,4));date.setUTCDate(date.getUTCDate()-((date.getUTCDay()+6)%7)+(+m[2]-1)*7);const start=date.toISOString().slice(0,10);date.setUTCDate(date.getUTCDate()+6);rows=await query('SELECT id FROM outfit WHERE owner_id=$1 AND planned_for BETWEEN $2 AND $3 ORDER BY planned_for,label',[user,start,date.toISOString().slice(0,10)]);}
  else rows=await query('SELECT id FROM outfit WHERE owner_id=$1 ORDER BY planned_for,label',[user]);
  return c.json(await Promise.all(rows.map(r=>outfit(r.id))));
});
app.post('/api/v1/outfits',async c=>{const b=await body(c,z.object({items:z.array(uuid).min(1).max(6),label:z.string().max(60).nullable().optional(),planned_for:dateSchema.nullable().optional(),occasion:z.enum(occasions).nullable().optional()}));
  const result=await transaction(async db=>{const ids=[...new Set(b.items)];const gs=await query('SELECT * FROM garment WHERE owner_id=$1 AND id=ANY($2::uuid[]) FOR SHARE',[user,ids],db);if(gs.length!==ids.length)fail(422,'unknown garment id(s) for this wardrobe');const ss=gs.map(g=>g.slot);if(new Set(ss).size!==ss.length||ss.includes('dress')&&(ss.includes('top')||ss.includes('bottom')))fail(409,'slot clash');const oid=randomUUID();await query('INSERT INTO outfit(id,owner_id,label,planned_for,occasion) VALUES($1,$2,$3,$4,$5)',[oid,user,b.label??null,b.planned_for??null,b.occasion??null],db);for(const g of gs)await query('INSERT INTO outfit_item(outfit_id,slot,garment_id) VALUES($1,$2,$3)',[oid,g.slot,g.id],db);return outfit(oid,db);});return c.json(result,201);
});
app.delete('/api/v1/outfits/:id',async c=>{const rows=await query('DELETE FROM outfit WHERE id=$1 AND owner_id=$2 RETURNING id',[id(c),user]);if(!rows.length)fail(404,'outfit not found');return c.body(null,204);});
const today=()=>new Date(Date.now()+7*3600000).toISOString().slice(0,10);
app.post('/api/v1/outfits/:id/wear',async c=>{const b=await body(c,z.object({worn_on:dateSchema.nullable().optional()}));await transaction(async db=>{const o=await outfit(id(c),db);await query('INSERT INTO wear_log(outfit_id,worn_on) VALUES($1,$2)',[o.id,b.worn_on||today()],db);await query('UPDATE garment SET last_worn_at=$1,times_chosen=times_chosen+1 WHERE id=ANY($2::uuid[])',[b.worn_on||today(),o.items.map(g=>g.id)],db);});return c.body(null,204);});
app.get('/api/v1/avatar/:id',async c=>{const o=await outfit(id(c));const products=await query('SELECT * FROM product');const parts={};for(const g of o.items){const p=products.find(p=>p.gtin===g.gtin);const templates={top:'top_shirt.glb',dress:'dress.glb',outer:'outer_jacket.glb',footwear:'footwear_sneaker.glb',bottom:g.attrs.long_bottom?'bottom_pants.glb':'bottom_skirt.glb'};parts[g.slot]={garment_id:g.id,name:g.name,template:p?.glb_template||templates[g.slot]||null,texture:p?.image_url||null,tint:g.attrs.color_hex};}return c.json({outfit_id:o.id,body:{model:'female_base.glb',gender:'female'},slots:parts,covers:parts.dress?{dress:['top','bottom']}:{}});});

const hash=code=>createHash('sha256').update(code.toUpperCase().replace(/[^A-Z0-9]/g,'')).digest('hex');
const productAttrs=p=>Object.fromEntries(Object.keys(defaults).map(k=>[k,p[k]]));
app.get('/api/v1/admin/products',async c=>c.json(await query('SELECT gtin,name,slot FROM product ORDER BY gtin')));
app.post('/api/v1/admin/codes',async c=>{const b=await body(c,z.object({gtin:z.string().regex(/^\d{14}$/),count:z.number().int().min(1).max(20).default(1)}));if(!(await query('SELECT gtin FROM product WHERE gtin=$1',[b.gtin])).length)fail(404,'unknown gtin');const issued=await transaction(async db=>{const out=[];for(let i=0;i<b.count;i++){const serial=randomBytes(16).toString('hex');const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';const bytes=randomBytes(10);let bits=0,v=0,code='';for(const n of bytes){v=(v<<8)|n;bits+=8;while(bits>=5){bits-=5;code+=alphabet[(v>>>bits)&31];}}await query('INSERT INTO garment_code(serial,gtin,activation_hash) VALUES($1,$2,$3)',[serial,b.gtin,hash(code)],db);out.push({gtin:b.gtin,serial,activation_code:code.match(/.{4}/g).join('-')});}return out;});return c.json(issued,201);});
async function redeem(c,qr=false){const b=await body(c,qr?z.object({gtin:z.string().regex(/^\d{14}$/),serial:z.string().regex(/^[0-9a-f]{32}$/)}):z.object({code:z.string().min(1).max(64)}));const result=await transaction(async db=>{
  await query('SELECT pg_advisory_xact_lock(hashtext($1))',[user],db);
  const attempts=await query("SELECT count(*)::int AS n FROM activation_attempt WHERE user_id=$1 AND at>=now()-interval '1 hour'",[user],db);if(attempts[0].n>=10)return {error:429};
  const rows=await query(qr?'UPDATE garment_code SET owner_id=$1,used_at=now() WHERE serial=$2 AND gtin=$3 AND used_at IS NULL RETURNING *':'UPDATE garment_code SET owner_id=$1,used_at=now() WHERE activation_hash=$2 AND used_at IS NULL RETURNING *',qr?[user,b.serial,b.gtin]:[user,hash(b.code)],db);await query('INSERT INTO activation_attempt(user_id,at,ok) VALUES($1,now(),$2)',[user,!!rows.length],db);if(!rows.length)return {error:400};
  const tag=rows[0],p=(await query('SELECT * FROM product WHERE gtin=$1',[tag.gtin],db))[0];const gs=await query('INSERT INTO garment(id,owner_id,gtin,serial,name,slot,attrs,times_recommended,times_chosen,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,0,0,now()) RETURNING *',[randomUUID(),user,p.gtin,tag.serial,p.name,p.slot,JSON.stringify(productAttrs(p))],db);return {g:garment(gs[0])};
});if(result.error)fail(result.error,result.error===429?'too many attempts, try again later':'invalid code');return c.json(result.g,201);}
app.post('/api/v1/garments/activate',c=>redeem(c));
app.post('/api/v1/garments/scan',c=>redeem(c,true));
const escape=s=>String(s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
async function scan(c){const rows=await query('SELECT p.*,g.serial FROM product p JOIN garment_code g ON p.gtin=g.gtin WHERE g.serial=$1 AND p.gtin=$2',[c.req.param('serial'),c.req.param('gtin')]);if(!rows.length)fail(404,'unknown product tag');const p=rows[0];return {gtin:p.gtin,serial:p.serial,name:p.name,category:p.category,slot:p.slot,color_hex:p.color_hex,style:p.style,image_url:p.image_url,digital_link:`${new URL(c.req.url).origin}/01/${p.gtin}/21/${p.serial}`,wishlist_only:false,ownership:'Scan this QR or enter its activation key to register the garment once.'};}
app.get('/api/v1/scan/01/:gtin/21/:serial',async c=>c.json(await scan(c)));
app.get('/01/:gtin/21/:serial',async c=>{const p=await scan(c);return c.html(`<!doctype html><meta name="viewport" content="width=device-width"><title>Register garment</title><h1>${escape(p.name)}</h1><p id="result">Registering garment…</p><a href="${origin}/LIVE-DEMO/app/#/wardrobe">Open my wardrobe</a><script>fetch('/api/v1/garments/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify({gtin:p.gtin,serial:p.serial})})}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.detail);document.getElementById('result').textContent=d.name+' added to your wardrobe.';}).catch(e=>document.getElementById('result').textContent='Unable to register: '+e.message);</script>`);});
app.get('/api/v1/codes/:serial/qr.svg',async c=>{const row=(await query('SELECT gtin FROM garment_code WHERE serial=$1',[c.req.param('serial')]))[0];if(!row)fail(404,'unknown serial');const svg=await QRCode.toString(`${new URL(c.req.url).origin}/01/${row.gtin}/21/${c.req.param('serial')}`,{type:'svg'});return c.body(svg,200,{'Content-Type':'image/svg+xml'});});

const toTime=v=>new Date(v.includes('T')?v:v.replace(' ','T'));
const whenDate=v=>v?new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(v)?v:v+'+07:00'):new Date();
async function forecast(adm4){
  const key='weather:'+adm4,now=Date.now();const cached=await state(key), fault=await activeFault();
  if(cached&&cached.expires>now)return {...cached,source:'CACHED',note:'cache hit'};
  const started=performance.now();
  try {
    if(fault!=='none')throw new Error('injected '+fault);
    let payload;
    if(process.env.WEATHER_MODE==='mock'){payload=structuredClone(fixture);const entries=payload.data[0].cuaca.flat();const first=Date.parse(entries[0].utc_datetime.replace(' ','T')+'Z');const delta=Math.floor(now/3600000)*3600000-3600000-first;for(const e of entries){e.utc_datetime=new Date(Date.parse(e.utc_datetime.replace(' ','T')+'Z')+delta).toISOString().slice(0,19).replace('T',' ');}}
    else {const r=await fetch(bmkg+'?adm4='+adm4,{signal:AbortSignal.timeout(3000)});if(!r.ok)throw new Error('BMKG HTTP '+r.status);payload=await r.json();}
    const tz=payload.lokasi?.timezone||'Asia/Jakarta';const offset=tz==='Asia/Jayapura'?'+09:00':tz==='Asia/Makassar'?'+08:00':'+07:00';
    const entries=payload.data?.[0]?.cuaca?.flat();if(!entries?.length)throw new Error('feed has no entries');
    const parsed=entries.map(e=>{const at=e.utc_datetime?new Date(e.utc_datetime.replace(' ','T')+'Z'):new Date(e.local_datetime.replace(' ','T')+offset);if(!e.local_datetime||typeof e.t!=='number'||e.t<15||e.t>40||typeof e.hu!=='number'||e.hu<0||e.hu>100||typeof e.weather_desc!=='string'||!e.weather_desc.trim()||!Number.isFinite(+at)||+at<now-86400000||+at>now+3*86400000)throw new Error('invalid BMKG entry');return {at:at.toISOString(),t:e.t,humidity:Math.round(e.hu),description:e.weather_desc,rain:e.weather_desc.toLowerCase().includes('hujan'),hot:e.t>=32};}).sort((a,b)=>a.at.localeCompare(b.at));
    const fc={slots:parsed,fetched_at:new Date(now).toISOString(),expires:now+10800000,timezone:tz,source:'LIVE',note:''};await put(key,fc);await log('I2','GET '+bmkg+'?adm4='+adm4,200,performance.now()-started);return fc;
  }catch(e){await log('I2','GET '+bmkg+'?adm4='+adm4,null,performance.now()-started,null,e.message);if(cached&&now-Date.parse(cached.fetched_at)<=21600000)return {...cached,source:'CACHED',note:'fallback after '+e.message};return {source:'MANUAL_REQUIRED',note:e.message,slots:[]};}
}
app.get('/api/v1/weather',async c=>{const adm4=c.req.query('adm4')||'31.71.03.1001';if(!adm4Schema.safeParse(adm4).success)fail(422,'invalid adm4');const fc=await forecast(adm4);c.set('weather_source',fc.source);return c.json({...fc,adm4,credit,slots:fc.slots.map(s=>({...s,local_time:new Date(s.at).toLocaleString('en-GB',{timeZone:fc.timezone||'Asia/Jakarta'})}))});});
app.post('/api/v1/outfits/recommend',async c=>{
  const b=await body(c,z.object({occasion:z.enum(occasions),when:z.string().optional().nullable(),adm4:adm4Schema.optional().nullable(),manual_weather:z.object({rain:z.boolean(),hot:z.boolean()}).optional().nullable()}));const when=whenDate(b.when);if(!Number.isFinite(+when))fail(422,'invalid datetime');let weather;
  if(b.manual_weather)weather={...b.manual_weather,source:'MANUAL',at:when.toISOString(),fetched_at:null,t:null,humidity:null,description:'Manual answer',note:'manual override',credit:null};
  else {const fc=await forecast(b.adm4||'31.71.03.1001');const slot=fc.slots.reduce((a,s)=>!a||Math.abs(Date.parse(s.at)-when)<Math.abs(Date.parse(a.at)-when)?s:a,null);if(!slot||Math.abs(Date.parse(slot.at)-when)>10800000){weather={source:'MANUAL_REQUIRED',note:fc.note||'no forecast slot near requested time',ask:['rain','hot'],credit};}else weather={...slot,source:fc.source,fetched_at:fc.fetched_at,note:fc.note,credit};}
  c.set('weather_source',weather.source);if(weather.source==='MANUAL_REQUIRED')return c.json({weather,outfits:[],message:'Weather unavailable. Answer two taps (Rainy/Dry, Hot/Normal) and resend with manual_weather.'});
  weather.local_time=new Date(weather.at).toLocaleString('en-GB',{timeZone:'Asia/Jakarta'})+' WIB';const context={rain:weather.rain,hot:weather.hot,occasion:b.occasion};const recs=recommend(await wardrobe(),context,new Date(+when+7*3600000).toISOString().slice(0,10));const shown=[...new Set(recs.flatMap(r=>r.items.map(g=>g.id)))];if(shown.length)await query('UPDATE garment SET times_recommended=times_recommended+1 WHERE id=ANY($1::uuid[])',[shown]);return c.json({weather,context,outfits:recs,message:recs.length?null:context.rain?'No rain-ready outfit for this occasion; add rain footwear or a rain outer.':"No outfit satisfies this occasion's rules; add suitable garments."});
});
app.post('/api/v1/admin/fault',async c=>{const b=await body(c,z.object({mode:z.enum(faults)}));await put('fault',{mode:b.mode,expires:Date.now()+600000});await query("UPDATE neon_demo_state SET value=jsonb_set(value,'{expires}','0'::jsonb) WHERE key LIKE 'weather:%'");return c.json({fault:b.mode,expires_in_seconds:b.mode==='none'?0:600});});
app.post('/api/v1/admin/weather/clear-cache',async c=>{await query("DELETE FROM neon_demo_state WHERE key LIKE 'weather:%'");return c.json({cleared:true});});
app.post('/api/v1/admin/reset',async c=>{await transaction(async db=>{for(const table of ['wear_log','outfit_item','outfit','activation_attempt','interface_log','garment','garment_code'])await query('DELETE FROM '+table,[],db);for(const g of seed.garments)await query('INSERT INTO garment(id,owner_id,name,slot,attrs,times_recommended,times_chosen,last_worn_at,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,now())',[g.id,user,g.name,g.slot,JSON.stringify(g.attrs),g.times_recommended||0,g.times_chosen||0,g.last_worn_at||null],db);await query('DELETE FROM neon_demo_state',[],db);});return c.json({reset:true});});
app.get('/api/v1/metrics/interface-log',async c=>{const limit=z.coerce.number().int().min(1).max(500).safeParse(c.req.query('limit')||50);const iface=c.req.query('interface');if(!limit.success||iface&&!/^I[1-6]$/.test(iface))fail(422,'invalid log filter');const rows=await query('SELECT * FROM interface_log WHERE ($1::text IS NULL OR interface=$1) ORDER BY id DESC LIMIT $2',[iface||null,limit.data]);return c.json(rows);});
app.get('/api/v1/metrics/summary',async c=>{const counts=await query('SELECT interface,count(*)::int AS n FROM interface_log GROUP BY interface');const calls=await query("SELECT count(*)::int AS n FROM interface_log WHERE interface='I2' AND at>=now()-interval '24 hours'");return c.json({rows_per_interface:Object.fromEntries(counts.map(r=>[r.interface,r.n])),bmkg_calls_last_24h:calls[0].n});});
export default app;
