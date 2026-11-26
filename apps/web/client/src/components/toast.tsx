import {useSyncExternalStore} from 'react';
import * as m from 'motion/react-m';
import {AnimatePresence} from 'motion/react';
import {dur, easeOut} from '../motion/tokens.ts';
import './components.css';

type Toast = {id: number; text: string; tone: 'info' | 'error' | 'success'};
let toasts: Toast[] = [];
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => { for (const l of listeners) l(); };

export function toast(text: string, tone: Toast['tone'] = 'info', ms = 5000) {
  const t = {id: ++seq, text, tone};
  toasts = [...toasts, t].slice(-3);
  emit();
  setTimeout(() => { toasts = toasts.filter(x => x.id !== t.id); emit(); }, ms);
}

export function Toaster() {
  const list = useSyncExternalStore(l => { listeners.add(l); return () => { listeners.delete(l); }; }, () => toasts, () => toasts);
  return <div className="toaster" role="status" aria-live="polite">
    <AnimatePresence initial={false}>
      {list.map(t => <m.div key={t.id} className={`toast toast-${t.tone}`} layout
        initial={{opacity: 0, y: 16}} animate={{opacity: 1, y: 0}} exit={{opacity: 0, y: 8}}
        transition={{duration: dur.d3, ease: easeOut}}>{t.text}</m.div>)}
    </AnimatePresence>
  </div>;
}
