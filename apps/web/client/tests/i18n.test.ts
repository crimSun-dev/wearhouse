// @vitest-environment jsdom
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {describe, expect, it} from 'vitest';
import {en} from '../src/i18n/en.ts';
import {id} from '../src/i18n/id.ts';
import {errorCopy} from '../src/i18n/errors.ts';
import {detectLanguage, translate} from '../src/i18n/index.tsx';

// Node 26's own (unconfigured) Web Storage global shadows jsdom's, so give the window a plain in-memory store.
const memory = new Map<string, string>();
Object.defineProperty(window, 'localStorage', {configurable: true, value: {
  getItem: (k: string) => memory.get(k) ?? null, setItem: (k: string, v: string) => void memory.set(k, v),
  removeItem: (k: string) => void memory.delete(k), clear: () => memory.clear(),
}});

describe('message catalogues', () => {
  it('has exactly the same keys in English and Indonesian, none empty', () => {
    expect(Object.keys(id).sort()).toEqual(Object.keys(en).sort());
    for (const [k, v] of Object.entries(id)) expect(v.trim(), k).not.toBe('');
  });
  it('keeps the same {placeholders} in both languages', () => {
    const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const k of Object.keys(en) as Array<keyof typeof en>) expect(vars(id[k]), k).toEqual(vars(en[k]));
  });
  it('covers every API error code in both languages', () => {
    const source = readFileSync(resolve(process.cwd(), '../../../packages/contracts/src/error-codes.d.ts'), 'utf8');
    const codes = [...source.matchAll(/'([A-Z_]+)'/g)].map(m => m[1]);
    expect(codes.length).toBeGreaterThan(40);
    expect(Object.keys(errorCopy).sort()).toEqual([...codes].sort());
    for (const c of codes) {
      const copy = errorCopy[c as keyof typeof errorCopy];
      expect(copy.en && copy.id, c).toBeTruthy();
    }
  });
  it('interpolates variables', () => {
    expect(translate('id', 'home.wearCount', {n: 3})).toBe('Dipakai 3×');
  });
});

describe('signed-out language', () => {
  it('defaults to English, whatever the browser language', () => {
    window.localStorage.clear();
    Object.defineProperty(navigator, 'languages', {value: ['id-ID', 'id'], configurable: true});
    expect(detectLanguage()).toBe('en');
  });
  it('prefers a remembered device choice', () => {
    window.localStorage.setItem('wearhouse.lang', 'id');
    expect(detectLanguage()).toBe('id');
    window.localStorage.clear();
  });
});