import { useId, useRef, useState } from 'react';
import type { ReactNode, Ref } from 'react';
import { message } from './i18n';
import type { Locale } from './i18n';

type TheaterProps = {
  locale: Locale; sourceId: string; onBack: () => void; main: ReactNode; secondary: ReactNode;
};

/** A non-modal presentation mode, keyed by source in Watch. It owns no media session. */
export function PrivateTheaterFrame(props: TheaterProps) {
  const [focused, setFocused] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const secondaryId = useId();
  function exitFocus() {
    setFocused(false);
    toggle.current?.focus({ preventScroll: true });
  }
  return <PrivateTheaterView {...props} focused={focused} toggleRef={toggle} secondaryId={secondaryId} onExitFocus={exitFocus} onToggleFocus={() => focused ? exitFocus() : setFocused(true)} />;
}

export function PrivateTheaterView({ locale, sourceId, onBack, main, secondary, focused, toggleRef, secondaryId, onExitFocus, onToggleFocus }: TheaterProps & {
  focused: boolean; toggleRef?: Ref<HTMLButtonElement>; secondaryId: string; onExitFocus: () => void; onToggleFocus: () => void;
}) {
  const t = (key: Parameters<typeof message>[1]) => message(locale, key);
  return <section className="fan-watch-detail private-theater" aria-labelledby="fan-watch-title" data-fan-watch-detail data-theater-source-id={sourceId} data-theater-focus={focused}
    onKeyDown={(event) => { if (focused && event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); onExitFocus(); } }}>
    <div className="theater-toolbar">
      <button type="button" className="button button-outline" onClick={onBack}>← {t('theater.backContext')}</button>
      <span className="theater-brand">PTTI · PRIVATE THEATER</span>
      <button ref={toggleRef} type="button" className="button button-outline" aria-pressed={focused} aria-controls={secondaryId} onClick={onToggleFocus}>{t(focused ? 'theater.exitFocus' : 'theater.enterFocus')}</button>
    </div>
    <p className="theater-mode-notice" role="status">{t(focused ? 'theater.focusNotice' : 'theater.welcome')}</p>
    {main}
    <div id={secondaryId} className="theater-secondary" hidden={focused}>{secondary}</div>
  </section>;
}
