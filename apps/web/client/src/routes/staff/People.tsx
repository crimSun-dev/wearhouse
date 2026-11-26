import {useState, type FormEvent} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {useI18n} from '../../i18n/index.tsx';
import {useSession} from '../../session/SessionProvider.tsx';
import {ApiFailure} from '../../api/index.ts';
import {Button, Select, Skeleton, TextField} from '../../components/ui.tsx';
import {toast} from '../../components/toast.tsx';
import {useFail} from '../wardrobe/shared.tsx';
import {LookCard, PersonChip} from '../social/Community.tsx';
import {StaffError} from './Staff.tsx';
import {useStaffKey} from './Catalogue.tsx';
import '../social/social.css';

export function ModerationScreen() {
  const {t, date} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const queue = useQuery({queryKey: key('moderation'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/moderation/reports', {signal})});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  if (queue.isPending) return <Skeleton ratio="6 / 1" />;
  if (queue.isError) return <StaffError error={queue.error} onRetry={() => queue.refetch()} />;
  const act = (id: string, action: 'hide' | 'restore' | 'dismiss') => void api.call('post', '/api/v2/admin/moderation/shares/{share_id}', {path: {share_id: id}, body: {action, reason: reasons[id]!.trim()}})
    .then(() => { toast(t('mo.done'), 'success'); return qc.invalidateQueries({queryKey: key('moderation')}); }, fail);
  return <><h2>{t('sf.moderation')}</h2>
    {!queue.data.items.length ? <p className="muted">{t('sf.none')}</p> : <ul className="share-list">{queue.data.items.map(s => <li key={s.id} className="share">
      <header>{s.owner && <PersonChip card={s.owner} />}<span className="tag tag-warn">{t('mo.reports', {n: s.reports})}</span>
        <span className="tag tag-quiet">{s.moderation ?? 'visible'}</span><span className="muted small">{s.first_reported_at && date(s.first_reported_at)}</span></header>
      <p className="small"><strong>{t('mo.reasons')}:</strong> {s.reasons.join(' · ')}</p>
      {s.caption && <p className="share-caption">{s.caption}</p>}
      {s.look && <LookCard look={s.look} owned />}
      <div className="staff-inline">
        <TextField label={t('sf.reason')} value={reasons[s.id] ?? ''} required onChange={e => setReasons(r => ({...r, [s.id]: e.target.value}))} />
        {s.moderation === 'hidden' ? <Button disabled={!reasons[s.id]?.trim()} onClick={() => act(s.id, 'restore')}>{t('mo.restore')}</Button>
          : <Button variant="danger" disabled={!reasons[s.id]?.trim()} onClick={() => act(s.id, 'hide')}>{t('mo.hide')}</Button>}
        <Button variant="ghost" disabled={!reasons[s.id]?.trim()} onClick={() => act(s.id, 'dismiss')}>{t('mo.dismiss')}</Button>
      </div>
    </li>)}</ul>}</>;
}

// Roles the API can grant or revoke (moderator is provisioned by operators, not here).
const ROLES = ['catalogue_editor', 'inventory_manager', 'admin'] as const;
type Role = typeof ROLES[number];

export function RolesScreen() {
  const {t, errorText} = useI18n();
  const {api} = useSession();
  const qc = useQueryClient();
  const key = useStaffKey();
  const fail = useFail();
  const staff = useQuery({queryKey: key('roles'), queryFn: ({signal}) => api.call('get', '/api/v2/admin/staff', {signal})});
  const [handle, setHandle] = useState(''); const [role, setRole] = useState<Role>('catalogue_editor');
  const [error, setError] = useState<string | null>(null);
  const [found, setFound] = useState<{handle: string | null; roles: string[]; capabilities: string[]} | null>(null);
  if (staff.isPending) return <Skeleton ratio="6 / 1" />;
  if (staff.isError) return <StaffError error={staff.error} onRetry={() => staff.refetch()} />;
  const refresh = () => qc.invalidateQueries({queryKey: key('roles')});
  const explain = (e: unknown) => { if (e instanceof ApiFailure && e.status < 500) setError(errorText(e.code, e.message)); else fail(e); };
  const grant = (e: FormEvent) => { e.preventDefault(); setError(null);
    void api.call('put', '/api/v2/admin/staff/{handle}/roles/{role}', {path: {handle: handle.replace(/^@/, ''), role}}).then(() => { toast(t('ro.granted'), 'success'); return refresh(); }, explain); };
  const revoke = (h: string, r: string) => { setError(null);
    void api.call('delete', '/api/v2/admin/staff/{handle}/roles/{role}', {path: {handle: h, role: r as Role}}).then(() => { toast(t('ro.revoked')); return refresh(); }, explain); };
  return <><h2>{t('sf.roles')}</h2>
    {error && <p className="co-alert" role="alert">{error}</p>}
    <table className="staff-table"><thead><tr><th>{t('ro.handle')}</th><th>{t('ro.role')}</th><th>{t('ro.capabilities')}</th></tr></thead>
      <tbody>{staff.data.map(a => <tr key={a.handle ?? a.display_name}><td>{a.handle ? `@${a.handle}` : '—'} <span className="muted small">{a.display_name}</span></td>
        <td>{a.roles.map(r => <span key={r} className="tag tag-quiet role-chip">{r}{a.handle && <button type="button" className="chip-x" aria-label={`${t('ro.revoke')} ${r}`} onClick={() => revoke(a.handle!, r)}>×</button>}</span>)}</td>
        <td className="small">{a.capabilities.join(', ')}</td></tr>)}</tbody></table>
    <form className="staff-inline" onSubmit={grant}>
      <TextField label={t('ro.handle')} required value={handle} onChange={e => setHandle(e.target.value)} />
      <Select label={t('ro.role')} value={role} onChange={e => setRole(e.target.value as Role)}>{ROLES.map(r => <option key={r} value={r}>{r}</option>)}</Select>
      <Button onClick={() => { setError(null); void api.call('get', '/api/v2/admin/staff/{handle}', {path: {handle: handle.replace(/^@/, '')}}).then(setFound, explain); }} disabled={!handle.trim()}>{t('ro.lookup')}</Button>
      <Button type="submit" variant="primary">{t('ro.grant')}</Button>
    </form>
    {found && <p className="muted small" role="status">@{found.handle}: {found.roles.join(', ') || '—'} · {found.capabilities.join(', ') || '—'}</p>}</>;
}

export function OpsScreen() {
  const {t} = useI18n();
  const {api} = useSession();
  const key = useStaffKey();
  const ops = useQuery({queryKey: key('ops'), refetchInterval: 30_000, queryFn: ({signal}) => api.call('get', '/api/v2/admin/ops', {signal})});
  const ready = useQuery({queryKey: key('ready'), refetchInterval: 30_000, retry: false, queryFn: ({signal}) => api.call('get', '/api/v2/health/ready', {signal, anonymous: true})});
  if (ops.isPending) return <Skeleton ratio="6 / 1" />;
  if (ops.isError) return <StaffError error={ops.error} onRetry={() => ops.refetch()} />;
  const o = ops.data;
  const rows: Array<[string, string]> = [
    [t('op.ready'), ready.isSuccess ? t('op.readyOk') : ready.isError ? String((ready.error as Error).message) : '…'],
    [t('op.schema'), o.schema_head], [t('op.model'), o.model_mode], [t('op.artifact'), o.active_artifact ?? '—'],
    [t('op.claims', {h: o.window_hours}), t('op.claimsDetail', {ok: o.claims_succeeded, fail: o.claim_failures, all: o.claim_attempts})],
    [t('op.outbox'), t('op.outboxDetail', {pending: o.outbox_pending, failing: o.outbox_failing})], [t('op.imports'), String(o.import_jobs_running)],
    [t('op.rateLimited'), Object.entries(o.rate_limited_since_start).map(([k, v]) => `${k} ${v}`).join(' · ') || '0'],
  ];
  return <><h2>{t('sf.ops')}</h2><dl className="product-facts">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></>;
}
