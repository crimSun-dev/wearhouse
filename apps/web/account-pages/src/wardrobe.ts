/**
 * TEMPORARY wardrobe pages (build-wearhouse-wardrobe-planning-services 7.2): the "Library". Plain DOM, no polish.
 * Wardrobe (shelves, items, care, slot), Add item (with private photo), Looks, Planner (7 days), Suggestions.
 */
import type {Look, Planner, Shelf, Suggestions, WardrobeItem, WardrobeItems} from '@wearhouse/contracts';

import {newIdempotencyKey, type ApiClient} from './api.ts';
import {currentSettings} from './settings.ts';
import {sizeOptions} from './sizes.ts';
import {shareControls} from './social.ts';
import {act, button, el, field, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient};
let ctx: Ctx;

export function initWardrobe(c: Ctx) {
  ctx = c;
}

const SLOTS = ['top', 'outer', 'bottom', 'dress', 'footwear', 'bag', 'headwear', 'eyewear', 'earrings', 'necklace', 'tie',
  'scarf', 'belt', 'wrist', 'ring', 'accessory'];  // accessory = uncategorized
const CARE = ['ready', 'laundry', 'repair', 'stored'];
const label = (i: WardrobeItem) => `${i.name ?? '(unnamed)'} · ${i.slot}`;

function subnav(): HTMLElement {
  return el('p', {className: 'subnav'}, el('a', {href: '#/wardrobe', text: 'All items'}), ' · ',
            el('a', {href: '#/wardrobe/add', text: 'Add item'}), ' · ', el('a', {href: '#/wardrobe/shelves', text: 'Shelves'}),
            ' · ', el('a', {href: '#/looks', text: 'Looks'}), ' · ', el('a', {href: '#/planner', text: 'Planner'}), ' · ',
            el('a', {href: '#/suggestions', text: 'Suggestions'}));
}

async function allItems(): Promise<WardrobeItem[]> {
  return (await ctx.api().call<WardrobeItems>('GET', '/me/wardrobe/items')).items;
}

// ================================================================== Wardrobe (library)
export async function wardrobePage(parts: string[]) {
  if (parts[0] === 'add') return addItemPage();
  if (parts[0] === 'shelves') return shelvesPage();
  const api = ctx.api();
  const shelfId = parts[0] === 'shelf' ? parts[1] : undefined;
  const params = new URLSearchParams(location.hash.split('?')[1] ?? '');
  const sortBy = params.get('sort') ?? '';
  const [shelves, page, sizes] = await Promise.all([
    api.call<Shelf[]>('GET', '/me/wardrobe/shelves'),
    api.call<WardrobeItems>('GET', '/me/wardrobe/items', {query: {shelf_id: shelfId, sort: sortBy || undefined}}),
    sizeOptions('size: unknown')]);
  const sorter = select('sort', [['', 'Default order'], ['size', 'Size'], ['name', 'Name'], ['worn', 'Most worn']], sortBy);
  sorter.id = 'wardrobe-sort';
  sorter.addEventListener('change', () => {
    location.hash = `#/wardrobe${shelfId ? `/shelf/${shelfId}` : ''}${sorter.value ? `?sort=${sorter.value}` : ''}`;
  });
  const side = el('ul', {className: 'list shelves', ariaLabel: 'Shelves'},
    el('li', {}, el('a', {href: '#/wardrobe', text: 'All items'})),
    ...shelves.map(s => el('li', {}, el('a', {href: `#/wardrobe/shelf/${s.id}`, text: `${s.name} (${s.count})`}))));
  const cards = page.items.map(i => {
    const care = select('care', CARE.map(c => [c, c]), i.care_state);
    care.ariaLabel = `Care state of ${i.name}`;
    care.addEventListener('change', () => act(null, async () => {
      await api.call('PATCH', `/me/wardrobe/items/${i.id}`, {body: {care_state: care.value}});
      return `${i.name}: ${care.value}.`;
    }));
    const slot = select('slot', [['', i.slot_source === 'override' ? 'clear override' : `slot: ${i.slot}`], ...SLOTS.map(s => [s, s] as [string, string])]);
    slot.ariaLabel = `Slot of ${i.name}`;
    slot.addEventListener('change', () => act(null, async () => {
      await api.call('PATCH', `/me/wardrobe/items/${i.id}`, {body: {slot_override: slot.value || null}});
      await wardrobePage(parts);
      return `${i.name}: slot ${slot.value || 'reset'}.`;
    }));
    const current = i.size ? `${i.size.system}:${i.size.code}` : '';
    const size = select('size', sizes, current);
    size.ariaLabel = `Size of ${i.name}`;
    size.addEventListener('change', () => act(null, async () => {
      const [system, code] = size.value.split(':');
      await api.call('PATCH', `/me/wardrobe/items/${i.id}`, {body: {size: size.value ? {system, code} : null}});
      await wardrobePage(parts);
      return `${i.name}: size ${size.value ? code : 'cleared'}.`;
    }));
    const attrs = el('details', {className: 'attrs'}, el('summary', {text: 'Attributes'}),
      ...Object.entries(i.attributes ?? {}).map(([k, a]) => {
        const opts: Array<[string, string]> = k === 'warmth'
          ? [['', `rule: ${a.origin === 'rule' ? a.value : '…'}`], ['light', 'light'], ['medium', 'medium'], ['heavy', 'heavy']]
          : [['', `rule${a.origin === 'rule' ? `: ${a.value ? 'yes' : 'no'}` : ''}`], ['true', 'yes'], ['false', 'no']];
        const pick = select(k, opts, a.origin === 'owner' ? String(a.value) : '');
        pick.ariaLabel = `${k.replace('_', ' ')} of ${i.name}`;
        pick.addEventListener('change', () => act(null, async () => {
          const value = pick.value === '' ? null : k === 'warmth' ? pick.value : pick.value === 'true';
          await api.call('PATCH', `/me/wardrobe/items/${i.id}`, {body: {attributes: {[k]: value}}});
          return `${i.name}: ${k.replace('_', ' ')} ${value === null ? 'back to the rule' : 'set'}.`;
        }));
        return el('label', {className: 'check'}, `${k.replace('_', ' ')} `, pick);
      }));
    const photo = el('span', {className: 'thumb empty', ariaHidden: 'true'});
    if (i.has_photo) {
      void api.raw(`/me/wardrobe/items/${i.id}/photo`).then(async r => {
        if (r.ok) photo.replaceWith(el('img', {className: 'thumb', alt: '', src: URL.createObjectURL(await r.blob())}));
      });
    }
    return el('li', {className: 'card product'}, photo,
      el('span', {className: 'who'}, el('strong', {text: i.name ?? '(unnamed)'}), el('br'),
         el('small', {text: [i.verified ? 'verified' : 'declared (not verified)', i.category, i.colour_known ? i.colour : 'colour unknown',
                             i.size ? `size ${i.size.label}${i.size_source === 'purchase' ? ' (bought)' : ''}` : 'size unknown',
                             `worn ${i.wear_count}×`].filter(Boolean).join(' · ')})),
      care, slot, size, attrs,
      i.kind === 'declared' ? button('Archive', b => act(b, async () => {
        await api.call('PATCH', `/me/wardrobe/items/${i.id}`, {body: {archived: true}});
        await wardrobePage(parts);
        return `${i.name} archived.`;
      })) : '');
  });
  const title = shelfId ? (shelves.find(s => s.id === shelfId)?.name ?? 'Shelf') : 'Wardrobe';
  const prefs = currentSettings()?.values;  // add-wearhouse-settings-security: default view + auto-categorize
  const listClass = prefs?.wardrobe_view === 'list' ? 'list' : 'list grid';
  let body: HTMLElement;
  if (prefs?.wardrobe_group_by_slot !== false && !sortBy) {
    const groups = new Map<string, HTMLElement[]>();
    page.items.forEach((i, n) => groups.set(i.slot, [...(groups.get(i.slot) ?? []), cards[n]]));
    const order = [...SLOTS, 'unknown'].filter(s => groups.has(s));
    body = el('div', {}, ...order.map(s => el('section', {}, el('h2', {text: s === 'unknown' ? 'Not categorized' : s}),
                                                 el('ul', {className: listClass, ariaLabel: `Items: ${s}`}, ...groups.get(s)!))));
  } else {
    body = el('ul', {className: listClass, ariaLabel: 'Items'}, ...cards);
  }
  view(`${title} (${page.items.length})`, subnav(), field('Sort by', sorter), el('div', {className: 'library'}, side, body),
       page.items.length ? '' : el('p', {text: 'No items yet. Claim a garment or add one you already own.'}));
}

async function addItemPage() {
  const sizeChoice = select('size', await sizeOptions('Unknown'));
  const name = el('input', {name: 'name', required: true, maxLength: 80});
  const slot = select('slot', SLOTS.map(s => [s, s]), 'top');
  const category = el('input', {name: 'category', maxLength: 60, placeholder: 'optional'});
  const colour = el('input', {name: 'colour', maxLength: 40, placeholder: 'optional, e.g. Black'});
  const photo = el('input', {type: 'file', name: 'photo', accept: 'image/jpeg,image/png,image/webp'});
  const form = el('form', {}, field('Name', name), field('Slot', slot), field('Size', sizeChoice), field('Category', category), field('Colour', colour),
                  field('Photo (private, max 2 MB)', photo),
                  el('p', {className: 'hint', text: 'Declared items are not verified: they get no serial, and anything you leave empty stays unknown.'}),
                  el('button', {type: 'submit', text: 'Add to wardrobe', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      const item = await ctx.api().call<WardrobeItem>('POST', '/me/wardrobe/items', {body: {
        name: name.value, slot: slot.value, category: category.value || null, colour: colour.value || null,
        ...(sizeChoice.value ? {size: {system: sizeChoice.value.split(':')[0], code: sizeChoice.value.split(':')[1]}} : {})}});
      if (photo.files?.[0]) await ctx.api().upload('PUT', `/me/wardrobe/items/${item.id}/photo`, photo.files[0]);
      location.hash = '#/wardrobe';
      return `${item.name} added.`;
    });
  });
  view('Add an item you already own', subnav(), form);
}

async function shelvesPage() {
  const api = ctx.api();
  const [shelves, items] = await Promise.all([api.call<Shelf[]>('GET', '/me/wardrobe/shelves'), allItems()]);
  const editor = (s?: Shelf) => {
    const name = el('input', {name: 'name', value: s?.name ?? '', required: true, maxLength: 40});
    name.id = `shelf-name-${s?.id ?? 'new'}`;
    const boxes = items.map(i => {
      const cb = el('input', {type: 'checkbox', value: i.id, checked: !!s?.item_ids.includes(i.id)});
      cb.id = `shelf-${s?.id ?? 'new'}-${i.id}`;
      return el('label', {className: 'check', htmlFor: cb.id}, cb, ' ', label(i));
    });
    const form = el('form', {}, field('Shelf name', name), el('fieldset', {}, el('legend', {text: 'Items'}), ...boxes),
                    el('button', {type: 'submit', text: s ? 'Save shelf' : 'Create shelf', className: 'primary'}),
                    s ? button('Delete shelf', b => act(b, async () => {
                      await api.call('DELETE', `/me/wardrobe/shelves/${s.id}`);
                      await shelvesPage();
                      return 'Shelf deleted.';
                    }), 'danger') : '');
    form.addEventListener('submit', e => {
      e.preventDefault();
      const ids = boxes.map(b => b.querySelector('input')!).filter(c => c.checked).map(c => c.value);
      act(form.querySelector('button[type=submit]') as HTMLButtonElement, async () => {
        if (s) await api.call('PATCH', `/me/wardrobe/shelves/${s.id}`, {body: {name: name.value, item_ids: ids}});
        else await api.call('POST', '/me/wardrobe/shelves', {body: {name: name.value, item_ids: ids}});
        await shelvesPage();
        return 'Shelf saved.';
      });
    });
    return el('section', {}, el('h2', {text: s ? s.name : 'New shelf'}), form);
  };
  view('Shelves', subnav(), ...shelves.map(s => editor(s)), editor());
}

// ================================================================== Looks
function lookForm(items: WardrobeItem[], onSave: (name: string, slots: Record<string, string[]>) => Promise<unknown>,
                  initial?: Look): HTMLFormElement {
  const name = el('input', {name: 'look_name', required: true, maxLength: 60, value: initial?.name ?? ''});
  name.id = `look-name-${initial?.id ?? 'new'}`;
  const current = initial?.current.slots ?? {};
  const pickers: Array<[string, HTMLSelectElement]> = [];
  for (const slot of SLOTS) {
    const count = slot === 'accessory' ? 3 : 1;
    const choices = items.filter(i => i.slot === slot && i.care_state !== 'stored');
    for (let n = 0; n < count; n++) {
      const s = select(`${slot}-${n}`, [['', '— none —'], ...choices.map(i => [i.id, i.name ?? i.id] as [string, string])],
                       current[slot]?.[n] ?? '');
      s.id = `look-${initial?.id ?? 'new'}-${slot}-${n}`;
      pickers.push([slot, s]);
    }
  }
  const form = el('form', {}, field('Look name', name),
                  ...pickers.map(([slot, s], i) => field(slot === 'accessory' ? `accessory ${i - pickers.findIndex(p => p[0] === 'accessory') + 1}` : slot, s)),
                  el('p', {className: 'hint', text: 'A dress cannot be combined with a top or bottom.'}),
                  el('button', {type: 'submit', text: initial ? 'Save new revision' : 'Create look', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    const slots: Record<string, string[]> = {};
    for (const [slot, s] of pickers) if (s.value) (slots[slot] ??= []).push(s.value);
    act(form.querySelector('button[type=submit]') as HTMLButtonElement, () => onSave(name.value, slots).then(() => 'Look saved.'));
  });
  return form;
}

export async function looksPage() {
  const api = ctx.api();
  const [looks, items] = await Promise.all([api.call<Look[]>('GET', '/me/looks'), allItems()]);
  view('Looks', subnav(),
       ...looks.map(l => el('section', {className: 'look'},
         el('h2', {text: `${l.name} (revision ${l.current_revision_no})`}),
         el('ul', {}, ...l.current.items.map(x => el('li', {text: `${x.slot}: ${x.item?.name ?? '(item no longer in your wardrobe)'}`}))),
         shareControls(l.id),
         el('details', {}, el('summary', {text: 'Edit'}), lookForm(items, async (name, slots) => {
           await api.call('PATCH', `/me/looks/${l.id}`, {body: {name, slots}});
           await looksPage();
         }, l)),
         button('Delete look', b => act(b, async () => {
           await api.call('DELETE', `/me/looks/${l.id}`);
           await looksPage();
           return 'Look deleted (plans keep their revision).';
         }), 'danger'))),
       el('h2', {text: 'New look'}),
       lookForm(items, async (name, slots) => { await api.call('POST', '/me/looks', {body: {name, slots}}); await looksPage(); }));
}

// ================================================================== Planner
export async function plannerPage() {
  const api = ctx.api();
  const [planner, looks] = await Promise.all([api.call<Planner>('GET', '/me/planner'), api.call<Look[]>('GET', '/me/looks')]);
  const adm4 = el('input', {name: 'adm4', placeholder: 'e.g. 31.71.03.1001', maxLength: 13});
  const loc = el('form', {}, field('BMKG location code (adm4)', adm4), el('button', {type: 'submit', text: 'Save location'}));
  loc.addEventListener('submit', e => {
    e.preventDefault();
    act(loc.querySelector('button'), async () => {
      await api.call('PUT', '/me/weather/location', {body: {adm4: adm4.value.trim()}});
      await plannerPage();
      return 'Location saved.';
    });
  });
  const days = planner.days.map(day => {
    const w = day.weather;
    const weather = w.status === 'forecast'
      ? `${w.min_temp_c}–${w.max_temp_c} °C${w.rain ? ', rain' : ''}${w.hot ? ', hot' : ''} (${w.source})`
      : w.status === 'beyond_forecast' ? 'Beyond the forecast horizon' : `No forecast (${w.reason ?? 'unavailable'})`;
    const pick = select('look', [['', '— choose a look —'], ...looks.map(l => [l.current.id, l.name] as [string, string])],
                        day.plan?.look_revision.id ?? '');
    pick.ariaLabel = `Look for ${day.date}`;
    const controls: (HTMLElement | string)[] = [];
    if (!day.past) {
      controls.push(pick, button('Plan', b => act(b, async () => {
        if (!pick.value) throw new Error('Choose a look first.');
        await api.call('PUT', `/me/planner/${day.date}`, {body: {look_revision_id: pick.value}});
        await plannerPage();
        return `Planned for ${day.date}.`;
      })));
      if (day.plan) controls.push(button('Clear', b => act(b, async () => {
        await api.call('DELETE', `/me/planner/${day.date}`);
        await plannerPage();
        return 'Plan cleared.';
      })));
    }
    if (day.is_today && day.plan) {
      controls.push(button('I wore this', b => act(b, async () => {
        await api.call('POST', '/me/wear', {body: {worn_on: day.date, look_revision_id: day.plan!.look_revision.id},
                                            idem: newIdempotencyKey()});
        await plannerPage();
        return 'Wear logged.';
      }), 'primary'));
    }
    return el('li', {className: 'card day'},
      el('span', {className: 'who'}, el('strong', {text: `${day.date}${day.is_today ? ' (today)' : ''}`}), el('br'),
         el('small', {text: weather}), el('br'),
         el('span', {text: day.plan ? `Planned: ${day.plan.look_revision.name} (r${day.plan.look_revision.revision_no})` : 'Nothing planned'}),
         day.worn.length ? el('span', {text: ` · Worn: ${day.worn.length} entry`}) : ''),
      ...controls);
  });
  view('Planner (next 7 days)', subnav(), loc,
       el('p', {className: 'hint', text: 'Weather comes from BMKG and is never invented: days past the forecast horizon say so.'}),
       el('ul', {className: 'list'}, ...days));
}

// ================================================================== Suggestions
const OCCASIONS: Array<[string, string]> = [['casual', 'Casual'], ['campus', 'Campus'], ['hangout', 'Hangout'],
  ['worship', 'Worship (long sleeves + long bottom)'], ['wedding', 'Wedding (formal piece)']];
const RULE_LABEL: Record<string, string> = {heat: 'heat', rain: 'rain', worship_dress_code: 'worship dress code',
  wedding_dress_code: 'wedding dress code'};

export async function suggestionsPage() {
  const api = ctx.api();
  const date = el('input', {type: 'date', name: 'date', value: new Date().toISOString().slice(0, 10)});
  const occasion = select('occasion', OCCASIONS, 'casual');
  const rain = select('rain', [['', 'Use forecast'], ['true', 'Rain'], ['false', 'No rain']]);
  const hot = select('hot', [['', 'Use forecast'], ['true', 'Hot'], ['false', 'Not hot']]);
  const out = el('div', {});
  const form = el('form', {}, field('Date', date), field('Occasion', occasion), field('Rain', rain), field('Heat', hot),
                  el('button', {type: 'submit', text: 'Suggest outfits', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      const s = await api.call<Suggestions>('GET', '/me/recommendations/outfits', {query: {
        date: date.value, occasion: occasion.value, rain: rain.value || undefined, hot: hot.value || undefined, limit: '5'}});
      if (!s.enabled || !s.model) {
        out.replaceChildren(el('p', {}, 'Style suggestions are turned off. ',
                                     el('a', {href: '#/settings/style', text: 'Turn them on in Settings'}), '.'));
        return 'Suggestions are off.';
      }
      const removed = Object.entries(s.removed_by_rule ?? {}).map(([k, n]) => `${RULE_LABEL[k] ?? k} removed ${n}`);
      const event = (body: {kind: 'displayed' | 'chosen'; index?: number}) =>
        api.call('POST', `/me/recommendations/outfits/${s.run_id}/events`, {body});
      out.replaceChildren(
        el('p', {className: 'hint', text: `Ranked by ${s.model.name} (${s.model.mode}) with ${s.ruleset} and the thesis score `
          + `(${s.style ?? 'balanced'}: compatibility ${s.weights?.compatibility}, preference ${s.weights?.preference}, `
          + `recency ${s.weights?.recency}); weather ${s.weather.source}${s.weather.source === 'DISABLED' ? ' (off in Settings)' : ''}; `
          + `${s.ready_items} ready items, ${s.candidates_considered} combinations${removed.length ? '; ' + removed.join(', ') : ''}.`}),
        ...(s.reasons.length ? [el('p', {className: 'warn', text: s.reasons.join('; ')})] : []),
        el('ol', {ariaLabel: 'Suggested outfits'}, ...s.suggestions.map((x, n) => el('li', {},
          el('strong', {text: x.items.map(i => i.name).join(' + ')}), el('br'),
          el('small', {text: `score ${x.score ?? '—'} · ` + Object.entries(x.components).map(([k, v]) => `${k} ${v ?? 'unknown'}`).join(' · ')}),
          el('ul', {className: 'hint'}, ...(x.explanation ?? []).map(t => el('li', {text: t}))),
          button('Save as look', b => act(b, async () => {
            const slots: Record<string, string[]> = {};
            for (const [id, slot] of Object.entries(x.slots)) (slots[slot] ??= []).push(id);
            await api.call('POST', '/me/looks', {body: {name: `Suggested ${date.value}`, slots}});
            await event({kind: 'chosen', index: n});  // feeds preference (Eq. 8) once per run
            return 'Saved as a look.';
          }))))));
      if (s.run_id && s.suggestions.length) await event({kind: 'displayed'});  // exposures count only when shown
      return `${s.suggestions.length} suggestion(s).`;
    });
  });
  view('Outfit suggestions', subnav(), form, out);
}
