import {useFocused} from '../focus/store.ts';
import {useI18n} from '../i18n/index.tsx';

function Key({k}: {k: string}) { return <kbd className="key">{k}</kbd>; }

/** Focus-mode footer: keyboard keys for what the focused object and the shell can do. Hidden on touch-only devices. */
export function HintBar({onMenu}: {onMenu: () => void}) {
  const {t} = useI18n();
  const focused = useFocused();
  const actions = focused?.actions ?? [{key: 'Enter', label: t('hint.select')}];
  return <footer className="hintbar" aria-label={t('hint.bar')}>
    <button type="button" className="hint hint-btn" onClick={onMenu}><Key k="M" />{t('hint.menu')}</button>
    <span className="hint-group">
      {actions.map(a => <span key={a.key + a.label} className="hint"><Key k={a.key} />{a.label}</span>)}
      <span className="hint"><Key k="/" />{t('hint.search')}</span>
      <span className="hint"><Key k="Q" />{t('hint.quick')}</span>
      <span className="hint"><Key k="Esc" />{t('hint.back')}</span>
    </span>
  </footer>;
}
