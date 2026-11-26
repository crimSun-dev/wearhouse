import {useEffect, useRef, useState} from 'react';
import {ScanLine} from 'lucide-react';
import {useI18n} from '../i18n/index.tsx';
import {Button} from './ui.tsx';

type Detector = {detect: (source: CanvasImageSource) => Promise<Array<{rawValue: string}>>};
type DetectorCtor = new (opts: {formats: string[]}) => Detector;

/** Camera QR scanner (BarcodeDetector over HTTPS or localhost). `onCode` returns true to stop scanning. */
export function QrScanner({onCode, label}: {onCode: (raw: string) => boolean; label?: string}) {
  const {t} = useI18n();
  const Ctor = (window as unknown as {BarcodeDetector?: DetectorCtor}).BarcodeDetector;
  const supported = !!Ctor && window.isSecureContext && !!navigator.mediaDevices?.getUserMedia;
  const [on, setOn] = useState(false);
  const [denied, setDenied] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const handler = useRef(onCode);
  handler.current = onCode;
  useEffect(() => {
    if (!on || !Ctor) return;
    let stream: MediaStream | null = null;
    let raf = 0;
    let stopped = false;
    const detector = new Ctor({formats: ['qr_code']});
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
        if (stopped || !video.current) return;
        video.current.srcObject = stream;
        // Do not block detection on play(): some streams resolve it late or never.
        void video.current.play().catch(() => {});
        const tick = async () => {
          if (stopped || !video.current) return;
          const codes = await detector.detect(video.current).catch(() => []);
          if (codes[0] && handler.current(codes[0].rawValue)) { setOn(false); return; }
          raf = requestAnimationFrame(() => void tick());
        };
        void tick();
      } catch { setDenied(true); setOn(false); }
    })();
    return () => { stopped = true; cancelAnimationFrame(raf); stream?.getTracks().forEach(track => track.stop()); };
  }, [on, Ctor]);
  if (!supported) return <p className="muted small">{t('tag.noCamera')}</p>;
  return <div className="tag-scanner">
    {denied && <p className="muted small" role="status">{t('tag.cameraDenied')}</p>}
    {on && <><video ref={video} className="tag-video" muted playsInline aria-label={t('tag.scanning')} />
      <p className="muted small">{t('tag.scanning')}</p></>}
    <Button onClick={() => { setDenied(false); setOn(o => !o); }}><ScanLine size={18} aria-hidden /> {on ? t('tag.stopScan') : label ?? t('tag.scan')}</Button>
  </div>;
}
