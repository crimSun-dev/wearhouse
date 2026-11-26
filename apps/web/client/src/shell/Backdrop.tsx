import * as m from 'motion/react-m';
import {AnimatePresence} from 'motion/react';
import {useSettledFocus} from '../focus/store.ts';
import {resolveMedia} from '../components/Media.tsx';
import {dur, easeOut} from '../motion/tokens.ts';

/** The page backdrop the focused tile repaints: an accent wash plus a heavily blurred copy of its image. */
export function Backdrop() {
  const focused = useSettledFocus(140);   // repaint once the selection rests: one layer, not one per keypress
  const image = resolveMedia(focused?.image ?? null);
  return <div className="backdrop" aria-hidden>
    <AnimatePresence initial={false}>
      <m.div key={focused?.id ?? 'none'} className="backdrop-layer"
        initial={{opacity: 0}} animate={{opacity: 1}} exit={{opacity: 0}} transition={{duration: dur.d4, ease: easeOut}}
        style={{'--wash': focused?.accent ?? 'transparent'} as never}>
        {image && <img src={image} alt="" className="backdrop-image" />}
      </m.div>
    </AnimatePresence>
    <div className="backdrop-vignette" />
  </div>;
}
