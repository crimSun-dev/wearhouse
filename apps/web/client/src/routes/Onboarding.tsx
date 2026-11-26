import {useState, type FormEvent} from 'react';
import {useNavigate} from 'react-router';
import {useSession} from '../session/SessionProvider.tsx';
import {useSettings} from '../settings/SettingsProvider.tsx';
import {useI18n, type Lang} from '../i18n/index.tsx';
import {ApiFailure} from '../api/index.ts';
import {Button, Segmented, TextField} from '../components/ui.tsx';
import {Logo} from '../shell/TopBar.tsx';
import './pages.css';

// Data, not styling: the server's six avatar presets and the swatch each one shows.
const PRESETS = [['plum', '#632947'], ['ivory', '#f4ead9'], ['blush', '#f1c9d6'], ['noir', '#2b1624'], ['sage', '#9fb59a'], ['sky', '#a9c4e0']] as const;

export function OnboardingRoute() {
  const {t, errorText, lang} = useI18n();
  const {api, broker, refresh} = useSession();
  const {setLanguage} = useSettings();
  const navigate = useNavigate();
  const [handle, setHandle] = useState('');
  const [name, setName] = useState(broker?.name ?? '');
  const [preset, setPreset] = useState<(typeof PRESETS)[number][0]>('plum');
  const [language, setLang] = useState<Lang>(lang);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErrors({}); setFormError(null);
    try {
      await api.call('patch', '/api/v2/me/profile', {body: {handle: handle.trim().replace(/^@/, ''), display_name: name.trim() || null,
        avatar: {kind: 'preset', preset}}});
      // Save the language the person is already seeing, so the account doesn't flip to English after sign-in.
      await setLanguage(language);
      await refresh();
      navigate('/');
    } catch (err) {
      if (err instanceof ApiFailure) {
        const byField: Record<string, string> = {};
        for (const f of err.fieldErrors as Array<{field: string; message: string}>) byField[f.field.split('.').pop()!] = f.message;
        if (err.code === 'HANDLE_UNAVAILABLE' || err.code === 'HANDLE_CHANGE_TOO_SOON') byField.handle = errorText(err.code);
        setErrors(byField);
        if (!Object.keys(byField).length) setFormError(errorText(err.code, err.message));
      } else setFormError(t('common.offline'));
    } finally { setBusy(false); }
  };

  return <div className="page page-auth"><section className="auth-card">
    <Logo /><h1>{t('onb.title')}</h1><p className="muted">{t('onb.body')}</p>
    <form className="auth-form" onSubmit={submit}>
      <TextField label={t('onb.handle')} required value={handle} onChange={e => setHandle(e.target.value)} autoComplete="username"
        hint={t('onb.handleHelp')} error={errors.handle} pattern="@?[A-Za-z0-9_]{3,30}" />
      <TextField label={t('onb.displayName')} value={name} onChange={e => setName(e.target.value)} error={errors.display_name} autoComplete="name" />
      <fieldset className="swatches"><legend className="field-label">{t('onb.avatar')}</legend>
        {PRESETS.map(([id, colour]) => <label key={id} className="swatch" style={{'--sw': colour} as never}>
          <input type="radio" name="avatar" value={id} checked={preset === id} onChange={() => setPreset(id)} />
          <span className="swatch-dot" aria-hidden /><span className="visually-hidden">{id}</span></label>)}
      </fieldset>
      <div className="field"><span className="field-label">{t('onb.language')}</span>
        <Segmented label={t('onb.language')} value={language} onChange={setLang}
          options={[{value: 'en', label: t('lang.en')}, {value: 'id', label: t('lang.id')}]} /></div>
      {formError && <p className="form-error" role="alert">{formError}</p>}
      <Button type="submit" variant="primary" size="lg" loading={busy}>{t('onb.finish')}</Button>
    </form>
  </section></div>;
}
