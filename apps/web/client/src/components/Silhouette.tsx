// Authored slot silhouettes: the honest stand-in when a garment has no image ("Image unavailable").
const paths: Record<string, string> = {
  top: 'M34 18 L46 12 Q50 18 54 18 Q58 18 62 12 L74 18 L86 34 L76 42 L70 36 L70 88 L38 88 L38 36 L32 42 L22 34 Z',
  outer: 'M36 14 L46 10 L54 30 L62 10 L72 14 L88 36 L80 92 L66 92 L64 46 L54 30 L44 46 L42 92 L28 92 L20 36 Z',
  bottom: 'M36 12 L72 12 L76 92 L60 92 L54 40 L48 92 L32 92 Z',
  dress: 'M44 10 L64 10 L62 26 L70 34 L84 92 L24 92 L38 34 L46 26 Z',
  footwear: 'M18 64 Q20 52 32 52 L44 54 Q50 64 64 64 L88 66 Q92 76 84 78 L22 78 Q16 76 18 64 Z',
  bag: 'M30 40 L78 40 L84 88 L24 88 Z M42 40 Q42 22 54 22 Q66 22 66 40',
  headwear: 'M22 66 Q22 32 54 30 Q86 32 86 66 Z M14 66 L94 66 L94 72 L14 72 Z',
  eyewear: 'M14 48 L44 48 L42 62 Q30 70 18 62 Z M64 48 L94 48 L90 62 Q78 70 66 62 Z M44 52 L64 52',
  accessory: 'M54 18 L80 44 L54 90 L28 44 Z',
};

export function Silhouette({slot, label}: {slot: string | null | undefined; label?: string}) {
  const d = paths[slot ?? ''] ?? paths.accessory;
  return <span className="silhouette" role={label ? 'img' : undefined} aria-label={label}>
    <svg viewBox="0 0 108 100" aria-hidden focusable="false">
      <path d={d} fill="currentColor" fillOpacity="0.16" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
    </svg>
    {label && <span className="silhouette-label">{label}</span>}
  </span>;
}
