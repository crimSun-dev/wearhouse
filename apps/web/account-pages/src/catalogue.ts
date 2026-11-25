/**
 * TEMPORARY catalogue pages (publish-wearhouse-catalogue 5.2). Store: public browse/search/collections/product.
 * Staff (catalogue_editor or admin): CSV import, review/publish/retire, collections. Plain DOM, no polish.
 */
import type {BrowsePage, Collection, Facets, ImportJob, ProductCard, ProductDetail, ProductsForMe, RecModel, ReviewItem,
  SimilarProducts, StaffCollection, StaffProduct} from '@wearhouse/contracts';

import type {ApiClient} from './api.ts';
import {offerBox, staffOffersPage} from './commerce.ts';
import {can, denied, hasStaffAccess, mediaPanel, moderationPage, ordersStaffPage, productsPage, rolesPage, staffHome,
  staffNav, unitsPage} from './staff.ts';
import {productSizesPanel, sizeOptions, staffSizesPage} from './sizes.ts';
import {act, button, el, field, say, select, view} from './ui.ts';

type Ctx = {api: () => ApiClient; caps: () => string[]; mediaUrl: (uri: string) => string};
let ctx: Ctx;

export function catalogueNav(caps: string[]): Array<[string, string]> {
  return hasStaffAccess(caps) ? [['store', 'Store'], ['staff', 'Staff workspace']] : [['store', 'Store']];
}

export function catalogueRoutes(c: Ctx) {
  ctx = c;
  return {
    async store(parts: string[]) {
      if (parts[0] === 'product' && parts[1]) return productPage(parts[1]);
      if (parts[0] === 'collection' && parts[1]) return collectionPage(parts[1]);
      return storePage();
    },
    async staff(parts: string[]) {
      const section = parts[0] ?? '';
      if (section === 'units') return unitsPage();
      if (section === 'orders') return ordersStaffPage();
      if (section === 'roles') return rolesPage();
      if (section === 'moderation') return can('social:moderate') ? moderationPage() : denied('Moderation');
      if (section === 'products') return productsPage();
      if (section === 'offers') return can('commerce:offers') ? staffOffersPage(staffNav()) : denied('Offers');
      if (section === 'sizes') return can('catalogue:ingest') ? staffSizesPage(staffNav()) : denied('Sizes');
      if (section === 'product' && parts[1]) {
        return can('catalogue:ingest') || can('catalogue:media') ? staffProductPage(parts[1]) : denied('Product');
      }
      if (['review', 'import', 'collections'].includes(section) && !can('catalogue:ingest')) return denied('Catalogue');
      if (section === 'review') return reviewPage();
      if (section === 'import') return importPage();
      if (section === 'collections') return staffCollectionsPage();
      return staffHome();
    },
  };
}

const anon = {anonymous: true} as const;

// ================================================================== Store
function cardItem(c: ProductCard): HTMLElement {
  const sizes = (c as ProductCard & {sizes?: string[]}).sizes ?? [];
  const range = sizes.length ? `sizes ${sizes[0]}${sizes.length > 1 ? '–' + sizes[sizes.length - 1] : ''}` : null;
  const bits = [c.category, c.colour, c.slot ? `slot: ${c.slot}` : null, range].filter(Boolean).join(' · ');
  const thumb = c.thumbnail
    ? el('img', {className: 'thumb', src: ctx.mediaUrl(c.thumbnail), alt: '', referrerPolicy: 'no-referrer', width: 64, height: 80})
    : el('span', {className: 'thumb empty', ariaHidden: 'true'});
  return el('li', {className: 'card product'}, thumb,
            el('span', {className: 'who'}, el('a', {href: `#/store/product/${c.id}`, text: c.name ?? '(unnamed)'}),
               el('br'), el('small', {text: bits})));
}

async function storePage() {
  const params = new URLSearchParams(location.hash.split('?')[1] ?? '');
  const api = ctx.api();
  const [facets, collections] = await Promise.all([
    api.call<Facets>('GET', '/catalogue/facets', anon), api.call<Collection[]>('GET', '/catalogue/collections', anon)]);
  const opts = (xs: Facets['category'], any: string): Array<[string, string]> =>
    [['', any], ...xs.map(f => [f.value, `${f.value} (${f.count})`] as [string, string])];
  const q = el('input', {type: 'search', name: 'q', maxLength: 100, value: params.get('q') ?? '', placeholder: 'Search products'});
  const category = select('category', opts(facets.category, 'Any category'), params.get('category') ?? '');
  const colour = select('colour', opts(facets.colour, 'Any colour'), params.get('colour') ?? '');
  const slot = select('slot', opts(facets.slot, 'Any slot'), params.get('slot') ?? '');
  const sort = select('sort', [['newest', 'Newest'], ['name', 'Name A–Z']], params.get('sort') ?? 'newest');
  const size = select('size', await sizeOptions('Any size'), params.get('size') ?? '');
  const mine = el('input', {type: 'checkbox', name: 'my_sizes', id: 'my-sizes', checked: params.get('my_sizes') === 'true'});
  const hideOwned = el('input', {type: 'checkbox', name: 'hide_owned', id: 'hide-owned', checked: params.get('hide_owned') === 'true'});
  const hideBox = ctx.caps().length ? el('label', {className: 'check', htmlFor: 'hide-owned'}, hideOwned, ' Hide what I own') : '';
  const mineBox = ctx.caps().length
    ? el('label', {className: 'check', htmlFor: 'my-sizes'}, mine, ' In my size (', el('a', {href: '#/sizes', text: 'set my sizes'}), ')')
    : '';
  const results = el('ul', {className: 'list grid', ariaLabel: 'Products'});
  const more = el('div', {});
  const form = el('form', {role: 'search'}, field('Search', q), field('Category', category), field('Colour', colour),
                  field('Wardrobe slot', slot), field('Size', size), mineBox, hideBox, field('Sort by', sort),
                  el('button', {type: 'submit', text: 'Search', className: 'primary'}));

  const query = () => ({q: q.value || undefined, category: category.value || undefined, colour: colour.value || undefined,
                        slot: slot.value || undefined, size: size.value || undefined,
                        my_sizes: mine.checked && ctx.caps().length ? 'true' : undefined,
                        hide_owned: hideOwned.checked && ctx.caps().length ? 'true' : undefined, sort: sort.value});
  async function load(cursor?: string) {
    const signed = query().my_sizes || query().hide_owned ? {} : anon;  // these filters need the caller's identity
    const page = await api.call<BrowsePage>('GET', '/catalogue/products', {...signed, query: {...query(), cursor}});
    if (!cursor) results.replaceChildren();
    results.append(...page.items.map(cardItem));
    if (!results.children.length) results.append(el('li', {text: 'No published products match.'}));
    more.replaceChildren(page.next_cursor
      ? button('Load more', b => act(b, () => load(page.next_cursor!), 'Loaded more.')) : '');
    return `${results.querySelectorAll('li.product').length} products shown.`;
  }
  form.addEventListener('submit', e => {
    e.preventDefault();
    const qs = new URLSearchParams(Object.entries(query()).filter(([, v]) => v) as [string, string][]).toString();
    history.replaceState(null, '', `#/store${qs ? '?' + qs : ''}`);
    act(form.querySelector('button'), () => load());
  });
  const featured = collections.filter(c => c.items.length).map(c => el('section', {className: 'collection'},
    el('h2', {}, el('a', {href: `#/store/collection/${c.slug}`, text: c.title})),
    el('ul', {className: 'list grid'}, ...c.items.slice(0, 6).map(cardItem))));
  view('Store', await recommendedSection(), ...featured, el('h2', {text: 'Browse'}), form, results, more);
  await load().then(msg => say(msg)).catch(() => undefined);
}

async function collectionPage(slug: string) {
  const c = await ctx.api().call<Collection>('GET', `/catalogue/collections/${encodeURIComponent(slug)}`, anon);
  view(c.title, el('p', {}, el('a', {href: '#/store', text: '← Store'})),
       el('ul', {className: 'list grid'}, ...c.items.map(cardItem)));
}

function modelNote(m: RecModel): HTMLElement {
  const label = m.mode === 'trained' ? `trained model ${m.name} (${(m.trained_artifact ?? '').slice(0, 12)})` : `baseline: ${m.name}`;
  return el('p', {className: 'hint', text: `Ranked by ${label}${m.fallback ? ` — ${m.fallback}` : ''}.`});
}

async function recommendedSection(): Promise<HTMLElement | string> {
  if (!ctx.caps().length) return '';  // signed out
  const r = await ctx.api().call<ProductsForMe>('GET', '/me/recommendations/products', {query: {limit: '6'}});
  return r.items.length ? el('section', {}, el('h2', {text: 'Recommended for you'}), modelNote(r.model),
                             el('ul', {className: 'list grid'}, ...r.items.map(cardItem))) : '';
}

async function similarSection(id: string): Promise<HTMLElement | string> {
  const r = await ctx.api().call<SimilarProducts>('GET', `/catalogue/products/${encodeURIComponent(id)}/similar`, {...anon, query: {limit: '6'}});
  return r.items.length ? el('section', {}, el('h2', {text: 'Similar products'}), modelNote(r.model),
                             el('ul', {className: 'list grid'}, ...r.items.map(cardItem))) : '';
}

async function productPage(id: string) {
  const p = await ctx.api().call<ProductDetail>('GET', `/catalogue/products/${encodeURIComponent(id)}`, anon);
  const rows = Object.entries(p.facts).map(([k, f]) =>
    el('tr', {}, el('th', {scope: 'row', text: k}), el('td', {text: String(f.value ?? '')}), el('td', {text: f.source_field ?? ''})));
  const notes = Object.entries(p.annotations).map(([k, a]) =>
    el('li', {text: `${k}: ${String(a.value)} (annotation, origin ${a.origin ?? '?'}${a.note ? ', ' + a.note : ''})`}));
  view(String(p.facts.product_name?.value ?? 'Product'),
       el('p', {}, el('a', {href: '#/store', text: '← Store'})),
       ...p.media.map(m => el('img', {className: 'media', src: ctx.mediaUrl(m.uri), alt: m.alt_text ?? '', referrerPolicy: 'no-referrer'})),
       await offerBox(p.id),
       el('h2', {text: 'Verified facts'}),
       el('table', {}, el('thead', {}, el('tr', {}, el('th', {text: 'Fact'}), el('th', {text: 'Value'}), el('th', {text: 'Source field'}))),
          el('tbody', {}, ...rows)),
       el('h2', {text: 'Annotations (not source facts)'}),
       notes.length ? el('ul', {}, ...notes) : el('p', {text: 'None.'}),
       el('p', {className: 'hint', text: `Source: ${p.source.name} (${p.source.namespace}), id ${p.source.external_id}. Revision ${p.revision_no}.`}),
       el('p', {className: 'hint', text: p.one_size ? 'One size.'
         : `Sizes: ${p.sizes.map(s => s.label).join(', ')}${p.sizes.some(s => s.origin === 'rule') ? ' (generated sizes: the source has none)' : ''}.`}),
       await similarSection(p.id));
}

// ================================================================== Staff
async function reviewPage() {
  const queue = await ctx.api().call<ReviewItem[]>('GET', '/admin/catalogue/review', {query: {limit: '100'}});
  view('Review queue', staffNav(),
       el('p', {className: 'hint', text: 'Products whose latest revision is not published yet.'}),
       el('ul', {className: 'list'}, ...queue.map(r => el('li', {className: 'card'},
         el('span', {className: 'who'}, el('a', {href: `#/staff/product/${r.product_id}`, text: r.name ?? r.external_id}),
            el('br'), el('small', {text: `${r.namespace} · ${r.external_id} · ${r.publication_state} · latest r${r.latest_revision_no}`
              + (r.published_revision_no ? ` · published r${r.published_revision_no}` : '')}))))),
       queue.length ? '' : el('p', {text: 'Nothing to review.'}));
}

async function staffProductPage(id: string) {
  const api = ctx.api();
  const p = await api.call<StaffProduct>('GET', `/admin/catalogue/products/${encodeURIComponent(id)}`);
  const revs = p.revisions.slice().reverse().map(r => {
    const published = r.id === p.published_revision_id;
    const facts = Object.entries(r.facts as Record<string, {value: unknown}>).map(([k, f]) => `${k}: ${String(f.value)}`).join('; ');
    return el('li', {className: 'card'},
      el('span', {className: 'who'}, el('strong', {text: `Revision ${r.revision_no}${published ? ' (published)' : ''}`}),
         el('br'), el('small', {text: facts})),
      published ? '' : button(`Publish revision ${r.revision_no}`, b => act(b, async () => {
        await api.call('POST', `/admin/catalogue/products/${id}/publish`, {body: {revision_id: r.id}});
        await staffProductPage(id);
        return `Published revision ${r.revision_no}.`;
      }), 'primary'));
  });
  const media = can('catalogue:media') ? await mediaPanel(id, () => staffProductPage(id)) : '';
  const sizes = can('catalogue:ingest') ? await productSizesPanel(id, () => staffProductPage(id)) : '';
  view(`Product ${p.source.external_id}`, staffNav(),
       el('p', {text: `State: ${p.publication_state}. Source: ${p.source.name} (${p.source.namespace}).`}),
       el('p', {}, el('a', {href: `#/store/product/${p.id}`, text: 'View in store'}), ' · ', el('code', {text: p.id})),
       el('ul', {className: 'list'}, ...revs),
       p.publication_state === 'retired' ? el('p', {text: 'Retired: hidden from the store. Owned items and tag lookups remain.'})
         : button('Retire product', b => act(b, async () => {
           await api.call('POST', `/admin/catalogue/products/${id}/retire`);
           await staffProductPage(id);
           return 'Product retired.';
         }), 'danger'),
       sizes, media);
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

function importPage() {
  const today = new Date().toISOString().slice(0, 10);
  const inp = (name: string, value = '', extra: Partial<HTMLInputElement> = {}) => el('input', {name, value, required: true, ...extra});
  const namespace = inp('namespace', 'hm-pfr');
  const sourceName = inp('source_name', 'H&M Personalized Fashion Recommendations');
  const sourceUrl = inp('source_url', 'https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations');
  const fileName = inp('file_name', 'articles.csv');
  const acquired = inp('acquired_on', today, {type: 'date'});
  const basis = inp('basis', '', {placeholder: 'e.g. kaggle-competition-rules'});
  const scope = inp('scope', '', {placeholder: 'What the permission allows'});
  const acceptedOn = inp('accepted_on', today, {type: 'date'});
  const acceptedBy = inp('accepted_by', '', {placeholder: 'Who accepted the terms'});
  const terms = inp('terms_url', '', {placeholder: 'https://… terms page'});
  const file = el('input', {type: 'file', accept: '.csv,text/csv', name: 'csv_file'});
  const text = el('textarea', {name: 'csv', rows: 8, placeholder: 'article_id,prod_name,product_type_name,…'});
  file.addEventListener('change', async () => { if (file.files?.[0]) text.value = await file.files[0].text(); });
  const out = el('div', {className: 'outcome'});
  const form = el('form', {},
    el('fieldset', {}, el('legend', {text: 'Source'}), field('Namespace', namespace), field('Source name', sourceName),
       field('Source URL', sourceUrl), field('Snapshot file name', fileName), field('Acquired on', acquired)),
    el('fieldset', {}, el('legend', {text: 'Permission (required: no import without one)'}), field('Basis', basis),
       field('Scope', scope), field('Accepted on', acceptedOn), field('Accepted by', acceptedBy), field('Terms URL', terms)),
    field('CSV file (H&M articles.csv columns)', file), field('CSV text', text),
    el('p', {className: 'hint', text: 'Up to 5000 rows / 10 MB per job. The snapshot checksum is the SHA-256 of this CSV text.'}),
    el('button', {type: 'submit', text: 'Run import', className: 'primary'}));
  form.addEventListener('submit', e => {
    e.preventDefault();
    act(form.querySelector('button'), async () => {
      const job = await ctx.api().call<ImportJob>('POST', '/admin/catalogue/import-jobs', {body: {
        source: {namespace: namespace.value, name: sourceName.value, url: sourceUrl.value},
        snapshot: {sha256: await sha256Hex(text.value), file_name: fileName.value, acquired_on: acquired.value},
        permission: {basis: basis.value, scope: scope.value, accepted_on: acceptedOn.value, accepted_by: acceptedBy.value,
                     terms_url: terms.value},
        mapping: 'hm-articles@1', csv: text.value}});
      const t = job.totals;
      out.replaceChildren(el('h2', {text: 'Import result'}),
        el('p', {text: `Created ${t.created ?? 0}, revised ${t.revised ?? 0}, unchanged ${t.unchanged ?? 0}, rejected ${t.rejected ?? 0}.`}),
        el('ul', {className: 'list'}, ...job.rows.map(r => el('li', {},
          r.product_id ? el('a', {href: `#/staff/product/${r.product_id}`, text: `Row ${r.row_no} (${r.external_id ?? '?'}): ${r.outcome}`})
            : el('span', {text: `Row ${r.row_no} (${r.external_id ?? '?'}): ${r.outcome}`}),
          ...((r.errors as Array<{field: string; message: string}>).map(x => el('small', {className: 'warn', text: ` ${x.field}: ${x.message}`})))))));
      return `Import finished: ${t.created ?? 0} created, ${t.rejected ?? 0} rejected.`;
    });
  });
  view('Import CSV', staffNav(), form, out);
}

async function staffCollectionsPage() {
  const api = ctx.api();
  const cols = await api.call<StaffCollection[]>('GET', '/admin/catalogue/collections');
  const editor = (c?: StaffCollection) => {
    const slug = el('input', {name: 'slug', value: c?.slug ?? '', required: true, maxLength: 63, readOnly: !!c,
                              placeholder: 'e.g. autumn-picks'});
    const title = el('input', {name: 'title', value: c?.title ?? '', required: true, maxLength: 120});
    const ids = el('textarea', {name: 'product_ids', rows: 4, value: (c?.items ?? []).map(i => i.id).join('\n'),
                                placeholder: 'One product id per line, in display order'});
    slug.id = `col-slug-${c?.slug ?? 'new'}`; title.id = `col-title-${c?.slug ?? 'new'}`; ids.id = `col-ids-${c?.slug ?? 'new'}`;
    const form = el('form', {className: 'collection-editor'}, field('Slug', slug), field('Title', title), field('Products', ids),
                    el('button', {type: 'submit', text: c ? 'Save collection' : 'Create collection', className: 'primary'}),
                    c ? button('Delete collection', b => act(b, async () => {
                      await api.call('DELETE', `/admin/catalogue/collections/${c.slug}`);
                      await staffCollectionsPage();
                      return `Deleted ${c.slug}.`;
                    }), 'danger') : '');
    form.addEventListener('submit', e => {
      e.preventDefault();
      act(form.querySelector('button[type=submit]') as HTMLButtonElement, async () => {
        await api.call('PUT', `/admin/catalogue/collections/${encodeURIComponent(slug.value.trim())}`, {body: {
          title: title.value, product_ids: ids.value.split(/\s+/).filter(Boolean)}});
        await staffCollectionsPage();
        return `Saved ${slug.value.trim()}.`;
      });
    });
    const members = c ? el('ul', {className: 'list'}, ...c.items.map(i => el('li', {text: `${i.name ?? i.id} (${i.publication_state})`}))) : '';
    return el('section', {}, el('h2', {text: c ? c.title : 'New collection'}), members, form);
  };
  view('Collections', staffNav(), ...cols.map(c => editor(c)), editor());
}
