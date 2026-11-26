import {useRef, type ReactNode} from 'react';
import {ChevronLeft, ChevronRight} from 'lucide-react';
import {FocusZone} from '../focus/FocusZone.tsx';
import {useI18n} from '../i18n/index.tsx';
import {useSettings} from '../settings/SettingsProvider.tsx';

/** A horizontal rail with snap, visible previous/next controls and a heading. */
export function Rail({title, action, children, version, note, size = 'md', autoFocus, titleHidden}: {
  title: string; action?: ReactNode; children: ReactNode; version?: unknown; note?: ReactNode; size?: 'md' | 'lg'; autoFocus?: boolean;
  /** The title is still announced, but not shown (e.g. when a tab already names the row). */
  titleHidden?: boolean;
}) {
  const {t} = useI18n();
  const {reducedMotion} = useSettings();
  const wrap = useRef<HTMLDivElement>(null);
  const scroll = (dir: -1 | 1) => {
    const zone = wrap.current?.querySelector<HTMLElement>('[data-focus-zone]');
    zone?.scrollBy({left: dir * zone.clientWidth * 0.8, behavior: reducedMotion ? 'auto' : 'smooth'});
  };
  return <section className={`rail rail-${size}`} ref={wrap}>
    <header className={`rail-head ${titleHidden ? 'rail-head-compact' : ''}`}>
      <h2 className={titleHidden ? 'visually-hidden' : 'rail-title'}>{title}</h2>
      {note && <span className="rail-note">{note}</span>}
      <span className="rail-actions">
        {action}
        <button type="button" className="rail-nav" aria-label={`${t('common.previous')}: ${title}`} onClick={() => scroll(-1)}><ChevronLeft size={20} /></button>
        <button type="button" className="rail-nav" aria-label={`${t('common.next')}: ${title}`} onClick={() => scroll(1)}><ChevronRight size={20} /></button>
      </span>
    </header>
    <FocusZone kind="rail" label={title} className="rail-track" version={version} autoFocus={autoFocus}>{children}</FocusZone>
  </section>;
}
