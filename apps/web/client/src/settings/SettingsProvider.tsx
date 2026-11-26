import {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {LazyMotion, MotionConfig} from 'motion/react';

const motionFeatures = () => import('../motion/features.ts').then(r => r.default);
import type {Schemas} from '@wearhouse/contracts';
import {useSession} from '../session/SessionProvider.tsx';
import {I18nProvider, detectLanguage, rememberLanguage, type Lang} from '../i18n/index.tsx';
import {ApiFailure} from '../api/index.ts';
import {configureSound} from '../sound/uiSound.ts';
import {toast} from '../components/toast.tsx';
import {translate} from '../i18n/index.tsx';

type Values = Schemas['SettingsOut']['values'];
export type Presentation = 'focus' | 'desktop';
type ThemeChoice = 'dark' | 'light' | 'system';

type Settings = {
  values: Values;
  schema: Schemas['SettingsOut'] | null;
  lang: Lang;
  theme: ThemeChoice;
  resolvedTheme: 'dark' | 'light';
  reducedMotion: boolean;
  presentation: Presentation;
  setPresentation: (p: Presentation) => void;
  update: (values: Values) => Promise<void>;
  setLanguage: (lang: Lang) => Promise<void>;
};

const PRESENTATION_KEY = 'wearhouse.presentation';
const LOCAL_PREFS = 'wearhouse.localPrefs';
const Ctx = createContext<Settings | null>(null);

function readLocal<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) as T : fallback; } catch { return fallback; }
}
function writeLocal(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* not persisted */ }
}
function useMedia(query: string) {
  const [match, setMatch] = useState(() => typeof matchMedia !== 'undefined' && matchMedia(query).matches);
  useEffect(() => {
    const m = matchMedia(query);
    const on = () => setMatch(m.matches);
    m.addEventListener('change', on);
    return () => m.removeEventListener('change', on);
  }, [query]);
  return match;
}

export function SettingsProvider({children}: {children: ReactNode}) {
  const {api, status, userKey} = useSession();
  const client = useQueryClient();
  const signedIn = status === 'ready' || status === 'onboarding';
  const key = [...userKey, 'settings'];
  const query = useQuery({queryKey: key, enabled: signedIn,
    queryFn: ({signal}) => api.call('get', '/api/v2/me/settings', {signal})});
  const [local, setLocal] = useState<Values>(() => readLocal(LOCAL_PREFS, {}));
  const [presentation, setPresentationState] = useState<Presentation>(() =>
    readLocal<Presentation | null>(PRESENTATION_KEY, null) ?? (typeof innerWidth !== 'undefined' && innerWidth >= 900 ? 'focus' : 'desktop'));

  // Saves run one at a time, each with the latest server version, so quick successive toggles never race into a
  // 409. Values still in flight stay applied on screen while earlier saves complete.
  const chain = useRef<Promise<unknown>>(Promise.resolve());
  const pending = useRef<Values[]>([]);
  const inFlight = () => Object.assign({}, ...pending.current) as Values;
  const mutation = useMutation({
    mutationFn: (values: Values) => {
      const run = chain.current.then(() => {
        const current = client.getQueryData<Schemas['SettingsOut']>(key);
        return api.call('patch', '/api/v2/me/settings', {body: {version: current?.version ?? 0, values}});
      });
      chain.current = run.catch(() => undefined);
      return run;
    },
    onMutate: async values => {
      await client.cancelQueries({queryKey: key});
      pending.current.push(values);
      const previous = client.getQueryData<Schemas['SettingsOut']>(key);
      if (previous) client.setQueryData(key, {...previous, values: {...previous.values, ...values}});
      return {previous, values};
    },
    onSuccess: data => client.setQueryData(key, {...data, values: {...data.values, ...inFlight()}}),
    onError: async (error, _values, context) => {
      if (context?.previous) client.setQueryData(key, context.previous);
      if (error instanceof ApiFailure && error.code === 'SETTINGS_CHANGED') {
        await client.invalidateQueries({queryKey: key});
        toast(translate(lang, 'settings.changedElsewhere'));
      }
    },
    onSettled: (_d, _e, _v, context) => { pending.current = pending.current.filter(v => v !== context?.values); },
  });

  const values: Values = signedIn ? (query.data?.values ?? {}) : local;
  const osReduced = useMedia('(prefers-reduced-motion: reduce)');
  const osLight = useMedia('(prefers-color-scheme: light)');
  const lang: Lang = signedIn && (values.language === 'en' || values.language === 'id') ? values.language : detectLanguage();
  const theme = (['dark', 'light', 'system'].includes(String(values.theme)) ? values.theme : 'system') as ThemeChoice;
  const resolvedTheme = presentation === 'focus' ? 'dark' : theme === 'system' ? (osLight ? 'light' : 'dark') : theme;
  const reducedMotion = osReduced || values.reduce_motion === true;

  useEffect(() => {
    const html = document.documentElement;
    html.dataset.theme = resolvedTheme;
    html.dataset.motion = reducedMotion ? 'reduced' : 'full';
    html.dataset.presentation = presentation;
    html.lang = lang;
  }, [resolvedTheme, reducedMotion, presentation, lang]);
  useEffect(() => configureSound(values.sound_effects === true, Number(values.sound_volume ?? 60)),
    [values.sound_effects, values.sound_volume]);

  const update = useCallback(async (next: Values) => {
    if (!signedIn) {
      const merged = {...local, ...next};
      setLocal(merged);
      writeLocal(LOCAL_PREFS, merged);
      return;
    }
    await mutation.mutateAsync(next);
  }, [signedIn, local, mutation]);

  const setLanguage = useCallback(async (next: Lang) => {
    rememberLanguage(next);
    if (signedIn) await mutation.mutateAsync({language: next}); else setLocal(l => ({...l}));
  }, [signedIn, mutation]);

  const setPresentation = useCallback((p: Presentation) => { setPresentationState(p); writeLocal(PRESENTATION_KEY, p); }, []);

  const value = useMemo<Settings>(() => ({
    values, schema: query.data ?? null, lang, theme, resolvedTheme, reducedMotion, presentation,
    setPresentation, update, setLanguage,
  }), [values, query.data, lang, theme, resolvedTheme, reducedMotion, presentation, setPresentation, update, setLanguage]);

  return <Ctx.Provider value={value}>
    <I18nProvider lang={lang}>
      <LazyMotion features={motionFeatures} strict>
        <MotionConfig reducedMotion={reducedMotion ? 'always' : 'never'}>{children}</MotionConfig>
      </LazyMotion>
    </I18nProvider>
  </Ctx.Provider>;
}

export function useSettings(): Settings {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useSettings outside SettingsProvider');
  return ctx;
}
