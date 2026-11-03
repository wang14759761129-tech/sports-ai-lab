import type { PersonalMatchReport } from './personal-match-report.mjs';
import type { Locale } from './i18n';

/** Uses existing report calculations only. No inference, storage, IDs, media or timestamps. */
export function createTrainingAction(report: PersonalMatchReport, questionId: string | null, locale: Locale) {
  if (report.schema !== 'ptti.personal-match-report/0.1'
    || !['USER_MANUAL', 'SIMULATED_DEMO'].includes(report.source.type)) return null;
  const q = report.training_questions.find(row => row.question_id === questionId);
  if (!q) return null;
  const zh = locale === 'zh-CN';
  let basis = '', question = '', action = '', verify = '';
  let range: { first_point: number; last_point: number } | null = null;
  if (q.kind === 'KEY_SCORE_RANGE') {
    range = { first_point: q.first_point, last_point: q.last_point };
    basis = zh ? `第 ${q.first_point}–${q.last_point} 分，N=${q.sample_count}；A 得 ${q.player_a_won} 分，B 得 ${q.player_b_won} 分。` : `Points ${q.first_point}–${q.last_point}, N=${q.sample_count}; A won ${q.player_a_won}, B won ${q.player_b_won}.`;
    const score = q.stage_id === 'AFTER_7_7' ? '7:7' : q.stage_id === 'AFTER_9_9' ? '9:9' : '10:10';
    question = zh ? `从 ${score} 开始，接下来每分有哪些可直接记录的信息？` : `Starting at ${score}, what can you directly record about each following point?`;
    action = zh ? `下一次训练做一段从 ${score} 开始的模拟计分练习。逐分记得分方与确认的发球方，不确定则保留未知；与本段记录分别保存。` : `In the next practice, play a simulated scoring sequence from ${score}. Log point winners and confirmed servers; leave uncertainty unknown. Keep it separate from this record.`;
    verify = zh ? '核对每分累计比分及发球轮换，统计实际样本数；只比较观察结果，不据此断言技术进步或原因。' : 'Check cumulative scores and service rotation; count actual samples. Compare observations without claiming technical improvement or causes.';
  } else if (q.kind === 'SCORING_RUN') {
    range = { first_point: q.first_point, last_point: q.last_point };
    basis = zh ? `${q.side === 'PLAYER_A' ? 'A' : 'B'} 在第 ${q.first_point}–${q.last_point} 分连续得 ${q.length} 分（对方同期失分）。` : `${q.side === 'PLAYER_A' ? 'A' : 'B'} won ${q.length} consecutive points at points ${q.first_point}–${q.last_point} (opponent lost those points).`;
    question = zh ? '这段连续得失分中，哪些情境确实有记录，哪些原因还不知道？' : 'Which situations in this run are actually recorded, and which causes remain unknown?';
    action = zh ? '下一次练习逐分记录；出现连续得失分时标记起止分序，练习后与教练回顾可观察事实。没有录像或技术标注时不补写原因。' : 'Log each point next practice. Mark the start and end of scoring runs, then review observable facts with a coach. Do not fill in causes without video or technical annotations.';
    verify = zh ? '按分序重新累计，检查连续得分是否被对方得分中断；记录长度、样本量和未知信息。' : 'Recount the point sequence and check where the opponent interrupted the run. Record length, sample size and unknown information.';
  } else if (q.kind === 'SERVE_RECEIVE') {
    const stats = report.calculated_results.serve_receive;
    if (stats.status !== 'AVAILABLE' || !stats.players) return null;
    basis = (['PLAYER_A','PLAYER_B'] as const).map(side => {
      const s = stats.players![side];
      return `${side === 'PLAYER_A' ? 'A' : 'B'} · ${zh ? '发球' : 'serve'} ${s.serve.won}/${s.serve.total} · ${zh ? '接发' : 'receive'} ${s.receive.won}/${s.receive.total}`;
    }).join('; ');
    question = zh ? '在确认发球方的记录中，发球与接发球样本是否足够继续观察？' : 'Are the confirmed serve and receive samples sufficient for further observation?';
    action = zh ? '下一局先确认首发球方，逐分核对轮换并记录得分方；分别统计双方发球与接发球得失分。有未知发球方时只记数量，不输出比例。' : 'Next game, confirm the first server, check rotation and log every winner. Count serve and receive outcomes separately for both players. If any server is unknown, keep counts only and do not report rates.';
    verify = zh ? '先核对轮换合法、逐分完整和本局结束，再检查分子与分母；样本少时继续观察，不诊断发球技术。' : 'Check legal rotation, complete point coverage and game completion before reviewing numerators and denominators. Keep observing small samples; do not diagnose serve technique.';
  } else {
    basis = zh ? `已记录 ${q.sample_count} 分，但没有可信的旋转、落点或板数标注。` : `${q.sample_count} points recorded, without reliable spin, placement or stroke-count annotations.`;
    question = zh ? '下一次可以可靠补记哪一个可观察字段？' : 'Which observable field could you reliably annotate next time?';
    action = zh ? '与教练选择一个能直接观察的字段，在自己的获准录像或现场训练中人工记录；不确定时标未知，不用比分猜测。' : 'With a coach, choose one directly observable field to log manually in authorized personal footage or live practice. Mark uncertainty unknown; never infer it from scores.';
    verify = zh ? '复核该字段的已确认样本数与未知数；有分歧时保留未核验，不把新增标注当成独立证明。' : 'Review confirmed and unknown sample counts. Keep disputed labels unverified; extra annotations are not independent proof.';
  }
  return { schema: 'ptti.training-observation-action/0.1', locale, source: report.source.type,
    verification: report.confirmation_status, scope: report.media_scope,
    evidence: { report_schema: report.schema, question_id: q.question_id, kind: q.kind, sample_count: q.sample_count, point_range: range, basis },
    observation_question: question, next_training_action: action, verification_method: verify,
    limitations: zh ? '仅为训练观察计划。比分不能证明旋转、落点、动作、前三板质量、心理状态或因果；不含视频时间边界。' : 'Training observation plan only. Scores do not establish spin, placement, technique, first-three-ball quality, mental state or causes. No video time boundaries.',
    simulated: report.source.type === 'SIMULATED_DEMO', auto_saved: false, public_match_id: null, video_source_id: null };
}
export type TrainingAction = NonNullable<ReturnType<typeof createTrainingAction>>;
export function formatTrainingAction(plan: TrainingAction) {
  const zh = plan.locale === 'zh-CN';
  return [plan.simulated ? 'SIMULATED DEMO · NOT A REAL MATCH' : 'MANUAL USER RECORD · NOT INDEPENDENTLY VERIFIED',
    `${zh ? '实际依据 / 计算结果' : 'EVIDENCE / CALCULATED RESULT'}: ${plan.evidence.basis}`,
    `${zh ? '观察问题' : 'OBSERVATION QUESTION'}: ${plan.observation_question}`,
    `${zh ? '下次训练行动' : 'NEXT TRAINING ACTION'}: ${plan.next_training_action}`,
    `${zh ? '验证办法' : 'VERIFICATION METHOD'}: ${plan.verification_method}`,
    `${zh ? '证据限制' : 'LIMITATIONS'}: ${plan.limitations}`].join('\n\n');
}
