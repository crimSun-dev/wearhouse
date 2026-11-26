import {forwardRef, useEffect, useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes} from 'react';
import {Check, ChevronDown, LoaderCircle, Minus, Plus} from 'lucide-react';
import * as m from 'motion/react-m';
import {spring} from '../motion/tokens.ts';
import './components.css';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'md' | 'lg';
  loading?: boolean;
  /** Briefly shows a check after a confirmed success. */
  success?: boolean;
  icon?: ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {variant = 'secondary', size = 'md', loading, success, icon, children, className, disabled, ...rest}, ref) {
  const state = loading ? 'loading' : success ? 'success' : 'rest';
  return <button ref={ref} type="button" {...rest} disabled={disabled || loading} aria-busy={loading || undefined}
    className={`btn btn-${variant} btn-${size} ${className ?? ''}`} data-state={state}>
    <span className="btn-label">{icon}{children}</span>
    {loading && <span className="btn-overlay" aria-hidden><LoaderCircle className="spin" size={18} /></span>}
    {success && !loading && <span className="btn-overlay" aria-hidden><Check size={18} /></span>}
  </button>;
});

export function IconButton({label, children, badge, className, ...rest}:
  ButtonHTMLAttributes<HTMLButtonElement> & {label: string; badge?: number}) {
  return <button type="button" {...rest} aria-label={badge ? `${label} (${badge})` : label} title={label}
    className={`icon-btn ${className ?? ''}`}>
    {children}
    {!!badge && <span className="badge" aria-hidden>{badge > 99 ? '99+' : badge}</span>}
  </button>;
}

export function Chip({selected, children, ...rest}: ButtonHTMLAttributes<HTMLButtonElement> & {selected?: boolean}) {
  return <button type="button" {...rest} className={`chip ${selected ? 'is-selected' : ''}`} aria-pressed={selected}>{children}</button>;
}

export function Toggle({checked, onChange, label, description, disabled}:
  {checked: boolean; onChange: (v: boolean) => void; label: string; description?: string; disabled?: boolean}) {
  const id = useId();
  return <div className="toggle-row">
    <span className="toggle-text"><span id={id}>{label}</span>{description && <small>{description}</small>}</span>
    <button type="button" role="switch" aria-checked={checked} aria-labelledby={id} disabled={disabled}
      className={`toggle ${checked ? 'is-on' : ''}`} onClick={() => onChange(!checked)}>
      <m.span className="toggle-thumb" layout transition={spring.snappy} />
    </button>
  </div>;
}

/** Segmented control: a radio group with a sliding indicator. */
export function Segmented<T extends string>({value, options, onChange, label}:
  {value: T; options: Array<{value: T; label: string; icon?: ReactNode}>; onChange: (v: T) => void; label: string}) {
  const group = useId();
  return <div className="segmented" role="radiogroup" aria-label={label}>
    {options.map(o => <button type="button" key={o.value} role="radio" aria-checked={o.value === value}
      className={`seg ${o.value === value ? 'is-on' : ''}`} onClick={() => onChange(o.value)}>
      {o.value === value && <m.span layoutId={`seg-${group}`} className="seg-pill" transition={spring.snappy} />}
      <span className="seg-label">{o.icon}{o.label}</span>
    </button>)}
  </div>;
}

/** Tabs with a sliding underline. `[` and `]` switch them through the shell's intents. */
export function Tabs<T extends string>({value, tabs, onChange, label}:
  {value: T; tabs: Array<{value: T; label: string; count?: number}>; onChange: (v: T) => void; label: string}) {
  const group = useId();
  return <div className="tabs" role="tablist" aria-label={label}>
    {tabs.map(t => <button type="button" key={t.value} role="tab" aria-selected={t.value === value} id={`${group}-${t.value}`}
      className={`tab ${t.value === value ? 'is-on' : ''}`} onClick={() => onChange(t.value)}>
      {t.label}{t.count != null && <span className="tab-count">{t.count}</span>}
      {t.value === value && <m.span layoutId={`tab-${group}`} className="tab-line" transition={spring.snappy} />}
    </button>)}
  </div>;
}

export function Select({label, children, ...rest}: SelectHTMLAttributes<HTMLSelectElement> & {label: string}) {
  const id = useId();
  return <label className="field" htmlFor={id}><span className="field-label">{label}</span>
    <span className="select-wrap"><select id={id} {...rest}>{children}</select><ChevronDown className="select-chevron" size={18} aria-hidden /></span></label>;
}

export function TextField({label, error, hint, ...rest}: InputHTMLAttributes<HTMLInputElement> & {label: string; error?: string; hint?: string}) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-err`].filter(Boolean).join(' ') || undefined;
  return <div className={`field ${error ? 'has-error' : ''}`}>
    <label className="field-label" htmlFor={id}>{label}</label>
    <input id={id} {...rest} aria-invalid={!!error || undefined} aria-describedby={describedBy} />
    {hint && <small id={`${id}-hint`} className="field-hint">{hint}</small>}
    {error && <small id={`${id}-err`} className="field-error" role="alert">{error}</small>}
  </div>;
}

export function Slider({label, value, min, max, onCommit}: {label: string; value: number; min: number; max: number; onCommit: (v: number) => void}) {
  const id = useId();
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return <div className="field slider">
    <label className="field-label" htmlFor={id}>{label}<output htmlFor={id}>{v}</output></label>
    <input id={id} type="range" min={min} max={max} value={v} style={{'--p': `${((v - min) / (max - min)) * 100}%`} as never}
      onChange={e => setV(Number(e.target.value))} onPointerUp={() => onCommit(v)} onKeyUp={() => onCommit(v)} />
  </div>;
}

export function Stepper({label, value, min, max, onChange}: {label: string; value: number; min: number; max: number; onChange: (v: number) => void}) {
  return <div className="stepper" role="group" aria-label={label}>
    <button type="button" aria-label={`${label}: −1`} disabled={value <= min} onClick={() => onChange(value - 1)}><Minus size={16} /></button>
    <output aria-live="polite">{value}</output>
    <button type="button" aria-label={`${label}: +1`} disabled={value >= max} onClick={() => onChange(value + 1)}><Plus size={16} /></button>
  </div>;
}

export function Skeleton({ratio = '2 / 3', className}: {ratio?: string; className?: string}) {
  return <span className={`skeleton ${className ?? ''}`} style={{aspectRatio: ratio}} aria-hidden />;
}
