import {useQuery} from '@tanstack/react-query';
import {ExternalLink} from 'lucide-react';
import {useSession} from '../session/SessionProvider.tsx';
import {useI18n} from '../i18n/index.tsx';
import {ErrorState} from '../components/states.tsx';
import {Skeleton} from '../components/ui.tsx';
import './pages.css';

export function AboutRoute() {
  const {t} = useI18n();
  const {api} = useSession();
  const about = useQuery({queryKey: ['public', 'about'], staleTime: 60 * 60_000,
    queryFn: ({signal}) => api.call('get', '/api/v2/about', {signal, anonymous: true})});
  const health = useQuery({queryKey: ['public', 'health'], retry: false,
    queryFn: ({signal}) => api.call('get', '/api/v2/health', {signal, anonymous: true})});
  return <article className="page page-read">
    <h1>{t('about.title')}</h1>
    <p className={`health ${health.isSuccess ? 'is-ok' : health.isError ? 'is-bad' : ''}`} role="status">
      <span className="health-dot" aria-hidden />{health.isSuccess ? t('about.healthy') : health.isError ? t('about.unhealthy') : t('common.loading')}
    </p>
    {about.isPending ? <Skeleton ratio="3 / 1" /> : about.isError ? <ErrorState error={about.error} onRetry={() => about.refetch()} /> : <>
      <p className="muted">{t('about.version', {v: about.data.version})} · {t('about.schema', {v: about.data.schema_head})}</p>
      <section className="read-section">
        <h2>{t('about.sources')}</h2>
        <ul className="source-list">
          {about.data.sources.map(s => <li key={s.name}>
            <h3>{s.name}</h3>
            <p className="muted">{s.publisher}</p>
            <dl>
              <dt>{t('about.usedFor')}</dt><dd>{s.used_for}</dd>
              <dt>{t('about.licence')}</dt><dd>{s.licence}</dd>
              {s.citation && <><dt>Citation</dt><dd>{s.citation}</dd></>}
            </dl>
            <a href={s.terms_url} target="_blank" rel="noreferrer">{t('about.terms')} <ExternalLink size={14} aria-hidden /></a>
          </li>)}
        </ul>
      </section>
      {about.data.notices.length > 0 && <section className="read-section"><h2>{t('about.notices')}</h2>
        <ul>{about.data.notices.map(n => <li key={n}>{n}</li>)}</ul></section>}
    </>}
  </article>;
}
