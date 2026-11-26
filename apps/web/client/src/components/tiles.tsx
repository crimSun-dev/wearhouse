import type {ReactNode} from 'react';
import {focusItemProps} from '../focus/FocusZone.tsx';
import type {Descriptor} from '../focus/store.ts';
import {Media} from './Media.tsx';

type TileProps = {
  href: string;
  title: string;
  /** Second line under the title (state, price or occasion). */
  meta?: string;
  ratio: 'portrait' | 'look' | 'wide';
  image?: string | null;
  slot?: string | null;
  badges?: ReactNode;
  descriptor: Omit<Descriptor, 'title'>;
  children?: ReactNode;
};

/** One link per tile (image and title together); secondary actions live outside it. */
export function Tile({href, title, meta, ratio, image, slot, badges, descriptor, children}: TileProps) {
  return <a href={href} className={`tile tile-${ratio}`} {...focusItemProps({...descriptor, title})}>
    <span className="tile-media">
      {children ?? <Media src={image} alt="" slot={slot} />}
      {badges && <span className="tile-badges">{badges}</span>}
    </span>
    <span className="tile-text">
      <span className="tile-title">{title}</span>
      {meta && <span className="tile-meta">{meta}</span>}
    </span>
  </a>;
}

/** Deterministic accent from a garment's colour name, used only to tint the backdrop wash.
 * Data, not styling: a labelled approximation of H&M colour names, so it lives here rather than in tokens. */
const swatches: Record<string, string> = {
  black: '#3a2a33', white: '#efe6e9', beige: '#cdb99a', grey: '#8d8590', gray: '#8d8590', blue: '#4f6ea8', navy: '#2f3f6b',
  red: '#b23a48', pink: '#e59ab8', green: '#4f8a63', yellow: '#d8b84a', brown: '#7a5640', orange: '#d27a3a',
  purple: '#7b4b8f', khaki: '#a39a6a', turquoise: '#3f9a9a', lilac: '#b59ad0', silver: '#b9b6bd', gold: '#c9a24a',
};
export function accentFor(colour: string | null | undefined): string | undefined {
  if (!colour) return undefined;
  const key = colour.toLowerCase();
  return Object.entries(swatches).find(([name]) => key.includes(name))?.[1];
}
