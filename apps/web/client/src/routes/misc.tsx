import {useState} from 'react';
import {Link} from 'react-router';
import {Heart, Sparkles} from 'lucide-react';
import {useI18n} from '../i18n/index.tsx';
import {Button, Chip, IconButton, Segmented, Select, Skeleton, Slider, Stepper, Tabs, TextField, Toggle} from '../components/ui.tsx';
import {Rail} from '../components/Rail.tsx';
import {Tile} from '../components/tiles.tsx';
import {ModelLabel, SimulatedLabel, WeatherChip} from '../components/labels.tsx';
import {Silhouette} from '../components/Silhouette.tsx';
import {toast} from '../components/toast.tsx';
import {FocusZone} from '../focus/FocusZone.tsx';
import './pages.css';


export function NotFoundRoute() {
  const {t} = useI18n();
  return <section className="page"><h1>{t('common.notFound')}</h1><Link to="/">{t('common.goHome')}</Link></section>;
}

/** #/dev/kit: every component and state, for review at 360 and 1440 px in both themes. */
export function DevKitRoute() {
  const {t} = useI18n();
  const [toggle, setToggle] = useState(true);
  const [seg, setSeg] = useState<'grid' | 'list' | 'outfit'>('grid');
  const [tab, setTab] = useState<'a' | 'b' | 'c'>('a');
  const [qty, setQty] = useState(1);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const slots = ['top', 'bottom', 'dress', 'outer', 'footwear', 'bag', 'headwear', 'eyewear', 'accessory'];
  return <div className="page kit">
    <h1>{t('kit.title')}</h1>
    <section><h2>Buttons</h2><div className="kit-row">
      <Button variant="primary">Primary</Button><Button>Secondary</Button><Button variant="ghost">Ghost</Button>
      <Button variant="danger">Delete look</Button><Button disabled>Disabled</Button>
      <Button variant="primary" loading={loading} success={done} data-testid="kit-loading"
        onClick={() => { setLoading(true); setTimeout(() => { setLoading(false); setDone(true); setTimeout(() => setDone(false), 1200); }, 1200); }}>
        Wear today</Button>
      <Button variant="primary" size="lg" icon={<Sparkles size={18} />}>Get today’s suggestions</Button>
      <IconButton label="Wishlist" badge={3}><Heart size={20} /></IconButton>
    </div></section>
    <section><h2>Chips, toggle, segmented, tabs</h2><div className="kit-row">
      <Chip selected>All</Chip><Chip>Tops</Chip><Chip>Bottoms</Chip>
      <Segmented label="View" value={seg} onChange={setSeg} options={[{value: 'grid', label: 'Grid'}, {value: 'list', label: 'List'}, {value: 'outfit', label: 'Outfit'}]} />
    </div>
      <div className="kit-col"><Toggle label="Outfit suggestions" description="Uses your wardrobe, the occasion and BMKG weather." checked={toggle} onChange={setToggle} /></div>
      <Tabs label="Kit tabs" value={tab} onChange={setTab} tabs={[{value: 'a', label: 'Recently added'}, {value: 'b', label: 'Friends', count: 2}, {value: 'c', label: 'For you'}]} />
    </section>
    <section><h2>Fields</h2><div className="kit-grid">
      <TextField label="Handle" hint="3–30 letters, numbers or underscores." defaultValue="sekar_w" />
      <TextField label="Activation key" error="That key can’t be redeemed. Check it and try again." defaultValue="WEAR-HOUS-EXAM-PLE2" />
      <Select label="Occasion" defaultValue="campus"><option value="casual">Casual</option><option value="campus">Campus</option><option value="worship">Worship</option></Select>
      <Slider label="Sound volume" value={60} min={0} max={100} onCommit={() => undefined} />
      <Stepper label="Quantity" value={qty} min={1} max={5} onChange={setQty} />
      <Button onClick={() => toast('Saved to your wardrobe', 'success')}>Show a toast</Button>
    </div></section>
    <section><h2>Labels</h2><div className="kit-row">
      <SimulatedLabel /><ModelLabel mode="heuristic_baseline" /><span className="tag tag-ok">Ready</span><span className="tag tag-warn">In laundry</span>
      <WeatherChip source="LIVE" temp={31} rain hot={false} fetchedAt={new Date().toISOString()} />
      <WeatherChip source="MANUAL_REQUIRED" />
    </div></section>
    <Rail title="Tiles and silhouettes" version={slots.length}>
      {slots.map(s => <Tile key={s} href="#/dev/kit" title={`${s} (no image)`} meta="Declared · Not worn yet" ratio="portrait" slot={s}
        descriptor={{id: `kit:${s}`, actions: [{key: 'Enter', label: 'Inspect'}]}} />)}
    </Rail>
    <section><h2>Grid (arrow keys)</h2>
      <FocusZone kind="grid" label="Kit grid" className="kit-tiles">
        {slots.map(s => <Tile key={s} href="#/dev/kit" title={s} ratio="portrait" slot={s} descriptor={{id: `grid:${s}`}} />)}
      </FocusZone></section>
    <section><h2>Skeletons</h2><div className="kit-tiles"><Skeleton /><Skeleton /><Skeleton /><Silhouette slot="dress" label="Image unavailable" /></div></section>
  </div>;
}
