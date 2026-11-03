import { Component, lazy, Suspense } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import type { AthletePortrait as Portrait } from './MediaAsset';
import type { Locale } from './i18n';

const LoadedPortrait = lazy(() => import('./MediaAsset').then(module => ({ default: module.AthletePortrait })));
type BoundaryProps = { children: ReactNode; fallback: ReactNode; locale: Locale };
export class PortraitLoadBoundary extends Component<BoundaryProps, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <>{this.props.fallback}<p role="status">{this.props.locale === 'zh-CN' ? '照片暂不可用，继续显示 PTTI 原创视觉。' : 'Photo unavailable. Showing original PTTI artwork.'}</p></> : this.props.children;
  }
}
/** Only invoked by the already-authorized athlete detail surface. Rights logic stays in MediaAsset. */
export function AthletePortrait({ locale, ...props }: ComponentProps<typeof Portrait> & { locale: Locale }) {
  return <PortraitLoadBoundary key={props.athleteId} locale={locale} fallback={props.fallback}>
    <Suspense fallback={<>{props.fallback}<span className="portrait-load-status" role="status">{locale === 'zh-CN' ? '正在载入球员照片…' : 'Loading athlete photo…'}</span></>}>
      <LoadedPortrait {...props} />
    </Suspense>
  </PortraitLoadBoundary>;
}
