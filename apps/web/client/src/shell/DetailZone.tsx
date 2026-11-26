import type {ReactNode} from 'react';
import * as m from 'motion/react-m';
import {AnimatePresence} from 'motion/react';
import {useSettledFocus, type Descriptor} from '../focus/store.ts';
import {dur, easeOut} from '../motion/tokens.ts';

/** Big Picture's detail area under the rail: the focused object's title, meta and actions. */
export function DetailZone({fallback, actions}: {fallback: Descriptor; actions?: (d: Descriptor) => ReactNode}) {
  const focused = useSettledFocus() ?? fallback;
  return <div className="detail-zone" aria-live="polite">
    <AnimatePresence mode="wait" initial={false}>
      <m.div key={focused.id} initial={{opacity: 0, y: 8}} animate={{opacity: 1, y: 0}} exit={{opacity: 0, y: -4}}
        transition={{duration: dur.d2, ease: easeOut}} className="detail-inner">
        <h2 className="detail-title">{focused.title}</h2>
        {focused.meta && <p className="detail-meta">{focused.meta}</p>}
        {actions && <div className="detail-actions">{actions(focused)}</div>}
      </m.div>
    </AnimatePresence>
  </div>;
}
