/**
 * Tiny DOM helpers shared by the temporary pages. Every API value goes through textContent (never innerHTML).
 */
import {describe} from './messages.ts';

const mainEl = () => document.getElementById('main')!;
const statusEl = () => document.getElementById('status')!;

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, props: Partial<HTMLElementTagNameMap[K]> & {text?: string} = {},
                                                           ...children: (Node | string)[]): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  const {text, ...rest} = props as {text?: string};
  Object.assign(node, rest);
  if (text !== undefined) node.textContent = text;
  for (const c of children) node.append(c);
  return node;
}

export function field(label: string, input: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): HTMLElement {
  input.id ||= 'f-' + label.toLowerCase().replace(/\W+/g, '-');
  return el('div', {className: 'field'}, el('label', {htmlFor: input.id, text: label}), input);
}

export function say(text: string, kind: 'ok' | 'error' | 'busy' = 'ok') {
  const box = statusEl();
  box.textContent = text;
  box.className = kind;
}

export async function act<T>(button: HTMLButtonElement | null, work: () => Promise<T>, done?: string): Promise<T | undefined> {
  if (button) button.disabled = true;
  say('Working…', 'busy');
  try {
    const out = await work();
    say(typeof out === 'string' ? out : done ?? 'Done.');  // an action may return its own success message
    return out;
  } catch (err) {
    say(describe(err), 'error');
    return undefined;
  } finally {
    if (button) button.disabled = false;
  }
}

export function button(text: string, onClick: (b: HTMLButtonElement) => void, kind = ''): HTMLButtonElement {
  const b = el('button', {type: 'button', text, className: kind});
  b.addEventListener('click', () => onClick(b));
  return b;
}

let routeHash: string | null = null;

/** Called at the start of every route: a slower render started for an older route must not overwrite this one. */
export function beginRoute() {
  routeHash = location.hash;
  // Never leave the previous page interactive while the next one loads (its inputs would be silently discarded).
  const main = mainEl();
  main.setAttribute('aria-busy', 'true');
  main.replaceChildren(el('p', {className: 'hint', text: 'Loading…'}));
}

export function view(title: string, ...children: (Node | string)[]) {
  if (routeHash !== null && location.hash !== routeHash) return;  // stale render from a route we already left
  const main = mainEl();
  main.removeAttribute('aria-busy');
  main.replaceChildren(el('h1', {text: title}), ...children);
  main.focus();
}

export function select(name: string, options: Array<[string, string]>, value = ''): HTMLSelectElement {
  const s = el('select', {name});
  for (const [v, label] of options) s.append(el('option', {value: v, text: label}));
  if (options.some(([v]) => v === value)) s.value = value;  // otherwise keep the first option (never an empty select)
  return s;
}
