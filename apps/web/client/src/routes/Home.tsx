import {useEffect, useMemo, useState} from 'react';
import {useNavigate} from 'react-router';
import {CalendarDays, Shirt, Sparkles} from 'lucide-react';
import type {Schemas} from '@wearhouse/contracts';
import {likelySignedIn, useSession} from '../session/SessionProvider.tsx';
import {useSettings} from '../settings/SettingsProvider.tsx';
import {useI18n, TIME_ZONE} from '../i18n/index.tsx';
import {useCollections, useFeed, useForMe, useLooks, useMyWeather, useNewest, usePlanner, useWardrobeItems} from '../data/queries.ts';
import {Rail} from '../components/Rail.tsx';
import {Tile, accentFor} from '../components/tiles.tsx';
import {ItemImage} from '../components/ItemImage.tsx';
import {Media} from '../components/Media.tsx';
import {Button, Skeleton, Tabs} from '../components/ui.tsx';
import {ModelLabel, WeatherChip} from '../components/labels.tsx';
import {ErrorState, EmptyState} from '../components/states.tsx';
import {focusItemProps} from '../focus/FocusZone.tsx';
import {onIntent, type Descriptor} from '../focus/store.ts';
import {DetailZone} from '../shell/DetailZone.tsx';
import './home.css';

type Item = Schemas['WardrobeItemOut'];
type Look = Schemas['LookOut'];

function jakartaToday() {
  return new Intl.DateTimeFormat('en-CA', {timeZone: TIME_ZONE}).format(new Date());
}

function useTodayWeather() {
  const weather = useMyWeather();
  return useMemo(() => {
    const d = weather.data;
    if (!d) return {loading: weather.isPending, source: 'NONE', noLocation: false};
    const today = d.slots.filter(s => s.local_date === jakartaToday());
    const slots = today.length ? today : d.slots.slice(0, 4);
    return {
      loading: false, source: slots.length ? d.source : 'NONE', noLocation: d.note === 'no_location', fetchedAt: d.fetched_at,
      temp: slots.length ? Math.max(...slots.map(s => s.temp_c)) : null,
      rain: slots.length ? slots.some(s => s.rain) : null, hot: slots.length ? slots.some(s => s.hot) : null,
    };
  }, [weather.data, weather.isPending]);
}

/** What the Today card shows: the look planned for today, else the latest saved look, else nothing yet. */
type Featured = {kind: 'planned' | 'latest'; name: string; lookId: string | null; pieces: Item[]} | null;

function useTodayDescriptor(featured: Featured): Descriptor {
  const {t, date} = useI18n();
  const {values} = useSettings();
  const off = values.style_suggestions === false;
  const day = date(new Date(), {weekday: 'long', day: 'numeric', month: 'long'});
  const label = featured?.kind === 'planned' ? t('home.plannedToday') : featured ? t('home.latestLook') : t('home.nothingPlanned');
  const pieces = featured?.pieces.map(p => p.name ?? p.category ?? p.slot).join(', ');
  return {
    id: 'today', title: featured?.name ?? t('home.todayTitle'),
    meta: [`${label} · ${day}`, pieces || (off ? t('home.suggestionsOff') : t('home.todayBody'))].join('. '),
    accent: accentFor(featured?.pieces[0]?.colour) ?? 'var(--accent)',
    actions: [{key: 'Enter', label: featured ? t('home.openLook') : t('home.getSuggestions')}],
  };
}

function TodayTile({featured}: {featured: Featured}) {
  const {t} = useI18n();
  const {values} = useSettings();
  const w = useTodayWeather();
  const descriptor = useTodayDescriptor(featured);
  const off = values.style_suggestions === false;
  const href = featured?.lookId ? `#/wardrobe/looks/${featured.lookId}` : off ? '#/settings/style' : '#/wardrobe/suggestions';
  const label = featured?.kind === 'planned' ? t('home.plannedToday') : featured ? t('home.latestLook') : t('home.nothingPlanned');
  return <a href={href} className="tile tile-wide today-tile" aria-label={`${t('home.today')}: ${descriptor.title}`} {...focusItemProps(descriptor)}>
    <span className="tile-media today-media">
      {featured && <span className="today-outfit">{featured.pieces.slice(0, 4).map(p =>
        <span key={p.id}><ItemImage item={p} quiet /></span>)}</span>}
      <span className="today-info">
        <span className="today-label">{label}</span>
        {!featured && <span className="today-big" aria-hidden>{w.temp != null ? `${Math.round(w.temp)}°` : ''}</span>}
        {w.noLocation ? <span className="today-note">{t('weather.noLocation')}</span>
          : w.loading ? <Skeleton ratio="8 / 1" /> : <WeatherChip source={w.source} temp={w.temp} rain={w.rain} hot={w.hot} fetchedAt={w.fetchedAt} compact />}
      </span>
    </span>
  </a>;
}

function LookTile({look}: {look: Look}) {
  const {t} = useI18n();
  const pieces = look.current.items.filter(i => i.item);
  const first = pieces[0]?.item;
  const meta = `${t('home.lookPieces', {n: pieces.length})} · ${t('home.revision', {n: look.current_revision_no})}`;
  return <Tile href={`#/wardrobe/looks/${look.id}`} title={look.name} meta={meta} ratio="look"
    descriptor={{id: `look:${look.id}`, meta, accent: accentFor(first?.colour),
      actions: [{key: 'Enter', label: t('home.openLook')}]}}>
    <span className="collage">{pieces.slice(0, 4).map(p => <span key={p.item!.id}><ItemImage item={p.item!} quiet /></span>)}</span>
  </Tile>;
}

function ItemTile({item}: {item: Item}) {
  const {t} = useI18n();
  const state = item.care_state !== 'ready' ? t(`label.${item.care_state}`) : item.verified ? t('label.verified') : t('label.declared');
  const meta = `${state} · ${item.wear_count ? t('home.wearCount', {n: item.wear_count}) : t('home.neverWorn')}`;
  return <Tile href={`#/wardrobe/items/${item.id}`} title={item.name ?? item.category ?? item.slot} meta={meta} ratio="portrait"
    descriptor={{id: `item:${item.id}`, meta, accent: accentFor(item.colour), actions: [{key: 'Enter', label: t('home.inspect')}]}}>
    <ItemImage item={item} />
  </Tile>;
}

function ProductTile({p, meta}: {p: {id: string; name: string | null; thumbnail: string | null; slot: string | null; colour: string | null; category: string | null}; meta?: string}) {
  const {t} = useI18n();
  const title = p.name ?? p.category ?? '';
  return <Tile href={`#/catalogue/products/${p.id}`} title={title} meta={meta ?? p.category ?? undefined} ratio="portrait" image={p.thumbnail}
    slot={p.slot} descriptor={{id: `product:${p.id}`, meta: meta ?? p.category ?? undefined, image: p.thumbnail, accent: accentFor(p.colour),
      actions: [{key: 'Enter', label: t('home.viewProduct')}]}} />;
}

function RailSkeleton({ratio = '2 / 3', n = 6}: {ratio?: string; n?: number}) {
  return <div className="rail-skeleton">{Array.from({length: n}, (_, i) => <Skeleton key={i} ratio={ratio} />)}</div>;
}

function Discovery() {
  const {t} = useI18n();
  const collections = useCollections();
  const newest = useNewest();
  return <>
    {collections.isError ? <ErrorState error={collections.error} onRetry={() => collections.refetch()} />
      : !!collections.data?.length && <Rail title={t('home.featured')} version={collections.data.length}>
        {collections.data.map(c => <Tile key={c.slug} href={`#/collections/${c.slug}`} title={c.title}
          meta={t('home.lookPieces', {n: c.items.length})} ratio="wide" image={c.items[0]?.thumbnail} slot={c.items[0]?.slot}
          descriptor={{id: `collection:${c.slug}`, image: c.items[0]?.thumbnail, actions: [{key: 'Enter', label: t('hint.open')}]}} />)}
      </Rail>}
    {newest.isPending ? <RailSkeleton /> : newest.isError ? <ErrorState error={newest.error} onRetry={() => newest.refetch()} />
      : newest.data.items.length > 0 && <Rail title={t('home.newIn')} version={newest.data.items.length}>
        {newest.data.items.map(p => <ProductTile key={p.id} p={p} />)}
      </Rail>}
  </>;
}

function SignedOutHome() {
  const {t} = useI18n();
  const navigate = useNavigate();
  return <div className="home">
    <section className="home-hero">
      <h1>{t('home.signedOutTitle')}</h1>
      <p>{t('home.signedOutBody')}</p>
      <div className="home-hero-actions">
        <Button variant="primary" size="lg" onClick={() => navigate('/signin')}>{t('nav.signIn')}</Button>
        <Button size="lg" onClick={() => navigate('/catalogue')}>{t('home.browse')}</Button>
      </div>
    </section>
    <Discovery />
  </div>;
}

function EmptyWardrobeHome() {
  const {t} = useI18n();
  const navigate = useNavigate();
  return <div className="home">
    <section className="home-hero">
      <EmptyState title={t('home.emptyTitle')} body={t('home.emptyBody')}>
        <Button variant="primary" size="lg" onClick={() => navigate('/redeem')}>{t('home.redeem')}</Button>
        <Button size="lg" onClick={() => navigate('/wardrobe/add')}>{t('home.addGarment')}</Button>
        <Button size="lg" variant="ghost" onClick={() => navigate('/catalogue')}>{t('home.browse')}</Button>
      </EmptyState>
    </section>
    <Discovery />
  </div>;
}

type Tab = 'recent' | 'friends' | 'forYou';

function SignedInHome({items}: {items: Item[]}) {
  const {t} = useI18n();
  const navigate = useNavigate();
  const looks = useLooks();
  const feed = useFeed();
  const forMe = useForMe();
  const [tab, setTab] = useState<Tab>('recent');
  const order: Tab[] = ['recent', 'friends', 'forYou'];
  useEffect(() => onIntent(i => {
    if (i === 'tabNext' || i === 'tabPrev') setTab(cur => order[(order.indexOf(cur) + (i === 'tabNext' ? 1 : 2)) % 3]);
  }), []);  // eslint-disable-line react-hooks/exhaustive-deps

  const active = items.filter(i => !i.archived);
  const recent = [...active].sort((a, b) => (b.claimed_at ?? '').localeCompare(a.claimed_at ?? '')).slice(0, 14);
  const notWorn = [...active].filter(i => i.care_state === 'ready')
    .sort((a, b) => (a.last_worn_on ?? '0000').localeCompare(b.last_worn_on ?? '0000')).slice(0, 14);
  const recentLooks = (looks.data ?? []).filter(l => !l.deleted).slice(0, 8);
  const planner = usePlanner(jakartaToday());
  const todayPlan = planner.data?.days.find(d => d.is_today)?.plan;
  const pieces = (rev: Schemas['LookRevisionOut']) => rev.items.flatMap(i => i.item ? [i.item] : []);
  const featured: Featured = todayPlan
    ? {kind: 'planned', name: todayPlan.look_revision.name, lookId: todayPlan.look_revision.look_id, pieces: pieces(todayPlan.look_revision)}
    : recentLooks[0] ? {kind: 'latest', name: recentLooks[0].name, lookId: recentLooks[0].id, pieces: pieces(recentLooks[0].current)} : null;
  const fallback = useTodayDescriptor(featured);
  const {values} = useSettings();
  const suggestionsOff = values.style_suggestions === false;
  const suggest = <Button variant={featured?.kind === 'planned' ? 'ghost' : 'primary'} size="lg" icon={<Sparkles size={18} />}
    onClick={() => navigate(suggestionsOff ? '/settings/style' : '/wardrobe/suggestions')}>
    {suggestionsOff ? t('nav.settings') : t('home.getSuggestions')}</Button>;

  return <div className="home">
    {/* The first rail renders once looks are in too, so tiles never shift under the selection. */}
    {looks.isPending || planner.isPending ? <RailSkeleton ratio="16 / 9" n={3} /> :
    <Rail title={t('home.recentLooks')} size="lg" autoFocus version={`${recentLooks.length}-${recent.length}-${featured?.kind}`}>
      <TodayTile featured={featured} />
      {recentLooks.filter(l => l.id !== featured?.lookId).map(l => <LookTile key={l.id} look={l} />)}
      {recent.slice(0, 6).map(i => <ItemTile key={i.id} item={i} />)}
    </Rail>}
    <DetailZone fallback={fallback} actions={d => {
      const [kind, id] = d.id.split(':');
      if (kind === 'today') return featured?.kind === 'planned' ? <>
        <Button variant="primary" size="lg" onClick={() => navigate('/wardrobe/planner')}>{t('home.wearToday')}</Button>
        <Button size="lg" icon={<Shirt size={18} />} onClick={() => navigate(`/wardrobe/fitting-room?look=${featured.lookId}`)}>{t('home.tryOn')}</Button>
        {suggest}</> : <>
        {suggest}
        {featured && <Button size="lg" onClick={() => navigate(`/wardrobe/looks/${featured.lookId}`)}>{t('home.openLook')}</Button>}
        <Button size="lg" icon={<CalendarDays size={18} />} onClick={() => navigate('/wardrobe/planner')}>{t('hint.plan')}</Button></>;
      if (kind === 'look') return <>
        <Button variant="primary" size="lg" onClick={() => navigate(`/wardrobe/looks/${id}`)}>{t('home.openLook')}</Button>
        <Button size="lg" onClick={() => navigate('/wardrobe/planner')}>{t('home.planLook')}</Button></>;
      if (kind === 'item') return <Button variant="primary" size="lg" onClick={() => navigate(`/wardrobe/items/${id}`)}>{t('home.inspect')}</Button>;
      if (kind === 'product') return <Button variant="primary" size="lg" onClick={() => navigate(`/catalogue/products/${id}`)}>{t('home.viewProduct')}</Button>;
      return null;
    }} />
    <section className="home-tabs">
      <Tabs label={t('nav.home')} value={tab} onChange={setTab}
        tabs={[{value: 'recent', label: t('home.whatsNew')}, {value: 'friends', label: t('home.friends')}, {value: 'forYou', label: t('home.forYou')}]} />
    </section>
    {tab === 'recent' && <Rail title={t('home.recentlyAdded')} titleHidden version={recent.length}>{recent.map(i => <ItemTile key={i.id} item={i} />)}</Rail>}
    {tab === 'friends' && (feed.isPending ? <RailSkeleton ratio="3 / 4" /> : feed.isError ? <ErrorState error={feed.error} onRetry={() => feed.refetch()} />
      : feed.data.items.length === 0 ? <p className="home-empty-line">{t('home.noFriends')}</p>
      : <Rail title={t('home.friends')} titleHidden version={feed.data.items.length}>
        {feed.data.items.map(s => <Tile key={s.id} href={`#/shares/${s.id}`} title={s.look?.look_name ?? s.caption ?? ''}
          meta={`${s.owner?.display_name ?? ''}${s.caption ? ` · ${s.caption}` : ''}`} ratio="look"
          descriptor={{id: `share:${s.id}`, meta: s.owner?.display_name, actions: [{key: 'Enter', label: t('hint.open')}]}}>
          <span className="collage">{(s.look?.items ?? []).slice(0, 4).map((it, i) =>
            <span key={i}><Media src={null} alt="" slot={it.slot} quiet /></span>)}</span>
        </Tile>)}
      </Rail>)}
    {tab === 'forYou' && (forMe.isPending ? <RailSkeleton /> : forMe.isError ? <ErrorState error={forMe.error} onRetry={() => forMe.refetch()} />
      : <Rail title={t('home.forYou')} titleHidden version={forMe.data.items.length}
        note={<><ModelLabel mode={forMe.data.model.mode} /> {t('home.forYouNote')}</>}>
        {forMe.data.items.map(p => <ProductTile key={p.id} p={p} />)}
      </Rail>)}
    {notWorn.length > 0 && <Rail title={t('home.notWorn')} version={notWorn.length}>{notWorn.map(i => <ItemTile key={i.id} item={i} />)}</Rail>}
  </div>;
}

export function HomeRoute() {
  const {status} = useSession();
  const items = useWardrobeItems();
  // A device that never had a session sees the signed-out Home at once, not a placeholder, while the check runs.
  if (status === 'loading') return likelySignedIn() ? <div className="home"><RailSkeleton ratio="16 / 9" n={3} /></div> : <SignedOutHome />;
  if (status !== 'ready') return <SignedOutHome />;
  if (items.isPending) return <div className="home"><RailSkeleton ratio="16 / 9" n={3} /><RailSkeleton /></div>;
  if (items.isError) return <div className="home"><ErrorState error={items.error} onRetry={() => items.refetch()} /></div>;
  if (items.data.items.filter(i => !i.archived).length === 0) return <EmptyWardrobeHome />;
  return <SignedInHome items={items.data.items} />;
}
