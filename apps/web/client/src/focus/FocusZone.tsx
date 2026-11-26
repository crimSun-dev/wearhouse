import {useEffect, useLayoutEffect, useRef, type ReactNode} from 'react';
import {focusFirst, installKeyboard, refresh, registerZone, type ZoneKind} from './engine.ts';
import {publishFocus, type Descriptor} from './store.ts';
import {useSettings} from '../settings/SettingsProvider.tsx';

/** Installs keyboard spatial navigation (no gamepad: owner decision 2026-11-26). */
export function FocusRoot({children}: {children: ReactNode}) {
  const {reducedMotion} = useSettings();
  const reduced = useRef(reducedMotion);
  reduced.current = reducedMotion;
  useEffect(() => installKeyboard(() => reduced.current), []);
  return <>{children}</>;
}

type ZoneProps = {
  kind?: ZoneKind;
  label: string;
  className?: string;
  children: ReactNode;
  /** Changes whenever the item list changes, so the roving tabindex is reapplied. */
  version?: unknown;
  as?: 'div' | 'ul';
  /** Select this zone's first item when the screen opens in Focus mode. */
  autoFocus?: boolean;
};

export function FocusZone({kind = 'rail', label, className, children, version, as = 'div', autoFocus}: ZoneProps) {
  const ref = useRef<HTMLElement>(null);
  const {presentation} = useSettings();
  useLayoutEffect(() => (ref.current ? registerZone(ref.current, kind) : undefined), [kind]);
  useLayoutEffect(() => { if (ref.current) refresh(ref.current); }, [version]);
  useEffect(() => { if (autoFocus && presentation === 'focus' && ref.current) focusFirst(ref.current); }, [autoFocus, presentation, version]);
  const Tag = as;
  return <Tag ref={ref as never} data-focus-zone={kind} aria-label={label} role={as === 'div' ? 'group' : undefined}
    className={className}>{children}</Tag>;
}

/** Props that make an element a focus item which publishes its descriptor when focused or hovered. */
export function focusItemProps(descriptor: Descriptor) {
  return {
    'data-focus-item': '',
    onFocus: () => publishFocus(descriptor),
    onPointerMove: (e: React.PointerEvent) => {
      if (e.pointerType === 'mouse' && (e.movementX !== 0 || e.movementY !== 0)) publishFocus(descriptor);
    },
  };
}
