import { ArenaChallengePage } from './ArenaChallengePage';
import type { Locale } from './i18n';
import type { PersonalArenaContext } from './premiere.mjs';

/** Lives only inside the mounted Premiere. No IDs, media, storage or record callbacks. */
export function PersonalArenaChallenge({ context, locale, onBack, onReport }: {
  context: PersonalArenaContext; locale: Locale; onBack: () => void; onReport: () => void;
}) {
  const zh = locale === 'zh-CN';
  return <section data-personal-arena="SIMULATED_ONLY" className="personal-arena">
    <div className="personal-arena-history" role="note"><h4>{zh ? '真实记录来源（手工，未独立核验）' : 'Historical record source (manual, unverified)'}</h4>
      <p>{zh ? '第' : 'Point '}{context.point_index}{zh ? '分后' : ' completed'} · 9:9 · {context.completeness === 'GAME_COMPLETE' ? (zh ? '记录内本局完成' : 'Recorded game complete') : (zh ? '记录进行中' : 'Record in progress')}</p>
      <p>{zh ? '下方是独立的假设战术模拟。比分不证明真实打法、旋转、落点或得失分原因。选择不会写回比赛、报告或 Journal；不会传入身份或视频。' : 'Below is a separate hypothetical tactic simulation. Scores do not prove actual strokes, spin, placement or causes. Choices never write to the match, report or Journal. No identity or video is passed.'}</p>
      <button type="button" onClick={onReport}>{zh ? '回到个人报告' : 'Return to personal report'}</button>
    </div>
    <ArenaChallengePage locale={locale} onBack={onBack} />
  </section>;
}
