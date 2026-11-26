import {useState, type FormEvent} from 'react';
import {Link, useNavigate, useSearchParams} from 'react-router';
import {useSession} from '../session/SessionProvider.tsx';
import {useI18n} from '../i18n/index.tsx';
import {Button, TextField} from '../components/ui.tsx';
import {AuthFailure} from '../auth/port.ts';
import {checkPassword} from '../auth/password.ts';
import {Logo} from '../shell/TopBar.tsx';
import './pages.css';

function useBroker() {
  const {auth, refresh} = useSession();
  const {t} = useI18n();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<void>, after?: () => void) => {
    if (!auth) { setError(t('auth.unavailable')); return; }
    setBusy(true); setError(null);
    try { await fn(); await refresh(); after ? after() : navigate('/'); }
    catch (e) { setError(e instanceof AuthFailure ? e.message : t('auth.unavailable')); }
    finally { setBusy(false); }
  };
  return {auth, busy, error, run};
}

function Card({title, children}: {title: string; children: React.ReactNode}) {
  return <section className="auth-card"><Logo /><h1>{title}</h1>{children}</section>;
}

export function SignInRoute() {
  const {t} = useI18n();
  const {auth, busy, error, run} = useBroker();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const submit = (e: FormEvent) => { e.preventDefault(); void run(() => auth!.signInWithEmail(email, password)); };
  return <div className="page page-auth"><Card title={t('auth.title')}>
    <Button variant="primary" size="lg" loading={busy} onClick={() => run(() => auth!.signInWithGoogle())}>{t('auth.google')}</Button>
    <p className="auth-or"><span>{t('auth.or')}</span></p>
    <form onSubmit={submit} className="auth-form">
      <TextField label={t('auth.email')} type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
      <TextField label={t('auth.password')} type="password" autoComplete="current-password" required value={password}
        onChange={e => setPassword(e.target.value)} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button type="submit" size="lg" loading={busy}>{t('auth.signIn')}</Button>
    </form>
    <p className="auth-links"><Link to="/reset">{t('auth.forgot')}</Link> · {t('auth.noAccount')} <Link to="/signup">{t('auth.signUp')}</Link></p>
    <p className="muted small">{t('auth.brokerNote')}</p>
  </Card></div>;
}

export function SignUpRoute() {
  const {t} = useI18n();
  const {auth, busy, error, run} = useBroker();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const check = checkPassword(password, {email});
  const submit = (e: FormEvent) => { e.preventDefault(); if (check.ok) void run(() => auth!.signUpWithEmail(name, email, password)); };
  return <div className="page page-auth"><Card title={t('auth.signUpTitle')}>
    <form onSubmit={submit} className="auth-form">
      <TextField label={t('auth.name')} autoComplete="name" required value={name} onChange={e => setName(e.target.value)} />
      <TextField label={t('auth.email')} type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
      <TextField label={t('auth.password')} type="password" autoComplete="new-password" required value={password}
        onChange={e => setPassword(e.target.value)} error={password && !check.ok ? check.problems[0] : undefined}
        hint={password && check.ok ? check.strength : undefined} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!check.ok}>{t('auth.signUp')}</Button>
    </form>
    <p className="auth-links">{t('auth.haveAccount')} <Link to="/signin">{t('auth.signIn')}</Link></p>
    <p className="muted small">{t('auth.brokerNote')}</p>
  </Card></div>;
}

export function ResetRoute() {
  const {t} = useI18n();
  const {auth, busy, error, run} = useBroker();
  const [params] = useSearchParams();
  const token = params.get('token');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [done, setDone] = useState<string | null>(null);
  const check = checkPassword(password);
  if (!token) return <div className="page page-auth"><Card title={t('auth.resetTitle')}>
    {done ? <p role="status">{done}</p> : <form className="auth-form" onSubmit={e => { e.preventDefault();
      void run(() => auth!.requestPasswordReset(email), () => setDone(t('auth.resetSent'))); }}>
      <TextField label={t('auth.email')} type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button type="submit" variant="primary" size="lg" loading={busy}>{t('auth.sendReset')}</Button>
    </form>}
    <p className="auth-links"><Link to="/signin">{t('auth.signIn')}</Link></p>
  </Card></div>;
  return <div className="page page-auth"><Card title={t('auth.resetTitle')}>
    {done ? <><p role="status">{done}</p><Link to="/signin">{t('auth.signIn')}</Link></> : <form className="auth-form" onSubmit={e => {
      e.preventDefault(); if (check.ok) void run(() => auth!.resetPassword(token, password), () => setDone(t('auth.passwordSet'))); }}>
      <TextField label={t('auth.newPassword')} type="password" autoComplete="new-password" required value={password}
        onChange={e => setPassword(e.target.value)} error={password && !check.ok ? check.problems[0] : undefined} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={!check.ok}>{t('auth.setPassword')}</Button>
    </form>}
  </Card></div>;
}
