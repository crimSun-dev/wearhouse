import {NavLink} from 'react-router';
import {useI18n} from '../../i18n/index.tsx';
import {ApiFailure} from '../../api/index.ts';
import {toast} from '../../components/toast.tsx';
import {Tile, accentFor} from '../../components/tiles.tsx';
import {ItemImage} from '../../components/ItemImage.tsx';
import type {MessageKey} from '../../i18n/en.ts';
import type {Item} from '../../data/wardrobe.ts';
// Store layout primitives (filters bar, bag lines, alerts, confirm dialogs) are shared with the wardrobe.
import '../store/store.css';
import './wardrobe.css';

const SECTIONS: Array<[string, MessageKey]> = [
  ['/wardrobe', 'wr.nav.library'], ['/wardrobe/looks', 'wr.nav.looks'], ['/wardrobe/fitting-room', 'wr.nav.fitting'],
  ['/wardrobe/suggestions', 'wr.nav.suggest'], ['/wardrobe/planner', 'wr.nav.planner'], ['/wardrobe/wear', 'wr.nav.wear'],
  ['/weather', 'wr.nav.weather'], ['/sizes', 'wr.nav.sizes'],
];

/** The wardrobe's section bar (Steam Library style tabs). */
export function WardrobeNav() {
  const {t} = useI18n();
  return <nav className="wr-nav" aria-label={t('wr.title')}>
    {SECTIONS.map(([to, key]) => <NavLink key={to} to={to} end={to === '/wardrobe'} className={({isActive}) => `wr-nav-link ${isActive ? 'is-active' : ''}`}>
      {t(key)}</NavLink>)}
  </nav>;
}

export function useLabels() {
  const {t} = useI18n();
  const safe = (key: string, fallback: string) => { const v = t(key as MessageKey); return v === key ? fallback : v; };
  return {
    slot: (s: string | null | undefined) => (s ? safe(`wslot.${s}`, s) : t('wslot.unknown')),
    care: (c: string) => safe(`care.${c}`, c),
    source: (s: string | null | undefined) => (s ? safe(`src.${s}`, s) : ''),
    attr: (a: string) => safe(`attr.${a}`, a.replace(/_/g, ' ')),
    occasion: (o: string | null | undefined) => (o ? safe(`occ.${o}`, o) : t('occ.none')),
  };
}

export function useFail() {
  const {t, errorText} = useI18n();
  return (e: unknown) => toast(e instanceof ApiFailure ? errorText(e.code, e.message) : t('common.offline'), 'error');
}

export function itemTitle(item: Item) { return item.name ?? item.category ?? item.slot; }

export function ItemTile({item, onOpen}: {item: Item; onOpen?: () => void}) {
  const {t, date} = useI18n();
  const labels = useLabels();
  const state = item.care_state !== 'ready' ? labels.care(item.care_state) : item.verified ? t('wr.verified') : t('wr.declared');
  const meta = `${labels.slot(item.slot_source === 'unknown' ? null : item.slot)} · ${state}`;
  const detail = item.wear_count ? t('wr.worn', {n: item.wear_count}) + (item.last_worn_on ? ` · ${t('wr.lastWorn', {date: date(item.last_worn_on)})}` : '') : t('wr.neverWorn');
  return <div className={`wr-tile ${item.archived ? 'is-archived' : ''}`} onClickCapture={onOpen ? e => { e.preventDefault(); onOpen(); } : undefined}>
    <Tile href={`#/wardrobe/items/${item.id}`} title={itemTitle(item)} meta={meta} ratio="portrait"
      badges={<>{item.verified && <span className="tag tag-ok">{t('wr.verified')}</span>}{item.archived && <span className="tag tag-quiet">{t('wr.archived')}</span>}</>}
      descriptor={{id: `item:${item.id}`, meta: `${meta} · ${detail}`, accent: accentFor(item.colour), actions: [{key: 'Enter', label: t('home.inspect')}]}}>
      <ItemImage item={item} />
    </Tile>
  </div>;
}

export const ALL_SLOTS = ['top', 'outer', 'bottom', 'dress', 'footwear', 'bag', 'headwear', 'eyewear', 'earrings', 'necklace', 'tie',
  'scarf', 'belt', 'wrist', 'ring', 'accessory'] as const;
