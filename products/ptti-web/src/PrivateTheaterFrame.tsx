import { useId, useRef, useState } from 'react';
import type { ReactNode, Ref } from 'react';
import { message } from './i18n';
import type { Locale } from './i18n';

export type TheaterPresentation = { focused: boolean; mode: 'cinema' | 'fan' | 'intelligence'; panelVisible: boolean; ratio: 'wide' | 'balanced'; position: 'after' | 'before' };
export function theaterPresentation(input?: Partial<TheaterPresentation>): TheaterPresentation {
  return { focused: input?.focused === true, mode: input?.mode === 'cinema' || input?.mode === 'intelligence' ? input.mode : 'fan', panelVisible: input?.panelVisible !== false,
    ratio: input?.ratio === 'balanced' ? 'balanced' : 'wide', position: input?.position === 'before' ? 'before' : 'after' };
}
type TheaterProps = {
  locale: Locale; sourceId: string; onBack: () => void; main: ReactNode; secondary: ReactNode; intelligence?: ReactNode; presentation?: TheaterPresentation; onPresentationChange?: (value: TheaterPresentation) => void;
};

/** A non-modal presentation mode, keyed by source in Watch. It owns no media session. */
export function PrivateTheaterFrame(props: TheaterProps) {
  const [presentation, setPresentation] = useState(theaterPresentation(props.presentation));
  const { focused, mode, panelVisible, ratio, position } = presentation;
  const currentPresentation = useRef(presentation); currentPresentation.current = presentation;
  function update(patch: Partial<TheaterPresentation>) {
    const next = theaterPresentation({ ...currentPresentation.current, ...patch });
    currentPresentation.current = next; setPresentation(next); props.onPresentationChange?.(next);
  }
  const zh = props.locale === 'zh-CN';
  const toggle = useRef<HTMLButtonElement>(null);
  const secondaryId = useId();
  const modeDescriptionId = useId();
  const boothHelpId = useId();
  const focusActive = focused || mode === 'cinema';
  function exitFocus() {
    update({ focused: false, ...(mode === 'cinema' ? { mode: 'fan' } : {}) });
    toggle.current?.focus({ preventScroll: true });
  }
  const content = <div className="theater-workspace" data-layout-mode={mode} data-panel-ratio={ratio} data-panel-position={position} data-panel-visible={panelVisible && !focused}>
    <div className="theater-director" role="group" aria-label={zh ? '观看布局' : 'Viewing layout'}>
      {(['cinema', 'fan', 'intelligence'] as const).map(value => <button type="button" key={value} aria-pressed={mode === value} aria-describedby={modeDescriptionId} title={zh ? (value === 'cinema' ? '影院：专注官方来源入口' : value === 'fan' ? '球迷：赛事与相关内容' : '证据：只显示当前可用资料') : (value === 'cinema' ? 'Cinema: focus on the official viewing entry' : value === 'fan' ? 'Fan: match and related content' : 'Intelligence: available evidence only')} onClick={() => update({ mode: value, focused: false })}>{value === 'cinema' ? 'Cinema' : value === 'fan' ? 'Fan' : 'Intelligence'}</button>)}
      <details className="theater-booth"><summary>Director’s Booth · {zh ? '布局控制' : 'Layout controls'}</summary><div className="theater-booth-controls">
      <label><input type="checkbox" disabled={focusActive} aria-describedby={boothHelpId} checked={panelVisible} onChange={event => update({ panelVisible: event.target.checked })} />{zh ? '资料面板' : 'Source panel'}</label>
      <label>{zh ? '布局比例' : 'Layout ratio'} <select disabled={focusActive || mode !== 'intelligence' || !panelVisible} aria-describedby={boothHelpId} value={ratio} onChange={event => update({ ratio: event.target.value === 'balanced' ? 'balanced' : 'wide' })}><option value="wide">{zh ? '宽屏优先' : 'Wide main'}</option><option value="balanced">{zh ? '均衡' : 'Balanced'}</option></select></label>
      <label>{zh ? '面板位置' : 'Panel position'} <select disabled={focusActive || mode !== 'intelligence' || !panelVisible} aria-describedby={boothHelpId} value={position} onChange={event => update({ position: event.target.value === 'before' ? 'before' : 'after' })}><option value="after">{zh ? '右侧 / 下方' : 'Right / below'}</option><option value="before">{zh ? '左侧 / 下方' : 'Left / below'}</option></select></label>
      <p id={boothHelpId} className="theater-booth-hint">{focusActive ? (zh ? '专注模式已隐藏资料面板；退出专注后可调整。' : 'Focus mode hides the source panel. Exit focus to adjust it.') : (zh ? '面板比例与位置仅在 Intelligence 模式生效；窄窗口自动排在内容下方。' : 'Ratio and position apply in Intelligence mode; narrow windows place the panel below the content.')}</p>
      <button type="button" className="theater-reset" onClick={() => update(theaterPresentation())}>{zh ? '恢复默认布局' : 'Reset layout'}</button>
      </div></details>
      <span id={modeDescriptionId} role="status" aria-live="polite">{zh ? `当前：${mode === 'cinema' ? '影院' : mode === 'fan' ? '球迷' : '证据'}模式。只调整布局，官方视频仍在原站观看。` : `${mode === 'cinema' ? 'Cinema' : mode === 'fan' ? 'Fan' : 'Intelligence'} mode. Layout only; official video stays on its original platform.`}</span>
    </div>
    <div className="theater-layout">
      <div className="theater-main">{props.main}</div>
      <aside className="theater-intelligence" hidden={mode !== 'intelligence' || focused || !panelVisible} aria-label="Intelligence"><h2>Intelligence</h2>{props.intelligence ?? <p>{zh ? '暂无已核实逐分数据。' : 'No verified point data available.'}</p>}</aside>
    </div>
  </div>;
  return <PrivateTheaterView {...props} main={content} focused={focused || mode === 'cinema'} toggleRef={toggle} secondaryId={secondaryId} secondaryHidden={focused || mode === 'cinema' || !panelVisible} onExitFocus={exitFocus} onToggleFocus={() => focused || mode === 'cinema' ? exitFocus() : update({ focused: true })} />;
}

export function PrivateTheaterView({ locale, sourceId, onBack, main, secondary, focused, toggleRef, secondaryId, onExitFocus, onToggleFocus, secondaryHidden }: TheaterProps & {
  focused: boolean; secondaryHidden?: boolean; toggleRef?: Ref<HTMLButtonElement>; secondaryId: string; onExitFocus: () => void; onToggleFocus: () => void;
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
    <div id={secondaryId} className="theater-secondary" hidden={secondaryHidden ?? focused}>{secondary}</div>
  </section>;
}
