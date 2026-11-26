import {useEffect, useRef, type ReactNode} from 'react';
import * as m from 'motion/react-m';
import {AnimatePresence} from 'motion/react';
import {X} from 'lucide-react';
import {spring, dur} from '../motion/tokens.ts';
import {useI18n} from '../i18n/index.tsx';

type Side = 'left' | 'right' | 'center' | 'bottom';
const offsets: Record<Side, object> = {
  left: {x: '-100%'}, right: {x: '100%'}, bottom: {y: '100%'}, center: {y: 16, scale: 0.98},
};

/**
 * Modal surface on a native <dialog>: the browser traps focus, Escape closes it, and focus returns to the opener.
 * Panels slide in from their edge; under reduced motion MotionConfig turns that into a fade.
 */
export function Overlay({open, onClose, side, title, children, labelledBy}: {
  open: boolean; onClose: () => void; side: Side; title: string; children: ReactNode; labelledBy?: string;
}) {
  const {t} = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement as HTMLElement;
      d.showModal();
      // Big Picture: a menu opens on its first entry, not on the close button.
      d.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    }
  }, [open]);
  const finishClose = () => {
    const d = ref.current;
    if (d?.open && !open) { d.close(); opener.current?.focus(); }
  };
  return <dialog ref={ref} className={`overlay overlay-${side}`} aria-label={labelledBy ? undefined : title}
    aria-labelledby={labelledBy} onCancel={e => { e.preventDefault(); onClose(); }}
    onClick={e => { if (e.target === ref.current) onClose(); }}>
    <AnimatePresence onExitComplete={finishClose}>
      {open && <m.div className="overlay-panel" initial={{opacity: 0, ...offsets[side]}}
        animate={{opacity: 1, x: 0, y: 0, scale: 1}} exit={{opacity: 0, ...offsets[side]}}
        transition={{...spring.sheet, opacity: {duration: dur.d2}}}>
        <header className="overlay-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" aria-label={t('common.close')} onClick={onClose}><X size={20} /></button>
        </header>
        <div className="overlay-body">{children}</div>
      </m.div>}
    </AnimatePresence>
  </dialog>;
}
