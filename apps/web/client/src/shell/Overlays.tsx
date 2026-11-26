import {useNavigate} from 'react-router';
import {Home, Shirt, Store, Users, UserRound, Settings, LogOut, LogIn, Info} from 'lucide-react';
import {useQuery, useMutation, useQueryClient} from '@tanstack/react-query';
import {Overlay} from '../components/Overlay.tsx';
import {FocusZone} from '../focus/FocusZone.tsx';
import {useI18n} from '../i18n/index.tsx';
import {useSession} from '../session/SessionProvider.tsx';
import {useSettings} from '../settings/SettingsProvider.tsx';
import {useMyWeather} from '../data/queries.ts';
import {Segmented, Toggle, Button} from '../components/ui.tsx';
import {WeatherChip} from '../components/labels.tsx';
import type {MessageKey} from '../i18n/en.ts';

export function MainMenu({open, onClose}: {open: boolean; onClose: () => void}) {
  const {t} = useI18n();
  const {status, signOut} = useSession();
  const navigate = useNavigate();
  const go = (to: string) => { onClose(); navigate(to); };
  const entries: Array<[string, string, typeof Home]> = [['/', t('nav.home'), Home], ['/catalogue', t('nav.catalogue'), Store],
    ['/wardrobe', t('nav.wardrobe'), Shirt], ['/community', t('nav.community'), Users], ['/profile', t('nav.profile'), UserRound],
    ['/settings', t('nav.settings'), Settings], ['/about', t('nav.about'), Info]];
  return <Overlay open={open} onClose={onClose} side="left" title={t('nav.mainMenu')}>
    <FocusZone kind="grid" label={t('nav.mainMenu')} className="menu-list">
      {entries.map(([to, label, Icon], i) => <button type="button" key={to} data-focus-item data-autofocus={i === 0 || undefined} className="menu-entry" onClick={() => go(to)}>
        <Icon size={22} aria-hidden />{label}</button>)}
      {status === 'ready'
        ? <button type="button" data-focus-item className="menu-entry" onClick={async () => { onClose(); await signOut(); navigate('/'); }}>
            <LogOut size={22} aria-hidden />{t('nav.signOut')}</button>
        : <button type="button" data-focus-item className="menu-entry" onClick={() => go('/signin')}><LogIn size={22} aria-hidden />{t('nav.signIn')}</button>}
    </FocusZone>
  </Overlay>;
}

export function QuickAccess({open, onClose}: {open: boolean; onClose: () => void}) {
  const {t, date} = useI18n();
  const {api, userKey, status} = useSession();
  const {values, update} = useSettings();
  const navigate = useNavigate();
  const client = useQueryClient();
  const signedIn = status === 'ready';
  const notes = useQuery({queryKey: [...userKey, 'notifications'], enabled: open && signedIn,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/notifications', {signal})});
  const requests = useQuery({queryKey: [...userKey, 'requests', 'incoming'], enabled: open && signedIn,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/friend-requests', {signal, query: {direction: 'incoming', limit: 5}})});
  const weather = useMyWeather();
  const markRead = useMutation({mutationFn: () => api.call('post', '/api/v2/me/notifications/read', {}),
    onSuccess: () => client.invalidateQueries({queryKey: [...userKey, 'unread']})});
  const unread = notes.data?.items.filter(n => n.unread) ?? [];
  const slot = weather.data?.slots[0];
  return <Overlay open={open} onClose={onClose} side="right" title={t('nav.quickAccess')}>
    {signedIn && <section className="qa-section">
      <h3 className="caps">{t('quick.weather')}</h3>
      {weather.data?.note === 'no_location' ? <p className="muted">{t('weather.noLocation')}</p>
        : <WeatherChip source={weather.data?.source ?? 'NONE'} temp={slot?.temp_c} rain={slot?.rain} hot={slot?.hot} fetchedAt={weather.data?.fetched_at} />}
    </section>}
    {signedIn && <section className="qa-section">
      <h3 className="caps">{t('nav.notifications')}</h3>
      {unread.length === 0 ? <p className="muted">{t('quick.noNotifications')}</p> : <ul className="qa-list">
        {unread.slice(0, 5).map(n => <li key={n.ref + n.at}><b>{n.account.display_name}</b> {t(`notif.${n.kind}` as MessageKey)}
          <small>{date(n.at, {day: 'numeric', month: 'short'})}</small></li>)}</ul>}
      <div className="qa-row">
        {unread.length > 0 && <Button variant="ghost" loading={markRead.isPending} onClick={() => markRead.mutate()}>{t('quick.markRead')}</Button>}
        <Button variant="ghost" onClick={() => { onClose(); navigate('/notifications'); }}>{t('quick.allNotifications')}</Button>
      </div>
      {!!requests.data?.requests.length && <p>{t('quick.requests')}: <b>{requests.data.requests.length}</b></p>}
    </section>}
    <section className="qa-section">
      <h3 className="caps">{t('quick.theme')}</h3>
      <Segmented label={t('quick.theme')} value={String(values.theme ?? 'system') as 'dark' | 'light' | 'system'}
        onChange={v => void update({theme: v})}
        options={[{value: 'dark', label: t('theme.dark')}, {value: 'light', label: t('theme.light')}, {value: 'system', label: t('theme.system')}]} />
      <Toggle label={t('quick.reduceMotion')} checked={values.reduce_motion === true} onChange={v => void update({reduce_motion: v})} />
      <Toggle label={t('quick.sound')} checked={values.sound_effects === true} onChange={v => void update({sound_effects: v})} />
    </section>
  </Overlay>;
}
