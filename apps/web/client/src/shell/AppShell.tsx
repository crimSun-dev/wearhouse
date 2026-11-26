import {useEffect, useState} from 'react';
import {NavLink, Outlet, useLocation, useNavigate} from 'react-router';
import {Home, Shirt, Store, Users, UserRound} from 'lucide-react';
import {onIntent, publishFocus} from '../focus/store.ts';
import {useSettings} from '../settings/SettingsProvider.tsx';
import {useI18n} from '../i18n/index.tsx';
import {Toaster} from '../components/toast.tsx';
import {TopBar} from './TopBar.tsx';
import {MainMenu, QuickAccess} from './Overlays.tsx';
import {HintBar} from './HintBar.tsx';
import {Backdrop} from './Backdrop.tsx';
import './shell.css';

function BottomNav() {
  const {t} = useI18n();
  const items = [['/', t('nav.home'), Home], ['/catalogue', t('nav.catalogue'), Store], ['/wardrobe', t('nav.wardrobe'), Shirt],
    ['/community', t('nav.community'), Users], ['/profile', t('nav.profile'), UserRound]] as const;
  return <nav className="bottomnav" aria-label={t('nav.primary')}>
    {items.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === '/'} className="bottomnav-link">
      <Icon size={22} aria-hidden /><span>{label}</span></NavLink>)}
  </nav>;
}

export function AppShell() {
  const {t} = useI18n();
  const {presentation} = useSettings();
  const [menu, setMenu] = useState(false);
  const [quick, setQuick] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => onIntent(intent => {
    if (intent === 'menu') setMenu(true);
    else if (intent === 'quick') setQuick(true);
    else if (intent === 'search') navigate('/catalogue?all=1', {state: {search: true}});
    else if (intent === 'back' && location.pathname !== '/') navigate(-1);
  }), [navigate, location.pathname]);
  useEffect(() => { publishFocus(null); }, [location.pathname]);

  return <div className={`shell shell-${presentation}`}>
    <a className="skip-link" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus(); }}>{t('nav.skip')}</a>
    {presentation === 'focus' && <Backdrop />}
    <TopBar onMenu={() => setMenu(true)} onQuick={() => setQuick(true)} />
    <main id="main" tabIndex={-1} className="main"><Outlet /></main>
    {presentation === 'focus' && <HintBar onMenu={() => setMenu(true)} />}
    <BottomNav />
    <MainMenu open={menu} onClose={() => setMenu(false)} />
    <QuickAccess open={quick} onClose={() => setQuick(false)} />
    <Toaster />
  </div>;
}
