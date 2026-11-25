export const slots = ['top','bottom','dress','outer','footwear','accessory'];
export const slotNames = {top:'Tops',bottom:'Bottoms',dress:'Dresses',outer:'Outerwear',footwear:'Footwear',accessory:'Accessories'};
export const occasions = ['campus','casual','worship','formal','wedding'];
export const styles = ['casual','smart','formal','modest','sporty','street'];
export const cap = value => value ? value[0].toUpperCase() + value.slice(1) : '';
export const color = value => /^#[0-9a-f]{6}$/i.test(value || '') ? value : '#ae8b9d';
export const compose = (items, garment) => {
  if (items.some(item => item.id === garment.id)) return items.filter(item => item.id !== garment.id);
  return [...items.filter(item => item.slot !== garment.slot
    && !(garment.slot === 'dress' && ['top','bottom'].includes(item.slot))
    && !(item.slot === 'dress' && ['top','bottom'].includes(garment.slot))), garment];
};
const dateFormat = new Intl.DateTimeFormat('en-GB', {timeZone:'Asia/Jakarta', year:'numeric', month:'2-digit', day:'2-digit'});
export function today(date = new Date()) {
  const fields = Object.fromEntries(dateFormat.formatToParts(date).map(part => [part.type,part.value]));
  return [fields.year,fields.month,fields.day].join('-');
}
export const dateAt = day => new Date(day + 'T12:00:00+07:00');
export function shiftDay(day, delta) {
  return today(new Date(dateAt(day).getTime() + delta * 86400000));
}
export function weekDays(day) {
  const weekday = dateAt(day).getUTCDay() || 7;
  return Array.from({length:7}, (_, index) => shiftDay(day, index + 1 - weekday));
}
export function weekId(day) {
  const thursday = new Date(weekDays(day)[3] + 'T00:00:00Z');
  const year = thursday.getUTCFullYear();
  const week = Math.ceil(((thursday - Date.UTC(year,0,1)) / 86400000 + 1) / 7);
  return year + '-W' + String(week).padStart(2,'0');
}
export const displayDate = (day, options) => new Intl.DateTimeFormat('en-GB', {timeZone:'Asia/Jakarta', ...options}).format(dateAt(day));
export function scanTag(raw) {
  const url = new URL(raw.trim(), location.origin);
  const match = url.pathname.match(/^\/01\/(\d{14})\/21\/([^/]+)\/?$/);
  if (!match || !['https:','http:'].includes(url.protocol)) throw new Error('Paste a tag link with a GTIN and serial.');
  const serial = decodeURIComponent(match[2]);
  if (!/^[A-Za-z0-9._~-]+$/.test(serial)) throw new Error('The tag serial contains invalid characters.');
  return [match[1],serial];
}
