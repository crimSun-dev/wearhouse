import {useEffect, useRef, useState, type FormEvent} from 'react';
import {Link} from 'react-router';
import {useQueryClient} from '@tanstack/react-query';
import {Unlock} from 'lucide-react';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure, createIntent} from '../../api/index.ts';
import {Button} from '../../components/ui.tsx';
import {consumeKey, keyFrom, normaliseKey, peekKey} from './parts.tsx';
import {QrScanner} from '../../components/QrScanner.tsx';
import {useSettings} from '../../settings/SettingsProvider.tsx';
import {flyTo} from '../../motion/fly.ts';
import './store.css';

type Owned = {id: string; public_serial: string; product: {id: string; name: string}};

export function RedeemRoute() {
  const {t} = useI18n();
  const {api, userKey} = useSession();
  const {reducedMotion} = useSettings();
  const garment = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const [raw, setRaw] = useState(() => peekKey() ?? '');
  useEffect(() => consumeKey(), []);
  const [error, setError] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Owned | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);
  // A scanned QR fills the field; the user still checks and submits. Public tag links are explained, never redeemed.
  const onScan = (raw: string) => {
    if (/#\/items\//.test(raw)) { setScanNote(t('red.tagNotKey')); return true; }
    const key = keyFrom(raw);
    if (!key) { setScanNote(t('red.noKeyInQr')); return true; }
    setRaw(key); setError(null); setScanNote(t('red.scanned')); return true;
  };
  const intent = useRef(createIntent());
  const {clean, display} = normaliseKey(raw);
  useEffect(() => {
    if (wait <= 0) return;
    const timer = setTimeout(() => setWait(w => w - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (clean.length !== 16 || wait > 0) { if (clean.length !== 16) setError(t('red.invalid')); return; }
    setBusy(true); setError(null);
    try {
      const item = await api.call('post', '/api/v2/redemptions', {body: {activation_key: display}, intent: intent.current});
      setDone(item); setRaw('');
      intent.current = createIntent();
      // The unit is now claimed: owned items, the wardrobe and any cached receipt must refetch.
      for (const k of ['owned-items', 'wardrobe-items', 'order', 'orders']) void qc.invalidateQueries({queryKey: [...userKey, k]});
    } catch (err) {
      if (err instanceof ApiFailure && err.status === 429) { setWait(err.retryAfter ?? 60); setError(null); }
      else if (err instanceof ApiFailure && err.status < 500) setError(t('red.invalid'));   // one generic message for every invalid key
      else setError(t('common.offline'));
    } finally { setBusy(false); }
  };
  // Signature moment (web-motion 1), only after the server confirmed the claim: the four key groups lock in (masked,
  // so no key stays in the page), the card becomes the garment, and the garment flies into the Wardrobe navigation.
  if (done) return <div className="page store redeem">
    <section className="redeem-done" aria-live="polite">
      <ol className="redeem-groups" aria-hidden>{[0, 1, 2, 3].map(i => <li key={i} style={{'--i': i} as never}>••••</li>)}</ol>
      <div className="redeem-garment" ref={garment}
        onAnimationEnd={e => { if (e.target === garment.current && !reducedMotion) flyTo(garment.current!, ['.topnav a[href$="#/wardrobe"]', '.bottomnav-link[href$="#/wardrobe"]', '.menu-btn']); }}>
        <span className="redeem-unlock" aria-hidden><Unlock size={40} /></span>
        <div><h1>{t('red.success', {name: done.product.name})}</h1>
          <p className="muted">{t('red.serial', {serial: done.public_serial})}</p></div>
      </div>
      <div className="buy-actions">
        <Link className="btn btn-primary btn-lg" to={`/items/${done.public_serial}`}>{t('red.view')}</Link>
        <Button size="lg" onClick={() => setDone(null)}>{t('red.another')}</Button>
      </div>
    </section>
  </div>;
  return <div className="page store redeem">
    <header className="store-head"><div><h1>{t('red.title')}</h1><p className="muted">{t('red.body')}</p></div></header>
    <form className="redeem-form" onSubmit={e => void submit(e)}>
      <label className="field">
        <span className="field-label">{t('red.key')}</span>
        <input className="redeem-input" value={display} onChange={e => { setRaw(e.target.value); setError(null); }}
          autoComplete="off" autoCapitalize="characters" spellCheck={false} inputMode="text" maxLength={24}
          placeholder="XXXX-XXXX-XXXX-XXXX" aria-invalid={!!error || undefined} aria-describedby="redeem-msg" />
      </label>
      <p id="redeem-msg" className={error ? 'form-error' : 'muted small'} role={error || wait ? 'alert' : undefined}>
        {wait > 0 ? t('red.wait', {s: wait}) : error ?? ''}</p>
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={wait > 0 || clean.length !== 16}>{t('red.submit')}</Button>
    </form>
    <section className="store-section redeem-scan">
      <QrScanner onCode={onScan} label={t('red.scan')} />
      {scanNote && <p className="muted" role="status" data-testid="scan-note">{scanNote}</p>}
    </section>
  </div>;
}
