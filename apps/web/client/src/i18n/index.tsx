import {createContext, useCallback, useContext, useMemo, type ReactNode} from 'react';
import {en, type MessageKey} from './en.ts';
import {id} from './id.ts';
import {errorCopy} from './errors.ts';

export type Lang = 'en' | 'id';
export const TIME_ZONE = 'Asia/Jakarta';
const catalogues = {en, id} as const;
const LOCAL_KEY = 'wearhouse.lang';

/** Signed-out language: a remembered device choice, else the browser (any `id` locale gets Indonesian). */
export function detectLanguage(languages: readonly string[] = navigator.languages ?? [navigator.language]): Lang {
  try {
    const saved = window.localStorage.getItem(LOCAL_KEY);
    if (saved === 'en' || saved === 'id') return saved;
  } catch { /* storage unavailable: fall through to the browser */ }
  return languages.some(l => l.toLowerCase().split('-')[0] === 'id') ? 'id' : 'en';
}
export function rememberLanguage(lang: Lang) {
  try { window.localStorage.setItem(LOCAL_KEY, lang); } catch { /* not persisted; still applied */ }
}

export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>) {
  const text: string = catalogues[lang][key] ?? en[key];
  return vars ? text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? '')) : text;
}

type I18n = {
  lang: Lang;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  errorText: (code: string, fallback?: string) => string;
  date: (value: Date | string, opts?: Intl.DateTimeFormatOptions) => string;
  time: (value: Date | string) => string;
  idr: (amount: number) => string;
  number: (n: number) => string;
};

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({lang, children}: {lang: Lang; children: ReactNode}) {
  const locale = lang === 'id' ? 'id-ID' : 'en-GB';
  const t = useCallback((key: MessageKey, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);
  const value = useMemo<I18n>(() => ({
    lang, t,
    errorText: (code, fallback) => (errorCopy as Record<string, {en: string; id: string}>)[code]?.[lang] ?? fallback ?? translate(lang, 'common.error'),
    date: (v, opts = {weekday: 'long', day: 'numeric', month: 'long'}) =>
      new Intl.DateTimeFormat(locale, {timeZone: TIME_ZONE, ...opts}).format(typeof v === 'string' ? new Date(v) : v),
    time: v => new Intl.DateTimeFormat(locale, {timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit', hour12: false})
      .format(typeof v === 'string' ? new Date(v) : v),
    idr: amount => new Intl.NumberFormat('id-ID', {style: 'currency', currency: 'IDR', maximumFractionDigits: 0}).format(amount),
    number: n => new Intl.NumberFormat(locale).format(n),
  }), [lang, locale, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useI18n outside I18nProvider');
  return ctx;
}
