/** @typedef {import('./contracts').Garment} Garment */
/** @typedef {import('./contracts').Outfit} Outfit */
/** @typedef {import('./contracts').Forecast} Forecast */
const env = import.meta.env || {};
const base = (env.VITE_API_BASE || '').replace(/\/$/, '') + '/api/v1';
export class ApiError extends Error {
  constructor(status, detail) {
    super(Array.isArray(detail) ? detail.map(issue => issue.msg).join(' · ') : detail || 'The server could not complete the request.');
    this.status = status;
    this.detail = detail;
  }
}
export async function request(path, {method = 'GET', body, protectedRead = false, blob = false} = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' || protectedRead) headers['X-API-Key'] = env.VITE_API_KEY || 'demo-key';
  try {
    const response = await fetch(base + path, {method, headers, signal: controller.signal, body: body === undefined ? undefined : JSON.stringify(body)});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail);
    }
    if (response.status === 204) return undefined;
    return blob ? await response.blob() : await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error(error.name === 'AbortError' ? 'The server took too long. Try again.' : 'The wardrobe server is offline. Start the demo server and try again.');
  } finally {
    clearTimeout(timeout);
  }
}
const post = (path, body) => request(path, {method:'POST', body});
const remove = path => request(path, {method:'DELETE'});
const id = encodeURIComponent;
export const locationCode = '31.71.03.1001';
export const api = {
  wardrobe: () => request('/wardrobe'),
  health: () => request('/health'),
  weather: () => request('/weather?adm4=' + locationCode),
  recommend: values => post('/outfits/recommend', {...values, adm4:locationCode}),
  outfits: week => request('/outfits' + (week ? '?week=' + id(week) : '')),
  save: values => post('/outfits', values),
  deleteOutfit: outfitId => remove('/outfits/' + id(outfitId)),
  wear: (outfitId, worn_on) => post('/outfits/' + id(outfitId) + '/wear', {worn_on}),
  avatar: outfitId => request('/avatar/' + id(outfitId)),
  add: values => post('/garments', values),
  deleteGarment: garmentId => remove('/garments/' + id(garmentId)),
  activate: code => post('/garments/activate', {code}),
  registerScan: (gtin, serial) => post('/garments/scan', {gtin,serial}),
  scan: (gtin, serial) => request('/scan/01/' + id(gtin) + '/21/' + id(serial)),
  qr: serial => request('/codes/' + id(serial) + '/qr.svg', {protectedRead:true, blob:true}),
  log: filter => request('/metrics/interface-log?limit=50' + (filter ? '&interface=' + id(filter) : '')),
  summary: () => request('/metrics/summary'),
  fault: mode => post('/admin/fault', {mode}),
  clearWeather: () => post('/admin/weather/clear-cache'),
  products: () => request('/admin/products', {protectedRead:true}),
  issue: gtin => post('/admin/codes', {gtin,count:1}),
  reset: () => post('/admin/reset'),
};
