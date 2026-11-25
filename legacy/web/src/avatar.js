import {color} from './domain.js';
const shapes = {
  top:'M34 23l15-8h22l15 8 12 25-13 6-7-13v48H42V41l-7 13-13-6z',
  outer:'M32 23l17-9 11 7 11-7 17 9 10 55-13 3-8-38v48H43V43l-8 38-13-3z',
  bottom:'M39 17h42l5 75H66l-6-51-6 51H34z',
  skirt:'M43 20h34l16 64H27z',
  dress:'M42 26l10-11 8 9 8-9 10 11 4 30 13 34H25l13-34z',
  footwear:'M19 58h28l8-16 10 6v24H18zm52 0h21l8-16 9 6v24H70z',
  accessory:'M39 44c0-25 42-25 42 0h10l7 40H22l7-40zm9 0h24c0-13-24-13-24 0z',
};
export function garmentArt(garment) {
  const shape = garment.slot === 'bottom' && !garment.attrs.long_bottom ? 'skirt' : garment.slot;
  return '<svg viewBox="0 0 120 105" aria-hidden="true"><path d="' + shapes[shape] + '" fill="' + color(garment.attrs.color_hex) + '" stroke="#422738" stroke-opacity=".48" stroke-width="1.2" stroke-linejoin="round"/></svg>';
}
export function figure(items, avatar) {
  const slot = name => items.find(item => item.slot === name);
  const tint = (name, fallback) => avatar?.slots?.[name]?.tint ? color(avatar.slots[name].tint) : slot(name) ? color(slot(name).attrs.color_hex) : fallback;
  const dress = slot('dress');
  const skirt = slot('bottom') && !slot('bottom').attrs.long_bottom;
  const body = avatar?.body?.gender === 'male' ? 'M157 78l-18 12-12 80 21 4 9-57 8 80h50l8-80 9 57 21-4-12-80-18-12z' : 'M166 79l-23 13-12 77 19 4 10-57 9 74h42l9-74 10 57 19-4-12-77-23-13z';
  return '<svg viewBox="0 0 380 428" role="img" aria-label="Illustrated outfit preview"><defs><linearGradient id="studio" x2="0" y2="1"><stop stop-color="#e8d0db"/><stop offset="1" stop-color="#faf1ee"/></linearGradient></defs><path fill="url(#studio)" d="M0 0h380v428H0z"/><path stroke="#ac879a" stroke-opacity=".38" d="M0 339h380M70 0v339m240 0V0"/><ellipse cx="190" cy="382" rx="72" ry="10" fill="#654354" opacity=".16"/><path fill="#3e2b31" d="M168 54c-8-22 5-41 23-41s30 13 26 35l-3 35h-47z"/><ellipse cx="191" cy="48" rx="20" ry="25" fill="#bd826f"/><path fill="#3e2b31" d="M169 48c-3-29 38-38 47-7-12-1-21-7-28-12-5 11-12 16-19 19z"/><path fill="#bd826f" d="M181 65h19v27h-19zm-46 92h17l-3 68c-1 8-16 8-16-1zm93 0h17l2 67c0 9-15 9-16 1zm-68 79h24l-4 129h-19zm36 0h24l-1 129h-19z"/><path d="' + body + '" fill="' + tint('top','#d7aab9') + '" stroke="#402834" stroke-opacity=".32"/>' +
    (dress ? '<path d="M168 91l12-11 10 11 11-11 12 11-4 68 28 108h-94l28-108z" fill="'+tint('dress','#d7aab9')+'"/>' : skirt ? '<path d="M164 172h52l23 90h-98z" fill="'+tint('bottom','#a58d87')+'"/>' : '<path d="M164 173h52l10 186h-27l-9-123-9 123h-27z" fill="'+tint('bottom','#514653')+'"/>') +
    (slot('outer') ? '<path d="M168 83l15 12-4 112h-33l13-102-11 87h-19l13-101zm44 0l-15 12 4 112h33l-13-102 11 87h19l-13-101z" fill="'+tint('outer','#dbcbd1')+'" fill-opacity=".91" stroke="#402834" stroke-opacity=".27"/>' : '') +
    '<path d="M161 356h20l4 23h-44c0-10 7-12 20-14zm38 0h20v9c13 2 20 4 20 14h-44z" fill="'+tint('footwear','#f4e4dd')+'" stroke="#402834" stroke-opacity=".35"/>' +
    (slot('accessory') ? '<path d="M218 99l-45 91 3 3 48-91zm-57 82h25l7 38h-38z" fill="'+tint('accessory','#80586d')+'"/>' : '')+'</svg>';
}
