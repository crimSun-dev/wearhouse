import {dur, easeInOut} from './tokens.ts';

/** The first matching element that is actually on screen (a hidden nav variant has no client rects). */
function visible(selectors: string[]): HTMLElement | null {
  for (const s of selectors) {
    const el = [...document.querySelectorAll<HTMLElement>(s)].find(e => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden');
    if (el) return el;
  }
  return null;
}

/**
 * Flies a copy of `from` into the first visible `targets` element, then makes that element land (`.nav-landed`).
 * Callers skip it under reduced motion. The original stays where it is; the copy is decorative and hidden from
 * assistive technology, and it is removed when the flight finishes or is interrupted.
 */
export function flyTo(from: HTMLElement, targets: string[]) {
  const target = visible(targets);
  if (!target || typeof from.animate !== 'function') return;
  const a = from.getBoundingClientRect();
  const b = target.getBoundingClientRect();
  const ghost = from.cloneNode(true) as HTMLElement;
  ghost.setAttribute('aria-hidden', 'true');
  ghost.removeAttribute('id');
  ghost.classList.add('fly-ghost');
  Object.assign(ghost.style, {position: 'fixed', left: `${a.left}px`, top: `${a.top}px`, width: `${a.width}px`, height: `${a.height}px`, margin: '0'});
  document.body.append(ghost);
  const dx = b.left + b.width / 2 - (a.left + a.width / 2);
  const dy = b.top + b.height / 2 - (a.top + a.height / 2);
  const scale = Math.max(0.06, Math.min(b.width / a.width, b.height / a.height));
  const flight = ghost.animate([
    {transform: 'none', opacity: 1},
    {transform: `translate(${dx}px, ${dy}px) scale(${scale})`, opacity: 0.25},
  ], {duration: dur.d5 * 1000, easing: `cubic-bezier(${easeInOut.join(',')})`});
  const land = () => {
    ghost.remove();
    target.classList.remove('nav-landed');
    void target.offsetWidth;   // restart the landing animation if it is already running
    target.classList.add('nav-landed');
    target.addEventListener('animationend', () => target.classList.remove('nav-landed'), {once: true});
  };
  flight.onfinish = land;
  flight.oncancel = () => ghost.remove();
}
