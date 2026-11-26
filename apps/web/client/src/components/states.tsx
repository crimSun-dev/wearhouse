import {useState, type ReactNode} from 'react';
import {ApiFailure} from '../api/index.ts';
import {useI18n} from '../i18n/index.tsx';
import {Button} from './ui.tsx';

/** Recoverable error: plain message, retry, and the request id for support. */
export function ErrorState({error, onRetry}: {error: unknown; onRetry?: () => void}) {
  const {t, errorText} = useI18n();
  const [copied, setCopied] = useState(false);
  const failure = error instanceof ApiFailure ? error : null;
  const offline = !failure;
  const message = offline ? t('common.offline') : errorText(failure.code, failure.message);
  return <div className="state state-error" role="alert">
    <p>{message}</p>
    <div className="state-actions">
      {onRetry && <Button variant="secondary" onClick={onRetry}>{t('common.retry')}</Button>}
      {failure?.requestId && <Button variant="ghost" onClick={async () => {
        await navigator.clipboard?.writeText(`${failure.code} · ${failure.requestId}`).catch(() => undefined);
        setCopied(true);
      }}>{copied ? t('common.copied') : t('common.copyDetails')}</Button>}
    </div>
  </div>;
}

export function EmptyState({title, body, children}: {title: string; body?: string; children?: ReactNode}) {
  return <div className="state state-empty"><h2>{title}</h2>{body && <p>{body}</p>}
    {children && <div className="state-actions">{children}</div>}</div>;
}
