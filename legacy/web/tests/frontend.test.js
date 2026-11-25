import assert from 'node:assert/strict';
import {test} from 'node:test';
import {api, ApiError} from '../src/api.js';
import {compose, weekDays, weekId} from '../src/domain.js';

test('dress and separates replace each other without affecting footwear', () => {
  const top = {slot:'top',id:'top'};
  const bottom = {slot:'bottom',id:'bottom'};
  const footwear = {slot:'footwear',id:'footwear'};
  const dress = {slot:'dress',id:'dress'};
  assert.deepEqual(compose([top,bottom,footwear],dress),[footwear,dress]);
  assert.deepEqual(compose([dress,footwear],top),[footwear,top]);
  assert.deepEqual(compose([top,footwear],top),[footwear]);
});
test('ISO weeks remain correct near New Year', () => {
  assert.equal(weekId('2027-01-01'),'2026-W53');
  assert.equal(weekId('2027-01-04'),'2027-W01');
  assert.deepEqual(weekDays('2027-01-01'),['2026-12-28','2026-12-29','2026-12-30','2026-12-31','2027-01-01','2027-01-02','2027-01-03']);
});
test('API sends write credentials and accepts a 204 empty response', async t => {
  const fetch = t.mock.method(globalThis,'fetch',async()=>new Response(null,{status:204}));
  assert.equal(await api.wear('id','2026-11-24'),undefined);
  const [url,options] = fetch.mock.calls[0].arguments;
  assert.equal(url,'/api/v1/outfits/id/wear');
  assert.equal(options.method,'POST');
  assert.equal(options.headers['X-API-Key'],'demo-key');
  assert.deepEqual(JSON.parse(options.body),{worn_on:'2026-11-24'});
});
test('422 detail survives as structured input errors', async t => {
  t.mock.method(globalThis,'fetch',async()=>Response.json({detail:[{loc:['body','name'],msg:'Name is required.'}]},{status:422}));
  await assert.rejects(api.add({name:''}),error=>error instanceof ApiError&&error.status===422&&error.detail[0].loc[1]==='name');
});
test('network failure produces a recoverable offline error', async t => {
  t.mock.method(globalThis,'fetch',async()=>{throw new TypeError('Network error');});
  await assert.rejects(api.wardrobe(),/server is offline/);
});
test('QR reads carry the write key and return a blob', async t => {
  const fetch = t.mock.method(globalThis,'fetch',async()=>new Response('<svg/>',{headers:{'Content-Type':'image/svg+xml'}}));
  assert.equal((await api.qr('serial')).type,'image/svg+xml');
  assert.equal(fetch.mock.calls[0].arguments[1].headers['X-API-Key'],'demo-key');
});

test('retailer product reads carry the demo key', async t => {
  const fetch = t.mock.method(globalThis,'fetch',async()=>Response.json([]));
  await api.products();
  assert.equal(fetch.mock.calls[0].arguments[1].headers['X-API-Key'],'demo-key');
});

test('scanning registers the garment through a POST', async t => {
  const fetch=t.mock.method(globalThis,'fetch',async()=>Response.json({id:'garment'}));
  await api.registerScan('08999000000283','0123456789abcdef0123456789abcdef');
  const [url,options]=fetch.mock.calls[0].arguments;
  assert.equal(url,'/api/v1/garments/scan');
  assert.equal(options.method,'POST');
  assert.deepEqual(JSON.parse(options.body),{gtin:'08999000000283',serial:'0123456789abcdef0123456789abcdef'});
});
