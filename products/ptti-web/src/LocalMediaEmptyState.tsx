import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';

export function LocalMediaEmptyState({ locale, simulated, onSelect, onCinema }: {
  locale: Locale; simulated: boolean; onSelect: () => void; onCinema?: () => void;
}) {
  const t = (key: MessageKey) => message(locale, key);
  return <>
    <span className="eyebrow">{simulated ? 'SIMULATED_ONLY · INSIGHT' : 'PTTI CINEMA · LOCAL VIDEO'}</span>
    <h2>{t(simulated ? 'pro.media.demoTitle' : 'cinema.stage.title')}</h2>
    <p data-simulated-no-video={simulated || undefined}>{t(simulated ? 'pro.media.demoNoVideo' : 'cinema.stage.description')}</p>
    <div className="local-media-empty-actions">
      <button type="button" className="button button-primary" data-load-local-media onClick={onSelect}>{t('pro.video.selectFile')}</button>
      {simulated && onCinema && <button type="button" className="button button-secondary" data-return-cinema onClick={onCinema}>{t('pro.media.returnCinema')}</button>}
    </div>
    <small>{t(simulated ? 'pro.media.demoBinding' : 'cinema.stage.noMedia')}</small>
  </>;
}
