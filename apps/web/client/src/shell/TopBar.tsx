import {useEffect, useRef, useState} from 'react';
import {NavLink, useNavigate} from 'react-router';
import {Bell, Heart, Menu, Monitor, Rss, Search, ShoppingBag, Tv, UserRound} from 'lucide-react';
import * as m from 'motion/react-m';
import {AnimatePresence} from 'motion/react';
import {useSession} from '../session/SessionProvider.tsx';
import {useSettings} from '../settings/SettingsProvider.tsx';
import {useI18n} from '../i18n/index.tsx';
import {useCounts} from '../data/queries.ts';
import {IconButton, Button} from '../components/ui.tsx';
import {dur, easeOut} from '../motion/tokens.ts';

export const primaryNav = [
  {to: '/', key: 'nav.home'}, {to: '/catalogue', key: 'nav.catalogue'}, {to: '/wardrobe', key: 'nav.wardrobe'},
  {to: '/community', key: 'nav.community'}, {to: '/profile', key: 'nav.profile'},
] as const;

function Clock() {
  const {time} = useI18n();
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 15_000); return () => clearInterval(id); }, []);
  return <time className="clock" dateTime={now.toISOString()}>{time(now)}</time>;
}

export function Logo() {
  const {resolvedTheme} = useSettings();
  // Light theme: the plum lockup. Dark themes: the owner-supplied white lockup (different proportions).
  const light = resolvedTheme === 'light';
  return <img className="logo" src={`${import.meta.env.BASE_URL}brand/wordmark-${light ? 'plum' : 'white'}.png`}
    alt="Wearhouse" width={560} height={light ? 181 : 139} />;
}

function AccountMenu() {
  const {t} = useI18n();
  const {me, isStaff, signOut} = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); root.current?.querySelector('button')?.focus(); } };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', esc); };
  }, [open]);
  const go = (to: string) => { setOpen(false); navigate(to); };
  const items: Array<[string, string]> = [['/profile', t('nav.profile')], ['/redeem', t('nav.redeem')], ['/orders', t('nav.orders')],
    ['/settings', t('nav.settings')], ['/about', t('nav.about')]];
  if (isStaff) items.push(['/admin', t('nav.staff')]);
  return <div className="account" ref={root}>
    <button type="button" className="avatar-btn" aria-haspopup="menu" aria-expanded={open} aria-label={t('nav.account')} onClick={() => setOpen(o => !o)}>
      <UserRound size={20} aria-hidden /><span className="avatar-handle">{me?.handle ? `@${me.handle}` : ''}</span>
    </button>
    <AnimatePresence>
      {open && <m.div role="menu" className="menu" initial={{opacity: 0, y: -6}} animate={{opacity: 1, y: 0}}
        exit={{opacity: 0, y: -4}} transition={{duration: dur.d2, ease: easeOut}}>
        {items.map(([to, label]) => <button type="button" key={to} role="menuitem" onClick={() => go(to)}>{label}</button>)}
        <hr />
        <button type="button" role="menuitem" onClick={async () => { setOpen(false); await signOut(); navigate('/'); }}>{t('nav.signOut')}</button>
      </m.div>}
    </AnimatePresence>
  </div>;
}

export function TopBar({onMenu, onQuick}: {onMenu: () => void; onQuick: () => void}) {
  const {t} = useI18n();
  const {status} = useSession();
  const {presentation, setPresentation} = useSettings();
  const counts = useCounts();
  const navigate = useNavigate();
  const signedIn = status === 'ready';
  const hasSession = signedIn || status === 'onboarding';
  return <header className="topbar">
    <div className="topbar-start">
      <IconButton label={`${t('nav.mainMenu')} (M)`} onClick={onMenu} className="menu-btn"><Menu size={22} /></IconButton>
      <NavLink to="/" className="logo-link" aria-label="Wearhouse"><Logo /></NavLink>
    </div>
    <nav className="topnav" aria-label={t('nav.primary')}>
      {primaryNav.map(n => <NavLink key={n.to} to={n.to} end={n.to === '/'} className="topnav-link">{t(n.key)}</NavLink>)}
    </nav>
    <div className="topbar-end">
      <IconButton label={`${t('nav.search')} (/)`} onClick={() => navigate('/catalogue/browse')}><Search size={20} /></IconButton>
      {signedIn && <>
        <IconButton label={t('nav.wishlist')} badge={counts.wishlist} onClick={() => navigate('/wishlist')} className="hide-sm"><Heart size={20} /></IconButton>
        <IconButton label={t('nav.cart')} badge={counts.cart} onClick={() => navigate('/cart')} className="hide-sm"><ShoppingBag size={20} /></IconButton>
        <IconButton label={`${t('nav.notifications')} (Q)`} badge={counts.unread} onClick={onQuick}>
          <Bell size={20} className={counts.unread ? 'bell-ring' : undefined} /></IconButton>
        <IconButton label={t('nav.feed')} onClick={() => navigate('/community')} className="hide-sm"><Rss size={20} /></IconButton>
      </>}
      <Clock />
      <IconButton label={presentation === 'focus' ? t('presentation.toDesktop') : t('presentation.toFocus')} className="hide-sm"
        onClick={() => setPresentation(presentation === 'focus' ? 'desktop' : 'focus')}>
        {presentation === 'focus' ? <Monitor size={20} /> : <Tv size={20} />}</IconButton>
      {hasSession ? <AccountMenu /> : status !== 'loading' &&
        <Button variant="primary" onClick={() => navigate('/signin')}>{t('nav.signIn')}</Button>}
    </div>
  </header>;
}
