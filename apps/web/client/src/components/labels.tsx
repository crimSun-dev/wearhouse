import {CloudRain, Sun, Thermometer, CloudOff} from 'lucide-react';
import {useI18n} from '../i18n/index.tsx';
import type {MessageKey} from '../i18n/en.ts';

export function SimulatedLabel() {
  const {t} = useI18n();
  return <span className="tag tag-quiet">{t('label.simulated')}</span>;
}

export function ModelLabel({mode}: {mode: string | null | undefined}) {
  const {t} = useI18n();
  return <span className="tag tag-quiet" title={mode ?? undefined}>{mode === 'trained' ? t('label.trained') : t('label.baseline')}</span>;
}

/** Weather source chip: always names its source and credits BMKG when forecast data is shown. */
export function WeatherChip({source, temp, rain, hot, fetchedAt, compact}: {
  source: string; temp?: number | null; rain?: boolean | null; hot?: boolean | null; fetchedAt?: string | null; compact?: boolean;
}) {
  const {t, time} = useI18n();
  const known = source === 'LIVE' || source === 'CACHED' || source === 'MANUAL';
  const key = (`weather.${source}` as MessageKey);
  return <span className={`weather-chip ${known ? '' : 'is-muted'}`}>
    {known ? (rain ? <CloudRain size={16} aria-hidden /> : hot ? <Sun size={16} aria-hidden /> : <Thermometer size={16} aria-hidden />)
      : <CloudOff size={16} aria-hidden />}
    {temp != null && <b>{Math.round(temp)} °C</b>}
    {rain != null && known && <span>{rain ? t('weather.rain') : t('weather.dry')}</span>}
    {hot && known && <span>{t('weather.hot')}</span>}
    <span className="weather-source">{t(key)}{fetchedAt && !compact ? ` · ${t('weather.fetched', {time: time(fetchedAt)})}` : ''}</span>
    {(source === 'LIVE' || source === 'CACHED') && <span className="weather-credit">{t('weather.credit')}</span>}
  </span>;
}
