import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { message } from './i18n';
import type { Locale, MessageKey } from './i18n';
import {
  createQuickAnnotationInput,
  createQuickPointId,
  importQuickAnnotationDraft,
  nextUnannotatedPointNumber,
  suggestedLocalServerForPoint,
  summarizeLocalQuickPoints,
  validateQuickAnnotationPoint,
} from './local-video-review.mjs';
import type { ImportedQuickAnnotationDraft, LocalGameContext, LocalVideoPlayer, LocalVideoPoint, LocalVideoSession, QuickTactics } from './local-video-review.mjs';
import {
  LocalVideoPlaybackController,
} from '@ptti/playback-core';
import type {
  PlaybackSnapshot,
  RallyPlaybackBinding,
  RallyPlaylistTask,
} from '@ptti/playback-core';
import { toRallyPlaybackBinding, playbackIssueMessageKey } from './playback-adapter.mjs';
import { OBSERVED_LOSS_STAGES, summarizeObservedLosses } from './local-loss-insights.mjs';
import type { ObservedLossFilter } from './local-loss-insights.mjs';
import { prepareQuickSource, validateReviewTargets, matchesQuickSource } from './review-targets.mjs';
import type { QuickSource } from './review-targets.mjs';
import type { ReviewTargetsV01 } from './contracts/review-targets-v0.1';
import { createReviewComparisonExport } from './review-comparison.mjs';
import { CinemaDemo } from './CinemaDemo';

type SaveState = 'idle' | 'dirty' | 'saved' | 'invalid';
type AnnotationPass = 'score' | 'review';
type TacticalField = 'serve_side' | 'serve_length' | 'third_ball_attack';
type BoundaryField = 'start_seconds' | 'end_seconds';
type BoundaryPoint = LocalVideoPoint & {
  bound_video_identity: string;
  start_confirmed: boolean;
  end_confirmed: boolean;
  end_auto_suggested?: boolean;
};

const playerValues: LocalVideoPlayer[] = ['PLAYER_A', 'PLAYER_B', 'UNKNOWN'];
const tacticValues: Record<TacticalField, readonly string[]> = {
  serve_side: ['forehand', 'backhand', 'unknown'],
  serve_length: ['short', 'half_long', 'long', 'unknown'],
  third_ball_attack: ['yes', 'no', 'unknown'],
};
const unknownTactics: QuickTactics = {
  serve_side: 'unknown',
  serve_length: 'unknown',
  third_ball_attack: 'unknown',
};

function localPointLabel(locale: Locale, point: LocalVideoPoint) {
  return locale === 'zh-CN' ? `第 ${point.game_number} 局 · 第 ${point.point_number} 分` : `Game ${point.game_number} · Point ${point.point_number}`;
}

function formatTime(seconds: number | null, unknownLabel = 'UNKNOWN') {
  if (seconds === null || !Number.isFinite(seconds)) return unknownLabel;
  const safe = Math.max(0, seconds);
  const minutes = Math.floor(safe / 60);
  const remainder = (safe % 60).toFixed(2).padStart(5, '0');
  return `${String(minutes).padStart(2, '0')}:${remainder}`;
}

function roundToMillisecond(seconds: number) {
  return Math.round(seconds * 1000) / 1000;
}

function defaultGameContext(gameNumber: number): LocalGameContext {
  return { game_number: gameNumber, coverage: 'PARTIAL_OR_UNKNOWN', first_server: 'UNKNOWN' };
}

function emptyPlaybackSnapshot(): PlaybackSnapshot {
  return {
    status: 'empty', video_identity: null, file: null, duration_seconds: null,
    current_time_seconds: 0, is_playing: false, playback_rate: 1, error: null, playlist: null,
  };
}

function mediaIssueKey(code: string): MessageKey | '' {
  return playbackIssueMessageKey(code);
}

export function LocalVideoReview({ locale, active = true, onBrowseMatches, onOpenInsight }: { locale: Locale; active?: boolean; onBrowseMatches?: () => void; onOpenInsight?: () => void }) {
  const t = (key: MessageKey, values?: Record<string, string | number>) => Object.entries(values ?? {}).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    message(locale, key),
  );
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pointFormRef = useRef<HTMLFormElement | null>(null);
  const controllerRef = useRef<LocalVideoPlaybackController | null>(null);
  const pendingFileRef = useRef<File | null>(null);
  const nextSessionIdRef = useRef<string | null>(null);
  const activeSessionIdRef = useRef('');
  const playlistTaskRef = useRef<RallyPlaylistTask | null>(null);
  const pointCreationOrderRef = useRef<string[]>([]);
  const [session, setSession] = useState<LocalVideoSession | null>(null);
  const [importedDraft, setImportedDraft] = useState<ImportedQuickAnnotationDraft['identity'] | null>(null);
  const [points, setPoints] = useState<BoundaryPoint[]>([]);
  const [draft, setDraft] = useState<BoundaryPoint | null>(null);
  const [annotationPass, setAnnotationPass] = useState<AnnotationPass>('score');
  const [selectedPointId, setSelectedPointId] = useState('');
  const [selectedPlaylistIds, setSelectedPlaylistIds] = useState<string[]>([]);
  const [observer, setObserver] = useState<'PLAYER_A' | 'PLAYER_B'>('PLAYER_A');
  const [lossFilter, setLossFilter] = useState<ObservedLossFilter | null>(null);
  const quickSourceRef = useRef<QuickSource | null>(null);
  const quickImportGenerationRef = useRef(0);
  const targetsRef = useRef<ReviewTargetsV01 | null>(null);
  const targetsImportGenerationRef = useRef(0);
  const [targets, setTargets] = useState<ReviewTargetsV01 | null>(null);
  const [targetsStale, setTargetsStale] = useState(false);
  const [targetsIssue, setTargetsIssue] = useState('');
  const [insightMode, setInsightMode] = useState<'basic' | 'targets'>('basic');
  const [targetFilter, setTargetFilter] = useState<string | null>(null);
  const [comparisonNote, setComparisonNote] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => { if (!active) { cancelPlaylist(); controllerRef.current?.pause(); } }, [active]);
  useEffect(() => { setComparisonNote(''); }, [session?.session_id]);
  const [autoPauseOnAnnotate, setAutoPauseOnAnnotate] = useState(true);
  const [activeGameNumber, setActiveGameNumber] = useState(1);
  const [gameContexts, setGameContexts] = useState<Record<number, LocalGameContext>>({ 1: defaultGameContext(1) });
  const [playbackSnapshot, setPlaybackSnapshot] = useState<PlaybackSnapshot>(emptyPlaybackSnapshot);
  const [fileIssueKey, setFileIssueKey] = useState<MessageKey | ''>('');
  const [playlistIssueKey, setPlaylistIssueKey] = useState<MessageKey | ''>('');
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveIssue, setSaveIssue] = useState('');
  const [exported, setExported] = useState(false);
  const [draftImportIssue, setDraftImportIssue] = useState<MessageKey | ''>('');
  const [draftImportStatus, setDraftImportStatus] = useState<MessageKey | ''>('');

  const hasSession = Boolean(session);
  useEffect(() => {
    if (!hasSession || !videoRef.current) return undefined;
    const controller = new LocalVideoPlaybackController(videoRef.current, {
      createVideoIdentity: () => {
        const identity = nextSessionIdRef.current;
        nextSessionIdRef.current = null;
        return identity ?? `local-session:${crypto.randomUUID()}`;
      },
    });
    controllerRef.current = controller;
    let disposed = false;
    const unsubscribe = controller.subscribe((snapshot) => {
      if (disposed) return;
      setPlaybackSnapshot(snapshot);
      const activeIdentity = activeSessionIdRef.current;
      if (snapshot.video_identity && snapshot.video_identity === activeIdentity) {
        setCurrentTimeFromSnapshot(snapshot.current_time_seconds);
        setSession((current) => current?.session_id === activeIdentity
          ? {
            ...current,
            media_status: snapshot.status === 'ready' ? 'ready' : snapshot.status === 'error' ? 'error' : 'loading',
            duration_seconds: snapshot.duration_seconds,
          }
          : current);
      }
      if (snapshot.status === 'ready') setFileIssueKey('');
      if (snapshot.error) setFileIssueKey(mediaIssueKey(snapshot.error.code));
    });

    const pendingFile = pendingFileRef.current;
    if (pendingFile) {
      pendingFileRef.current = null;
      const result = controller.loadFile(pendingFile);
      if (!result.ok) {
        activeSessionIdRef.current = '';
        setSession(null);
        setFileIssueKey(mediaIssueKey(result.error.code));
      }
    }
    return () => {
      disposed = true;
      const task = playlistTaskRef.current;
      playlistTaskRef.current = null;
      task?.cancel();
      unsubscribe();
      controller.release();
      if (controllerRef.current === controller) controllerRef.current = null;
      setPlaybackSnapshot(emptyPlaybackSnapshot());
    };
  }, [hasSession]);

  useEffect(() => {
    if (!draft) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const form = pointFormRef.current;
      if (!form) return;
      const rect = form.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > window.innerHeight) form.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [draft?.point_id]);

  const mediaReady = Boolean(session && playbackSnapshot.status === 'ready' && playbackSnapshot.video_identity === session.session_id);
  const durationMs = Number.isFinite(playbackSnapshot.duration_seconds) && (playbackSnapshot.duration_seconds ?? 0) > 0
    ? Math.round((playbackSnapshot.duration_seconds ?? 0) * 1000)
    : null;
  const draftIsSaved = Boolean(draft && points.some((point) => point.point_id === draft.point_id));
  const activeGameContext = gameContexts[activeGameNumber] ?? defaultGameContext(activeGameNumber);
  const quickInput = session && mediaReady && points.length > 0
    ? createQuickAnnotationInput(session, points, gameContexts)
    : null;
  const playbackBindings = new Map<string, RallyPlaybackBinding>();
  if (quickInput?.ok && session) {
    for (const contractPoint of quickInput.value.points) {
      const point = points.find((candidate) => candidate.point_id === contractPoint.point_id);
      if (!point) continue;
      playbackBindings.set(contractPoint.point_id, toRallyPlaybackBinding(contractPoint, {
        current_video_identity: playbackSnapshot.video_identity,
        bound_video_identity: point.bound_video_identity,
        duration_seconds: playbackSnapshot.duration_seconds,
        start_confirmed: point.start_confirmed,
        end_confirmed: point.end_confirmed,
      }));
    }
  }
  const reviewablePoints = points.filter((point) => playbackBindings.get(point.point_id)?.binding_status === 'BOUND');
  const pointCounts = summarizeLocalQuickPoints(points, reviewablePoints.map((point) => point.point_id));
  const lossInsights = summarizeObservedLosses(points, activeGameNumber, observer, reviewablePoints.map((point) => point.point_id));
  const filteredLosses = lossFilter ? (lossFilter === 'ALL' ? lossInsights.all : lossInsights.stages[lossFilter]) : null;
  const targetsActive = Boolean(targets && !targetsStale && quickSourceRef.current && targetsRef.current === targets && matchesQuickSource(quickSourceRef.current, points, gameContexts));
  const activeTarget = targetsActive ? targets?.review_targets.find((target) => target.target_id === targetFilter) : undefined;
  const targetAthlete = targetsActive ? targets?.athletes.find((athlete) => athlete.role === (observer === 'PLAYER_A' ? 'player' : 'opponent')) : undefined;
  const visiblePoints = insightMode === 'targets' ? activeTarget ? points.filter((point) => activeTarget.point_ids.includes(point.point_id)) : points : filteredLosses ? points.filter((point) => filteredLosses.loss_point_ids.includes(point.point_id)) : points;
  const sampleLabel = (count: number) => count === 0 ? `${t('pro.video.unknown')} (0/${pointCounts.total_points})` : `${count}/${pointCounts.total_points}`;
  const suggestedServer = draft
    ? suggestedLocalServerForPoint(gameContexts[draft.game_number], draft.point_number)
    : 'UNKNOWN';

  function setCurrentTimeFromSnapshot(seconds: number) {
    setPlaybackSnapshot((current) => current.current_time_seconds === seconds ? current : { ...current, current_time_seconds: seconds });
  }

  function readCurrentVideoTime() {
    const currentTime = videoRef.current?.currentTime;
    return typeof currentTime === 'number' && Number.isFinite(currentTime) ? currentTime : playbackSnapshot.current_time_seconds;
  }

  function cancelPlaylist(clearSelection = true) {
    const task = playlistTaskRef.current;
    playlistTaskRef.current = null;
    task?.cancel();
    if (clearSelection) setSelectedPlaylistIds([]);
  }

  function resetPageAnnotations() {
    invalidateTargets();
    setLossFilter(null);
    pointCreationOrderRef.current = [];
    setImportedDraft(null);
    setPoints([]);
    setDraft(null);
    setSelectedPointId('');
    setAnnotationPass('score');
    setSelectedPlaylistIds([]);
    setActiveGameNumber(1);
    setGameContexts({ 1: defaultGameContext(1) });
    setSaveIssue('');
    setSaveState('idle');
    setExported(false);
  }

  function draftImportIssueFor(issue: string): MessageKey {
    if (issue === 'unsupported-contract-version') return 'pro.video.importVersionError';
    return 'pro.video.importDataError';
  }

  async function handleDraftImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    const generation = ++quickImportGenerationRef.current;
    let payload: unknown;
    let source: QuickSource | null = null;
    try {
      const text = await file.text();
      payload = JSON.parse(text);
      try { source = await prepareQuickSource(text); } catch { /* Existing Quick import stays usable without a canonical source. */ }
    } catch {
      setDraftImportIssue('pro.video.importJsonError');
      setDraftImportStatus('');
      return;
    }
    const result = importQuickAnnotationDraft(payload);
    if (!result.ok) {
      setDraftImportIssue(draftImportIssueFor(result.issue));
      setDraftImportStatus('');
      return;
    }
    if (generation !== quickImportGenerationRef.current) return;
    const hasCurrentWork = points.length > 0 || draft !== null || saveState === 'dirty' || saveState === 'invalid';
    if (hasCurrentWork && !window.confirm(t('pro.video.importReplaceConfirm'))) return;

    installImportedDraft(result.value, source);
  }

  function installImportedDraft(value: ImportedQuickAnnotationDraft, source: QuickSource | null) {
    cancelPlaylist();
    setComparisonNote('');
    quickSourceRef.current = source;
    targetsRef.current = null;
    targetsImportGenerationRef.current += 1;
    setTargets(null);
    setTargetsStale(false);
    setTargetFilter(null);
    setTargetsIssue('');
    setInsightMode('basic');
    activeSessionIdRef.current = '';
    nextSessionIdRef.current = null;
    pendingFileRef.current = null;
    setSession(null);
    pointCreationOrderRef.current = [];
    setImportedDraft(value.identity);
    setLossFilter(null);
    setGameContexts(value.game_contexts);
    setPoints(value.points);
    setDraft(null);
    setSelectedPointId('');
    setSelectedPlaylistIds([]);
    setAnnotationPass('score');
    setActiveGameNumber(value.points[0]?.game_number ?? 1);
    setSaveIssue('');
    setSaveState(value.points.length > 0 ? 'saved' : 'idle');
    setExported(false);
    setFileIssueKey('');
    setPlaylistIssueKey('');
    setDraftImportIssue('');
    setDraftImportStatus('pro.video.importedNeedVideo');
  }

  async function loadGolden(quick: unknown, report: ReviewTargetsV01): Promise<boolean> {
    if (session || points.length || draft) return false;
    const generation = ++quickImportGenerationRef.current;
    try {
      const value = importQuickAnnotationDraft(quick);
      if (!value.ok || value.value.identity.dataset_class !== 'SIMULATED_ONLY') throw new Error('invalid-demo');
      const source = await prepareQuickSource(JSON.stringify(quick));
      const validated = validateReviewTargets(report, source);
      if (generation !== quickImportGenerationRef.current || activeSessionIdRef.current) return false;
      installImportedDraft(value.value, source);
      targetsRef.current = validated;
      setTargets(validated);
      setInsightMode('targets');
      return true;
    } catch { setTargetsIssue('demo-validation-failed'); return false; }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    if (session && (points.length > 0 || saveState === 'dirty' || saveState === 'invalid') && !window.confirm(t('pro.video.replaceConfirm'))) return;

    cancelPlaylist();
    if (importedDraft) {
      setLossFilter(null);
      setDraft(null);
      setSelectedPointId('');
      setSelectedPlaylistIds([]);
      setPoints((current) => current.map((point) => ({
        ...point,
        bound_video_identity: '',
        start_confirmed: false,
        end_confirmed: false,
      })));
      setSaveState(points.length > 0 ? 'saved' : 'idle');
      setExported(false);
    } else {
      resetPageAnnotations();
    }
    setFileIssueKey('');
    setDraftImportIssue('');
    setDraftImportStatus('');
    setPlaylistIssueKey('');
    const validExtension = file.name.toLowerCase().endsWith('.mp4');
    if (!validExtension || (file.type !== '' && file.type !== 'video/mp4')) {
      controllerRef.current?.loadFile(file);
      activeSessionIdRef.current = '';
      nextSessionIdRef.current = null;
      pendingFileRef.current = null;
      setSession(null);
      setFileIssueKey('pro.video.fileTypeError');
      return;
    }
    if (!Number.isFinite(file.size) || file.size <= 0) {
      controllerRef.current?.loadFile(file);
      activeSessionIdRef.current = '';
      nextSessionIdRef.current = null;
      pendingFileRef.current = null;
      setSession(null);
      setFileIssueKey('pro.video.fileUnreadable');
      return;
    }

    const sessionToken = crypto.randomUUID();
    const expectedIdentity = `local-session:${sessionToken}`;
    nextSessionIdRef.current = expectedIdentity;
    activeSessionIdRef.current = expectedIdentity;
    const nextSession: LocalVideoSession = {
      session_id: expectedIdentity,
      dataset_id: importedDraft?.dataset_id ?? `HUMAN_QUICK_DRAFT:${sessionToken}`,
      dataset_class: importedDraft?.dataset_class ?? 'HUMAN_QUICK_DRAFT',
      contract_version: importedDraft?.contract_version ?? 'ptti.quick-annotation/0.2',
      match_id: importedDraft?.match_id ?? `LOCAL_QUICK_MATCH:${sessionToken}`,
      source_id: importedDraft?.source_id ?? null,
      binding_status: 'LOCAL_SESSION_ONLY',
      media_status: 'loading',
      duration_seconds: null,
      file: { name: file.name, type: file.type, size: file.size, last_modified_ms: file.lastModified },
    };
    setSession(nextSession);
    const controller = controllerRef.current;
    if (!controller) {
      pendingFileRef.current = file;
      return;
    }
    const result = controller.loadFile(file);
    if (!result.ok) {
      activeSessionIdRef.current = '';
      nextSessionIdRef.current = null;
      setSession(null);
      setFileIssueKey(mediaIssueKey(result.error.code));
      return;
    }
    if (result.value !== expectedIdentity) {
      controller.pause();
      activeSessionIdRef.current = '';
      setSession(null);
      setFileIssueKey('pro.video.identityMismatch');
    }
  }

  function beginNewPoint() {
    if (!session || !mediaReady) return;
    if ((saveState === 'dirty' || saveState === 'invalid') && !window.confirm(t('pro.video.discardConfirm'))) return;
    invalidateTargets();
    const pointNumber = nextUnannotatedPointNumber(points, activeGameNumber);
    if (autoPauseOnAnnotate && playbackSnapshot.is_playing) controllerRef.current?.pause();
    const pointId = createQuickPointId(session.match_id, activeGameNumber, pointNumber);
    const next: BoundaryPoint = {
      point_id: pointId,
      game_number: activeGameNumber,
      point_number: pointNumber,
      winner: 'UNKNOWN',
      server: 'UNKNOWN',
      observed_tactics: { ...unknownTactics },
      ...(session.contract_version === 'ptti.quick-annotation/0.2' ? { observed_rally_stage: 'UNKNOWN' as const } : {}),
      start_seconds: null,
      end_seconds: null,
      bound_video_identity: session.session_id,
      start_confirmed: false,
      end_confirmed: false,
    };
    setSelectedPointId(pointId);
    setDraft(next);
    setAnnotationPass('score');
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function selectPoint(point: BoundaryPoint) {
    if (!session || !mediaReady) return;
    if ((saveState === 'dirty' || saveState === 'invalid') && point.point_id !== draft?.point_id && !window.confirm(t('pro.video.discardConfirm'))) return;
    cancelPlaylist();
    setSelectedPointId(point.point_id);
    setAnnotationPass('review');
    setDraft({ ...point, observed_tactics: { ...point.observed_tactics } });
    setActiveGameNumber(point.game_number);
    setSaveState('saved');
    setSaveIssue('');
    setExported(false);
    const binding = playbackBindings.get(point.point_id);
    if (binding?.binding_status === 'BOUND' && binding.start_time !== null) {
      controllerRef.current?.seek(binding.start_time);
      setPlaylistIssueKey('');
    } else {
      setPlaylistIssueKey('pro.video.confirmRangeFirst');
    }
  }

  function invalidatePlaylistForBoundaryChange() {
    cancelPlaylist();
    setPlaylistIssueKey('');
  }

  function updateBoundary(field: BoundaryField, value: number | null) {
    if (!draft) return;
    invalidateTargets();
    invalidatePlaylistForBoundaryChange();
    setPoints((current) => current.map((point) => point.point_id === draft.point_id
      ? { ...point, bound_video_identity: '', start_confirmed: false, end_confirmed: false }
      : point));
    setDraft((current) => current ? {
      ...current,
      [field]: value,
      start_confirmed: false,
      end_confirmed: false,
      bound_video_identity: '',
      ...(field === 'end_seconds' ? { end_auto_suggested: false } : {}),
    } : current);
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function updateDraft<K extends keyof LocalVideoPoint>(field: K, value: LocalVideoPoint[K]) {
    if (!draft) return;
    if (field === 'start_seconds' || field === 'end_seconds') {
      updateBoundary(field, value as number | null);
      return;
    }
    invalidateTargets();
    invalidatePlaylistForBoundaryChange();
    setPoints((current) => current.map((point) => point.point_id === draft.point_id
      ? { ...point, bound_video_identity: '', start_confirmed: false, end_confirmed: false }
      : point));
    setDraft((current) => current ? { ...current, [field]: value, bound_video_identity: '', start_confirmed: false, end_confirmed: false } : current);
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function updateTactic(field: TacticalField, value: string) {
    if (!draft || !tacticValues[field].includes(value)) return;
    invalidateTargets();
    invalidatePlaylistForBoundaryChange();
    setPoints((current) => current.map((point) => point.point_id === draft.point_id
      ? { ...point, bound_video_identity: '', start_confirmed: false, end_confirmed: false }
      : point));
    setDraft((current) => current ? { ...current, observed_tactics: { ...current.observed_tactics, [field]: value }, bound_video_identity: '', start_confirmed: false, end_confirmed: false } : current);
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function updateObservedRallyStage(value: string) {
    if (!draft || !['END_AFTER_1_2_CONTACTS', 'END_AFTER_3_4_CONTACTS', 'END_AFTER_5_PLUS_CONTACTS', 'UNKNOWN'].includes(value)) return;
    invalidateTargets();
    invalidatePlaylistForBoundaryChange();
    setPoints((current) => current.map((point) => point.point_id === draft.point_id
      ? { ...point, bound_video_identity: '', start_confirmed: false, end_confirmed: false }
      : point));
    setDraft((current) => current ? { ...current, observed_rally_stage: value as LocalVideoPoint['observed_rally_stage'], bound_video_identity: '', start_confirmed: false, end_confirmed: false } : current);
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function updateGameContext(field: 'coverage' | 'first_server', value: string) {
    invalidateTargets();
    setGameContexts((current) => ({
      ...current,
      [activeGameNumber]: {
        ...(current[activeGameNumber] ?? defaultGameContext(activeGameNumber)),
        [field]: value,
      } as LocalGameContext,
    }));
    setSaveIssue('');
    setExported(false);
  }

  function setTimestamp(field: BoundaryField) {
    if (!draft || !mediaReady || durationMs === null) return;
    updateBoundary(field, roundToMillisecond(readCurrentVideoTime()));
  }

  function suggestSixSecondEnd() {
    if (!draft || !mediaReady || durationMs === null) return;
    const start = draft.start_seconds ?? roundToMillisecond(readCurrentVideoTime());
    const end = Math.min(start + 6, durationMs / 1000);
    if (end <= start) {
      setSaveIssue(t('pro.video.suggestionUnavailable'));
      return;
    }
    invalidateTargets();
    invalidatePlaylistForBoundaryChange();
    setDraft((current) => current ? {
      ...current,
      start_seconds: current.start_seconds ?? start,
      end_seconds: roundToMillisecond(end),
      start_confirmed: false,
      end_confirmed: false,
      end_auto_suggested: true,
    } : current);
    setPoints((current) => current.map((point) => point.point_id === draft.point_id
      ? { ...point, bound_video_identity: '', start_confirmed: false, end_confirmed: false }
      : point));
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function confirmBoundary(field: BoundaryField) {
    if (!draft || !session || !mediaReady || durationMs === null) return;
    const value = draft[field];
    const other = field === 'start_seconds' ? draft.end_seconds : draft.start_seconds;
    const valueMs = value === null ? null : Math.round(value * 1000);
    if (value === null || !Number.isFinite(value) || valueMs === null || !Number.isSafeInteger(valueMs) || value < 0 || valueMs > durationMs
      || (other !== null && (field === 'start_seconds' ? value >= other : other >= value))) {
      setSaveIssue(t('pro.video.confirmRangeFirst'));
      setSaveState('invalid');
      return;
    }
    invalidatePlaylistForBoundaryChange();
    const confirmedField = field === 'start_seconds' ? 'start_confirmed' : 'end_confirmed';
    const nextConfirmed = !draft[confirmedField];
    const otherConfirmed = field === 'start_seconds' ? draft.end_confirmed : draft.start_confirmed;
    const nextIdentity = nextConfirmed && otherConfirmed ? session.session_id : '';
    if (!nextConfirmed) {
      setPoints((current) => current.map((point) => point.point_id === draft.point_id
        ? { ...point, start_confirmed: false, end_confirmed: false, bound_video_identity: '' }
        : point));
    }
    setDraft((current) => current ? { ...current, [confirmedField]: nextConfirmed, bound_video_identity: nextIdentity } : current);
    setSaveState('dirty');
    setSaveIssue('');
    setExported(false);
  }

  function savePoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !draft) return;
    const result = validateQuickAnnotationPoint(draft, durationMs, gameContexts, points, draftIsSaved ? draft.point_id : null, session.match_id);
    if (!result.ok) {
      const key = result.issue === 'duplicate-point-id' ? 'pro.video.duplicateId'
        : result.issue === 'time-out-of-range' ? 'pro.video.timeOutOfRange'
          : result.issue === 'start-after-end' ? 'pro.video.startAfterEnd'
            : result.issue === 'duration-unknown' ? 'pro.video.durationUnknownForTime'
              : result.issue === 'service-rotation-conflict' ? 'pro.video.serviceConflict'
                : 'pro.video.invalidTime';
      setSaveIssue(t(key));
      setSaveState('invalid');
      return;
    }
    const saved: BoundaryPoint = { ...draft, bound_video_identity: draft.start_confirmed && draft.end_confirmed ? session.session_id : '', observed_tactics: { ...draft.observed_tactics } };
    if (!points.some((point) => point.point_id === saved.point_id)) {
      pointCreationOrderRef.current = [...pointCreationOrderRef.current.filter((pointId) => pointId !== saved.point_id), saved.point_id];
    }
    setPoints((current) => {
      const next = current.some((point) => point.point_id === saved.point_id)
        ? current.map((point) => point.point_id === saved.point_id ? saved : point)
        : [...current, saved];
      return next.sort((left, right) => left.game_number - right.game_number || left.point_number - right.point_number);
    });
    setDraft(saved);
    setSelectedPointId(saved.point_id);
    setSaveIssue('');
    setSaveState('saved');
    setExported(false);
  }

  function undoLastSavedPoint() {
    if (saveState === 'dirty' || saveState === 'invalid') return;
    const pointId = pointCreationOrderRef.current.at(-1);
    if (!pointId || !points.some((point) => point.point_id === pointId)) return;
    invalidateTargets();
    cancelPlaylist();
    pointCreationOrderRef.current = pointCreationOrderRef.current.slice(0, -1);
    setPoints((current) => current.filter((point) => point.point_id !== pointId));
    setSelectedPlaylistIds((current) => current.filter((selectedId) => selectedId !== pointId));
    if (selectedPointId === pointId) setSelectedPointId('');
    if (draft?.point_id === pointId) {
      setDraft(null);
      setSaveState('idle');
    }
    setSaveIssue('');
    setPlaylistIssueKey('');
    setExported(false);
  }

  function reviewWinnerStat(winner: 'PLAYER_A' | 'PLAYER_B') {
    setInsightMode('basic');
    setTargetFilter(null);
    setLossFilter(null);
    const point = reviewablePoints.find((candidate) => candidate.winner === winner);
    if (point) selectPoint(point);
  }

  function exportAnnotations() {
    if (!session || !mediaReady || points.length === 0 || saveState === 'dirty' || saveState === 'invalid') return;
    const result = createQuickAnnotationInput(session, points, gameContexts);
    if (!result.ok) {
      setSaveIssue(t(result.issue === 'service-rotation-conflict' ? 'pro.video.serviceConflict' : result.issue === 'duration-required-for-time-range' ? 'pro.video.durationUnknownForTime' : 'pro.video.exportError'));
      return;
    }
    try {
      const blob = new Blob([`${JSON.stringify(result.value, null, 2)}\n`], { type: 'application/json' });
      const exportUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = exportUrl;
      anchor.download = 'ptti-quick-annotation-draft.json';
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(exportUrl), 1000);
      setExported(true);
      setSaveIssue('');
    } catch {
      setSaveIssue(t('pro.video.exportError'));
    }
  }

  function handlePlayPause() {
    if (!mediaReady || !controllerRef.current) return;
    if (playbackSnapshot.is_playing) controllerRef.current.pause();
    else void controllerRef.current.play().then((result) => { if (!result.ok) setPlaylistIssueKey(playbackIssueMessageKey(result.error.code)); });
  }

  function togglePlaylistPoint(point: BoundaryPoint, checked: boolean) {
    const binding = playbackBindings.get(point.point_id);
    if (!binding || binding.binding_status !== 'BOUND') {
      setPlaylistIssueKey('pro.video.confirmRangeFirst');
      return;
    }
    cancelPlaylist(false);
    setSelectedPlaylistIds((current) => checked
      ? [...new Set([...current, point.point_id])]
      : current.filter((pointId) => pointId !== point.point_id));
    setPlaylistIssueKey('');
  }

  function playSelectedRallies() {
    startRallyPlayback(selectedPlaylistIds, 2);
  }

  function startRallyPlayback(pointIds: string[], minimum = 1) {
    if (!controllerRef.current || !session || !mediaReady) return;
    if (pointIds.length < minimum) {
      setPlaylistIssueKey('pro.video.selectTwoRallies');
      return;
    }
    const selected = pointIds.map((pointId) => playbackBindings.get(pointId));
    if (selected.some((binding) => !binding || binding.binding_status !== 'BOUND')) {
      setPlaylistIssueKey('pro.video.confirmRangeFirst');
      setSelectedPlaylistIds([]);
      return;
    }
    const result = controllerRef.current.playRallyPlaylist(selected as RallyPlaybackBinding[]);
    if (!result.ok) {
      setPlaylistIssueKey(playbackIssueMessageKey(result.error.code));
      return;
    }
    const task = result.value;
    playlistTaskRef.current = task;
    setPlaylistIssueKey('');
    void task.done.then((outcome) => {
      if (playlistTaskRef.current !== task) return;
      playlistTaskRef.current = null;
      if (outcome.status === 'failed') setPlaylistIssueKey(playbackIssueMessageKey(outcome.error.code));
    });
  }

  function chooseLossCategory(stage: ObservedLossFilter, play = false) {
    setInsightMode('basic');
    setTargetFilter(null);
    const group = stage === 'ALL' ? lossInsights.all : lossInsights.stages[stage];
    cancelPlaylist();
    setLossFilter(stage);
    setSelectedPlaylistIds(group.playable_loss_ids);
    if (play && group.playable_loss_ids.length > 0) startRallyPlayback(group.playable_loss_ids);
  }

  function stageLabel(stage: ObservedLossFilter) {
    return stage === 'ALL' ? t('pro.insight.allLosses') : t(stage === 'END_AFTER_1_2_CONTACTS' ? 'pro.video.stageOneTwo' : stage === 'END_AFTER_3_4_CONTACTS' ? 'pro.video.stageThreeFour' : 'pro.video.stageFivePlus');
  }

  function invalidateTargets() {
    cancelPlaylist();
    setComparisonNote('');
    quickImportGenerationRef.current += 1;
    targetsImportGenerationRef.current += 1;
    quickSourceRef.current = null;
    if (targetsRef.current) setTargetsStale(true);
    targetsRef.current = null;
    setTargetFilter(null);
  }

  async function handleTargetsImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    const generation = ++targetsImportGenerationRef.current;
    cancelPlaylist();
    setComparisonNote('');
    targetsRef.current = null;
    setTargets(null);
    setTargetsStale(false);
    setTargetFilter(null);
    setInsightMode('targets');
    const source = quickSourceRef.current;
    try {
      if (!source || !matchesQuickSource(source, points, gameContexts) || saveState === 'dirty' || saveState === 'invalid') throw new Error('quick-source-required');
      if (file.size > 2 * 1024 * 1024) throw new Error('file-too-large');
      const report = validateReviewTargets(JSON.parse(await file.text()), source);
      if (generation !== targetsImportGenerationRef.current) return;
      if (source !== quickSourceRef.current) throw new Error('input-changed-during-import');
      targetsRef.current = report;
      setTargets(report);
      setTargetsIssue('');
    } catch (error) {
      if (generation !== targetsImportGenerationRef.current) return;
      setTargetsIssue(error instanceof Error ? error.message : 'invalid-report');
    }
  }

  function chooseReviewTarget(targetId: string, play = false) {
    cancelPlaylist();
    if (!targetsActive || targetsRef.current !== targets || !quickSourceRef.current) return;
    const target = targets?.review_targets.find((candidate) => candidate.target_id === targetId);
    if (!target || target.subject_role !== (observer === 'PLAYER_A' ? 'player' : 'opponent')) return;
    if (targetFilter !== targetId) setComparisonNote('');
    setTargetFilter(targetId);
    const ids = target.point_ids.filter((id) => playbackBindings.get(id)?.binding_status === 'BOUND');
    setSelectedPlaylistIds(ids);
    if (play && ids.length > 0) startRallyPlayback(ids);
  }

  function playComparisonPoint(pointId: string) {
    cancelPlaylist();
    if (!targetsActive || targetsRef.current !== targets || !activeTarget || !activeTarget.point_ids.includes(pointId)) return;
    const binding = playbackBindings.get(pointId);
    if (!binding || binding.binding_status !== 'BOUND' || !points.some((point) => point.point_id === pointId)) {
      setPlaylistIssueKey('pro.video.confirmRangeFirst');
      return;
    }
    startRallyPlayback([pointId], 1);
  }

  function exportComparisonNotes() {
    if (!targetsActive || targetsRef.current !== targets || !activeTarget || !targets || !session) return;
    try {
      const payload = createReviewComparisonExport({ report: targets, target: activeTarget, points, playbackBindings, note: comparisonNote, sessionId: session.session_id });
      const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'ptti-review-comparison-notes.json';
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setPlaylistIssueKey('');
    } catch {
      setPlaylistIssueKey('pro.targets.exportError');
    }
  }

  function pausePlaylist() {
    playlistTaskRef.current?.pause();
  }

  function resumePlaylist() {
    const task = playlistTaskRef.current;
    if (!task) return;
    void task.resume().then((result) => { if (!result.ok) setPlaylistIssueKey(playbackIssueMessageKey(result.error.code)); });
  }

  function stopPlaylist() {
    cancelPlaylist(false);
    setPlaylistIssueKey('');
  }

  const stateLabel = !session ? t('pro.video.stateEmpty')
    : playbackSnapshot.status === 'loading' ? t('pro.video.stateLoading')
      : playbackSnapshot.status === 'error' || session.media_status === 'error' ? t('pro.video.stateError')
        : mediaReady ? t('pro.video.stateReady') : t('pro.video.stateLoading');
  const playlistStatus = playbackSnapshot.playlist?.status;
  const playlistStatusLabel = playlistStatus === 'playing' ? t('pro.video.playlistPlaying')
    : playlistStatus === 'paused' ? t('pro.video.playlistPaused')
      : playlistStatus === 'completed' ? t('pro.video.playlistCompleted')
        : playlistStatus === 'cancelled' ? t('pro.video.playlistCancelled')
          : playlistStatus === 'failed' ? t('pro.video.playlistFailed') : '';

  return <section className="local-video-review" aria-labelledby="local-video-title" data-local-video-review>
    {!session && <div className="cinema-intro-grid"><div className="cinema-empty-stage" data-empty-video-stage>
      <span className="eyebrow">PTTI CINEMA</span><h2>{t('cinema.stage.title')}</h2><p>{t('cinema.stage.description')}</p>
      <button type="button" className="button button-primary" onClick={() => fileInputRef.current?.click()}>{t('pro.video.selectFile')}</button>
      <button type="button" className="text-button" data-browse-library onClick={onBrowseMatches ?? (() => document.getElementById('match-search')?.focus())}>{t('cinema.stage.official')}</button><small>{t('cinema.stage.noMedia')}</small>
    </div><CinemaDemo locale={locale} onLoad={loadGolden} onLoaded={onOpenInsight} canReplace={!session && points.length === 0 && !draft} /></div>}
    <div className="local-video-heading">
      <div><p className="eyebrow">{t('pro.video.kicker')}</p><h3 id="local-video-title">{t('pro.video.title')}</h3><p>{t('pro.video.description')}</p></div>
      <div className="local-video-head-actions"><span className="local-video-status">{t('pro.video.status')}</span><button type="button" className="button button-primary" data-export-draft onClick={exportAnnotations} disabled={!mediaReady || points.length === 0 || saveState === 'dirty' || saveState === 'invalid'}>{t('pro.video.exportShort')}</button></div>
    </div>
    <p className="local-video-boundary">{t('pro.video.boundary')}</p>
    <div className="local-video-draft-import-row">
      <label className="local-video-import-control"><span>{t('pro.video.importDraft')}</span><input aria-label={t('pro.video.importDraft')} type="file" accept="application/json,.json" onChange={handleDraftImport} /></label>
      <span>{t('pro.video.importPrivacy')}</span>
    </div>
    <div className="local-video-draft-import-row"><label className="local-video-import-control"><span>{t('pro.targets.import')}</span><input type="file" accept="application/json,.json" aria-label={t('pro.targets.import')} data-import-review-targets onChange={handleTargetsImport} /></label><span>{t('pro.targets.privacy')}</span></div>
    {targetsIssue && <p className="local-video-error" role="alert" data-targets-error>{t('pro.targets.rejected', { issue: targetsIssue })}</p>}
    {targets && <div className="local-video-imported-summary" data-targets-match={targetsActive ? 'MATCHED' : 'STALE'}><strong>{t(targetsActive ? 'pro.targets.matched' : 'pro.targets.stale')}</strong><code>{targets.dataset.dataset_id}</code><code>{targets.canonical_input_sha256}</code><span>{t('pro.targets.hashNote')}</span></div>}
    {draftImportIssue && <p className="local-video-error" role="alert">{t(draftImportIssue)}</p>}
    {draftImportStatus && <p className="local-video-import-status" role="status" aria-live="polite">{t(draftImportStatus)}</p>}
    {importedDraft && <div className="local-video-imported-summary" data-imported-draft-summary data-import-contract-version={importedDraft.contract_version}>
      <strong>{importedDraft.dataset_class === 'SIMULATED_ONLY' ? t('pro.video.simulatedDraft') : t('pro.video.importedDraft')}</strong>
      <code>{importedDraft.dataset_id}</code>
      <span>{t('pro.video.contractVersion', { version: importedDraft.contract_version })}</span>
      <span>{t('pro.video.importedPointCount', { count: points.length })}</span>
      <span>{t('pro.video.importedSourceUnverified', { source: importedDraft.source_id ?? t('pro.video.unknown') })}</span>
      <span>{t('pro.video.importedReconfirm')}</span>
    </div>}
    <div className="local-video-file-row">
      <label className="local-video-file-control">
        <span>{t('pro.video.selectFile')}</span>
        <input ref={fileInputRef} aria-label={t('pro.video.selectFile')} type="file" accept="video/mp4,.mp4" onChange={handleFileChange} />
      </label>
      <span className="local-video-state" role="status" aria-live="polite">{stateLabel}</span>
    </div>
    {fileIssueKey && <p className="local-video-error" role="alert">{t(fileIssueKey)}</p>}

    {session && <div className="local-video-player-layout">
      <div className="local-video-player-column">
        <div className="local-video-screen">
          <video
            ref={videoRef}
            data-local-video-player
            controls
            playsInline
            preload="metadata"
          />
          {!mediaReady && <span className="local-video-overlay">{playbackSnapshot.status === 'error' ? t('pro.video.videoUnavailable') : t('pro.video.localVideoLabel')}</span>}
        </div>
        <div className="local-video-player-tools">
          <button type="button" className="button button-secondary" data-playback-toggle onClick={handlePlayPause} disabled={!mediaReady || Boolean(playlistTaskRef.current)}>
            {playbackSnapshot.is_playing ? t('pro.video.pause') : t('pro.video.play')}
          </button>
          <label className="local-video-seek-control"><span>{t('pro.video.seek')}</span><input aria-label={t('pro.video.seek')} type="range" min="0" max={playbackSnapshot.duration_seconds ?? 0} step="0.05" value={Math.min(playbackSnapshot.current_time_seconds, playbackSnapshot.duration_seconds ?? 0)} onChange={(event) => controllerRef.current?.seek(Number(event.currentTarget.value))} disabled={!mediaReady} /></label>
          <label className="local-video-speed"><span>{t('pro.insight.speed')}</span><select aria-label={t('pro.insight.speed')} data-playback-speed value={playbackSnapshot.playback_rate} onChange={(event) => controllerRef.current?.setPlaybackRate(Number(event.currentTarget.value))} disabled={!mediaReady}><option value="0.5">0.5×</option><option value="1">1×</option></select></label>
        </div>
        <label className="local-video-auto-pause"><input type="checkbox" checked={autoPauseOnAnnotate} onChange={(event) => setAutoPauseOnAnnotate(event.currentTarget.checked)} /><span>{t('pro.video.autoPause')}</span></label>
        <div className="local-video-timebar" aria-live="off"><span>{t('pro.video.currentTime')} <strong data-local-video-time>{formatTime(playbackSnapshot.current_time_seconds, t('pro.video.unknown'))}</strong></span><span>{t('pro.video.duration')} <strong>{formatTime(playbackSnapshot.duration_seconds, t('pro.video.unknown'))}</strong></span></div>
        <div className="local-video-file-meta"><strong>{session.file.name}</strong><span>{t('pro.video.fileInfo', { size: session.file.size })}</span><span>{t('pro.video.localMatchId')}: <code>{session.match_id}</code></span><span>{t('pro.video.localBinding')}</span><span>{t('pro.video.sourceUnbound')}</span></div>
      </div>

      <div className="local-video-annotation-column">
        <details className="local-video-rule-settings">
          <summary>{t('pro.video.rulesSummary')}</summary>
          <div className="local-video-game-settings">
          <label><span>{t('pro.video.gameNumber')}</span><select aria-label={t('pro.video.gameNumber')} value={activeGameNumber} onChange={(event) => {
            const next = Number(event.currentTarget.value);
            cancelPlaylist();
            setLossFilter(null);
            setActiveGameNumber(next);
            setGameContexts((current) => current[next] ? current : { ...current, [next]: defaultGameContext(next) });
          }}>{Array.from({ length: 7 }, (_, index) => index + 1).map((number) => <option key={number} value={number}>{number}</option>)}</select></label>
          <label><span>{t('pro.video.coverage')}</span><select aria-label={t('pro.video.coverage')} value={activeGameContext.coverage} onChange={(event) => updateGameContext('coverage', event.target.value)}>
            <option value="PARTIAL_OR_UNKNOWN">{t('pro.video.coveragePartial')}</option>
            <option value="COMPLETE_FROM_GAME_START">{t('pro.video.coverageComplete')}</option>
          </select></label>
          <label><span>{t('pro.video.firstServer')}</span><select aria-label={t('pro.video.firstServer')} value={activeGameContext.first_server} onChange={(event) => updateGameContext('first_server', event.target.value)}>
            {playerValues.map((value) => <option key={value} value={value}>{t(value === 'PLAYER_A' ? 'pro.video.playerA' : value === 'PLAYER_B' ? 'pro.video.playerB' : 'pro.video.unknown')}</option>)}
          </select></label>
          </div>
          <p className="local-video-rule-note">{t('pro.video.ruleNote')}</p>
        </details>
        <div className="local-video-pass-switch" role="group" aria-label={t('pro.video.passLabel')}>
          <button type="button" data-annotation-pass="score" aria-pressed={annotationPass === 'score'} onClick={() => setAnnotationPass('score')}>{t('pro.video.passScore')}</button>
          <button type="button" data-annotation-pass="review" aria-pressed={annotationPass === 'review'} disabled={points.length === 0 && !draft} onClick={() => setAnnotationPass('review')}>{t('pro.video.passReview')}</button>
        </div>
        <p className="local-video-pass-note">{t(annotationPass === 'score' ? 'pro.video.passScoreNote' : 'pro.video.passReviewNote')}</p>
        <div className="local-video-pass-switch" role="group" aria-label={t('pro.targets.mode')}><button type="button" data-insight-mode="basic" aria-pressed={insightMode === 'basic'} onClick={() => { cancelPlaylist(); setInsightMode('basic'); setTargetFilter(null); }}>{t('pro.targets.basic')}</button><button type="button" data-insight-mode="targets" aria-pressed={insightMode === 'targets'} onClick={() => { cancelPlaylist(); setInsightMode('targets'); setLossFilter(null); }}>{t('pro.targets.formal')}</button></div>
        {insightMode === 'targets' && <section className="local-loss-insights" data-review-targets-panel aria-label={t('pro.targets.formal')}>
          {!targetsActive || !targetAthlete ? <p data-targets-unavailable>{t(targetsStale || targets ? 'pro.targets.stale' : 'pro.targets.needImport')}</p> : <>
            <div className="local-loss-heading"><h4>{t('pro.targets.formal')}</h4><label><span>{t('pro.insight.observer')}</span><select data-targets-observer aria-label={t('pro.insight.observer')} value={observer} onChange={(event) => { cancelPlaylist(); setTargetFilter(null); setObserver(event.currentTarget.value as 'PLAYER_A' | 'PLAYER_B'); }}><option value="PLAYER_A">{t('pro.video.playerA')}</option><option value="PLAYER_B">{t('pro.video.playerB')}</option></select></label></div>
            <p data-targets-score>{t('pro.targets.score', { wins: targetAthlete.score.won_count, losses: targetAthlete.score.lost_count, n: targetAthlete.score.denominator })}</p>
            <small>{t('pro.targets.scope')}</small>
            {OBSERVED_LOSS_STAGES.map((stage) => {
              const metric = targetAthlete.observed_stages[stage];
              const target = targets?.review_targets.find((candidate) => candidate.subject_role === targetAthlete.role && candidate.observed_rally_stage === stage);
              const playable = target?.point_ids.filter((id) => playbackBindings.get(id)?.binding_status === 'BOUND') ?? [];
              return <div className="local-loss-category" key={stage}><button type="button" data-target-stage={stage} disabled={!target} aria-pressed={targetFilter === target?.target_id} onClick={() => target && chooseReviewTarget(target.target_id)}><strong>{stageLabel(stage)}</strong><span>{t('pro.targets.metric', { losses: metric.lost_count, n: metric.denominator, unknown: metric.unknown_count, playable: playable.length })}</span>{metric.sample_status === 'INSUFFICIENT_SAMPLE' && <span>{t('pro.targets.small', { threshold: targets?.display_caution_threshold ?? 5 })}</span>}</button>{target && playable.length > 0 ? <button type="button" data-target-play={stage} onClick={() => chooseReviewTarget(target.target_id, true)}>{t('pro.insight.play', { count: playable.length })}</button> : <span className="local-loss-unavailable">{t('pro.insight.noClip')}</span>}</div>;
            })}
            {activeTarget && <div className="local-target-points" data-target-point-list><strong>{t('pro.targets.ids')}</strong>{activeTarget.point_ids.map((id) => {
              const point = points.find((p) => p.point_id === id);
              const playable = playbackBindings.get(id)?.binding_status === 'BOUND';
              return <div key={id} data-target-point-id={id} data-target-playable={String(playable)}><code>{id}</code><span>{t(playable ? 'pro.video.boundForSession' : point?.start_seconds === null || point?.end_seconds === null ? 'pro.targets.noTime' : 'pro.targets.noBinding')}</span></div>;
            })}
            <strong>{t('pro.compare.title')}</strong>
            <div className="local-comparison-clip-tabs" role="group" aria-label={t('pro.compare.title')}>
              {activeTarget.point_ids.map((id, index) => {
                const playable = playbackBindings.get(id)?.binding_status === 'BOUND';
                return <button type="button" key={id} data-comparison-point={id} disabled={!playable} onClick={() => playComparisonPoint(id)}>{index + 1} · {id.split('/').at(-1)}{playable ? '' : ` · ${t('pro.compare.scoreOnly')}`}</button>;
              })}
            </div>
            <p className="local-comparison-authorship">{t('pro.compare.authorship')}</p>
            <label className="local-comparison-notes"><span>{t('pro.compare.myObservation')}</span><textarea data-comparison-note value={comparisonNote} placeholder={t('pro.compare.example')} maxLength={5000} onChange={(event) => setComparisonNote(event.currentTarget.value)} rows={4} /></label>
            <button type="button" className="button button-secondary" data-export-comparison disabled={!targetsActive || !mediaReady} onClick={exportComparisonNotes}>{t('pro.compare.export')}</button>
            </div>}
            {activeTarget && <button type="button" className="button button-secondary" data-clear-target-filter onClick={() => { cancelPlaylist(); setTargetFilter(null); }}>{t('pro.insight.clear')}</button>}
            <small>{t('pro.targets.unknown', { count: targets?.unknown_stage_count ?? 0 })}</small>
            {(playlistStatus === 'playing' || playlistStatus === 'paused') && <div className="local-video-actions"><button type="button" className="button button-secondary" data-target-pause onClick={playlistStatus === 'paused' ? resumePlaylist : pausePlaylist}>{t(playlistStatus === 'paused' ? 'pro.video.playlistResume' : 'pro.video.playlistPause')}</button><button type="button" className="button button-secondary" data-target-cancel onClick={stopPlaylist}>{t('pro.video.playlistCancel')}</button></div>}
          </>}
        </section>}
        {insightMode === 'basic' && <section className="local-loss-insights" data-loss-insights aria-label={t('pro.insight.title')}>
          <div className="local-loss-heading"><h4>{t('pro.insight.title')}</h4><label><span>{t('pro.insight.observer')}</span><select aria-label={t('pro.insight.observer')} data-loss-observer value={observer} onChange={(event) => { cancelPlaylist(); setLossFilter(null); setObserver(event.currentTarget.value as 'PLAYER_A' | 'PLAYER_B'); }}><option value="PLAYER_A">{t('pro.video.playerA')}</option><option value="PLAYER_B">{t('pro.video.playerB')}</option></select></label></div>
          <p data-insight-score>{t('pro.insight.score', { game: activeGameNumber, recorded: lossInsights.recorded, wins: lossInsights.all.wins, losses: lossInsights.all.losses, playable: lossInsights.all.playable_loss_ids.length })}</p>
          <small>{t('pro.insight.scope')}</small>
          {(['ALL', ...OBSERVED_LOSS_STAGES] as ObservedLossFilter[]).map((stage) => {
            const group = stage === 'ALL' ? lossInsights.all : lossInsights.stages[stage];
            return <div className="local-loss-category" key={stage}>
              <button type="button" data-loss-filter={stage} aria-pressed={lossFilter === stage} onClick={() => chooseLossCategory(stage)}><strong>{stageLabel(stage)}</strong><span>{t('pro.insight.group', { wins: group.wins, losses: group.losses, playable: group.playable_loss_ids.length })}</span></button>
              {group.playable_loss_ids.length > 0 && mediaReady ? <button type="button" data-loss-play={stage} onClick={() => chooseLossCategory(stage, true)}>{t('pro.insight.play', { count: group.playable_loss_ids.length })}</button> : <span className="local-loss-unavailable" data-loss-unavailable={stage}>{t('pro.insight.noClip')}</span>}
            </div>;
          })}
          <small data-insight-unknown>{t('pro.insight.unknown', { stage: lossInsights.unknown_stages, winner: lossInsights.unknown_winners })}</small>
          {filteredLosses && <div className="local-loss-selection" role="status"><strong data-loss-selection>{t('pro.insight.selected', { recorded: filteredLosses.losses, playable: filteredLosses.playable_loss_ids.length })}</strong><button type="button" data-clear-loss-filter onClick={() => { cancelPlaylist(); setLossFilter(null); }}>{t('pro.insight.clear')}</button>{filteredLosses.playable_loss_ids.length === 0 && <p data-loss-empty>{t('pro.insight.empty')}</p>}</div>}
          {(playlistStatus === 'playing' || playlistStatus === 'paused') && <div className="local-video-actions"><button type="button" className="button button-secondary" data-loss-playback-pause onClick={playlistStatus === 'paused' ? resumePlaylist : pausePlaylist}>{t(playlistStatus === 'paused' ? 'pro.video.playlistResume' : 'pro.video.playlistPause')}</button><button type="button" className="button button-secondary" data-loss-playback-cancel onClick={stopPlaylist}>{t('pro.video.playlistCancel')}</button></div>}
        </section>}
        <div className="local-video-points-heading"><div><h4>{t('pro.video.pointsTitle')}</h4><p>{t('pro.video.pointsCount', { count: points.length })}</p><small>{t('pro.video.nextMissingNote')}</small></div><div className="local-video-point-heading-actions"><button type="button" className="button button-secondary" data-undo-point onClick={undoLastSavedPoint} disabled={pointCreationOrderRef.current.length === 0 || saveState === 'dirty' || saveState === 'invalid'}>{t('pro.video.undoLastPoint')}</button><button type="button" className="button button-primary" onClick={beginNewPoint} disabled={!mediaReady}>{t('pro.video.newPoint')}</button></div></div>
        <div className="local-video-stats" aria-label={t('pro.video.statsTitle')}>
          <strong>{t('pro.video.scoreRecords')}</strong>
          <span className="local-video-score-counts" data-score-counts data-known-winner-count={pointCounts.known_winner_points}>{t('pro.video.scoreSummary', { playerA: pointCounts.score_by_winner.PLAYER_A, playerB: pointCounts.score_by_winner.PLAYER_B, known: pointCounts.known_winner_points, total: pointCounts.total_points })}</span>
          <strong>{t('pro.video.reviewableTitle')}</strong>
          <span className="local-video-score-counts" data-current-session-reviewable={pointCounts.reviewable_points}>{t('pro.video.sessionReviewableCount', { count: pointCounts.reviewable_points })}</span>
          <button type="button" data-review-winner="PLAYER_A" onClick={() => reviewWinnerStat('PLAYER_A')} disabled={!mediaReady || pointCounts.reviewable_by_winner.PLAYER_A === 0}>{t('pro.video.winnerStat', { player: t('pro.video.playerA'), count: pointCounts.reviewable_by_winner.PLAYER_A })}</button>
          <button type="button" data-review-winner="PLAYER_B" onClick={() => reviewWinnerStat('PLAYER_B')} disabled={!mediaReady || pointCounts.reviewable_by_winner.PLAYER_B === 0}>{t('pro.video.winnerStat', { player: t('pro.video.playerB'), count: pointCounts.reviewable_by_winner.PLAYER_B })}</button>
          <small>{t('pro.video.statsEvidence', { count: pointCounts.reviewable_points, total: pointCounts.total_points })}</small>
          <strong>{t('pro.video.independentMediaTitle')}</strong>
          <span className="local-video-score-counts" data-independent-media-verified={pointCounts.independently_verified_media_points}>{t('pro.video.independentMediaCount', { count: pointCounts.independently_verified_media_points })}</span>
          <small>{t('pro.video.independentMediaNote')}</small>
          <strong>{t('pro.video.technicalSamples')}</strong>
          <small data-technical-samples>{t('pro.video.technicalSampleSummary', { serveSample: sampleLabel(pointCounts.known_serve_side), thirdSample: sampleLabel(pointCounts.known_third_ball_attack) })}</small>
          {(pointCounts.known_serve_side < 5 || pointCounts.known_third_ball_attack < 5) && <small data-small-sample-warning>{t('pro.video.technicalSampleWarning')}</small>}
          <small>{t('pro.video.technicalSampleNote')}</small>
        </div>
        {points.length === 0 && !draft && <p className="local-video-empty" role="status">{t('pro.video.noPoints')}</p>}

        {draft && <form ref={pointFormRef} className="local-video-point-form" noValidate onSubmit={savePoint}>
          <div className="local-video-draft-heading"><strong>{draftIsSaved ? t('pro.video.editingPoint') : t('pro.video.newPointDraft')}</strong><code>{draft.point_id}</code></div>
          <div className="local-video-fields">
            <label><span>{t('pro.video.winner')}</span><select aria-label={t('pro.video.winner')} value={draft.winner} onChange={(event) => updateDraft('winner', event.target.value as LocalVideoPlayer)}>{playerValues.map((value) => <option key={value} value={value}>{t(value === 'PLAYER_A' ? 'pro.video.playerA' : value === 'PLAYER_B' ? 'pro.video.playerB' : 'pro.video.unknown')}</option>)}</select></label>
            {annotationPass === 'review' && <>
            <label><span>{t('pro.video.server')}</span><select aria-label={t('pro.video.server')} value={draft.server} onChange={(event) => updateDraft('server', event.target.value as LocalVideoPlayer)}>{playerValues.map((value) => <option key={value} value={value}>{t(value === 'PLAYER_A' ? 'pro.video.playerA' : value === 'PLAYER_B' ? 'pro.video.playerB' : 'pro.video.unknown')}</option>)}</select>{suggestedServer !== 'UNKNOWN' && draft.server === 'UNKNOWN' && <button type="button" className="local-video-suggestion" data-use-server-suggestion onClick={() => updateDraft('server', suggestedServer)}>{t('pro.video.useRuleServer', { player: t(suggestedServer === 'PLAYER_A' ? 'pro.video.playerA' : 'pro.video.playerB') })}</button>}{suggestedServer === 'UNKNOWN' && <small>{t('pro.video.serverUnknownRule')}</small>}</label>
            {(['start_seconds', 'end_seconds'] as const).map((field) => {
              const isStart = field === 'start_seconds';
              const confirmed = isStart ? draft.start_confirmed : draft.end_confirmed;
              const labelKey = isStart ? 'pro.video.start' : 'pro.video.end';
              const inputKey = isStart ? 'pro.video.startSeconds' : 'pro.video.endSeconds';
              return <label key={field}><span>{t(labelKey)}</span><div className="local-video-time-field"><input aria-label={t(inputKey)} type="number" min="0" max={playbackSnapshot.duration_seconds ?? undefined} step="0.001" value={draft[field] === null ? '' : draft[field]} disabled={durationMs === null} onChange={(event) => updateBoundary(field, event.currentTarget.value === '' ? null : Number(event.currentTarget.value))} /><button type="button" className="local-video-set-time" onClick={() => setTimestamp(field)} disabled={!mediaReady || durationMs === null}>{t('pro.video.useCurrent')}</button>{field === 'end_seconds' && <button type="button" className="local-video-suggest-six" data-suggest-six-seconds onClick={suggestSixSecondEnd} disabled={!mediaReady || durationMs === null}>{t('pro.video.suggestSixSeconds')}</button>}<button type="button" className={`local-video-confirm-time ${confirmed ? 'confirmed' : ''}`} data-confirm-boundary={isStart ? 'start' : 'end'} aria-pressed={confirmed} onClick={() => confirmBoundary(field)} disabled={!mediaReady || draft[field] === null}>{confirmed ? t('pro.video.boundaryConfirmed') : t('pro.video.confirmBoundary')}</button></div>{draft[field] !== null && !confirmed && <small>{draft.end_auto_suggested && !isStart ? t('pro.video.autoSuggestedProvisional') : t('pro.video.boundaryProvisional')}</small>}</label>;
            })}
            </>}
          </div>
          {annotationPass === 'review' && <details className="local-video-optional-tactics"><summary>{t('pro.video.optionalTactics')}</summary><p className="local-video-rule-note">{t('pro.video.tacticsContractNote')}</p><div className="local-video-fields">
            <label><span>{t('pro.video.serveSide')}</span><select aria-label={t('pro.video.serveSide')} value={draft.observed_tactics.serve_side} onChange={(event) => updateTactic('serve_side', event.target.value)}>{tacticValues.serve_side.map((value) => <option key={value} value={value}>{t(`pro.video.tactic.${value}` as MessageKey)}</option>)}</select></label>
            <label><span>{t('pro.video.serveLength')}</span><select aria-label={t('pro.video.serveLength')} value={draft.observed_tactics.serve_length} onChange={(event) => updateTactic('serve_length', event.target.value)}>{tacticValues.serve_length.map((value) => <option key={value} value={value}>{t(`pro.video.tactic.${value}` as MessageKey)}</option>)}</select></label>
            <label><span>{t('pro.video.thirdBall')}</span><select aria-label={t('pro.video.thirdBall')} value={draft.observed_tactics.third_ball_attack} onChange={(event) => updateTactic('third_ball_attack', event.target.value)}>{tacticValues.third_ball_attack.map((value) => <option key={value} value={value}>{t(`pro.video.tactic.${value}` as MessageKey)}</option>)}</select></label>
            {session.contract_version === 'ptti.quick-annotation/0.2' && <label><span>{t('pro.video.observedRallyStage')}</span><select aria-label={t('pro.video.observedRallyStage')} data-observed-rally-stage value={draft.observed_rally_stage ?? 'UNKNOWN'} onChange={(event) => updateObservedRallyStage(event.currentTarget.value)}><option value="END_AFTER_1_2_CONTACTS">{t('pro.video.stageOneTwo')}</option><option value="END_AFTER_3_4_CONTACTS">{t('pro.video.stageThreeFour')}</option><option value="END_AFTER_5_PLUS_CONTACTS">{t('pro.video.stageFivePlus')}</option><option value="UNKNOWN">{t('pro.video.unknown')}</option></select></label>}
          </div></details>}
          <p className="local-video-unknown-note">{t('pro.video.unknownNote')}</p>
          <div className="local-video-actions"><button type="submit" className="button button-primary" disabled={!mediaReady}>{t('pro.video.savePoint')}</button><button type="button" className="button button-secondary" onClick={exportAnnotations} disabled={!mediaReady || points.length === 0 || saveState === 'dirty' || saveState === 'invalid'}>{t('pro.video.export')}</button></div>
          <p className="local-video-save-status" role="status" aria-live="polite">{saveState === 'dirty' ? t('pro.video.unsaved') : saveState === 'invalid' ? t('pro.video.invalid') : exported ? t('pro.video.exported') : saveState === 'saved' ? t('pro.video.savedInMemory') : ''}</p>
          {saveIssue && <p className="local-video-error" role="alert">{saveIssue}</p>}
        </form>}
        <div className="local-video-playlist-panel">
          <div><strong>{t('pro.video.playlistTitle')}</strong><span>{t('pro.video.playlistSelectionCount', { count: selectedPlaylistIds.length })}</span></div>
          <div className="local-video-actions">
            <button type="button" className="button button-primary" data-playlist-start onClick={playSelectedRallies} disabled={!mediaReady || selectedPlaylistIds.length < 2}>{t('pro.video.playlistStart')}</button>
            {playlistStatus === 'playing' && <button type="button" className="button button-secondary" data-playlist-pause onClick={pausePlaylist}>{t('pro.video.playlistPause')}</button>}
            {playlistStatus === 'paused' && <button type="button" className="button button-secondary" data-playlist-resume onClick={resumePlaylist}>{t('pro.video.playlistResume')}</button>}
            {(playlistStatus === 'playing' || playlistStatus === 'paused') && <button type="button" className="button button-secondary" data-playlist-cancel onClick={stopPlaylist}>{t('pro.video.playlistCancel')}</button>}
          </div>
          <p className="local-video-playlist-status" role="status" aria-live="polite">{playlistStatusLabel}</p>
          {playlistIssueKey && <p className="local-video-error" role="alert">{t(playlistIssueKey)}</p>}
        </div>
        {points.length > 0 && <div className="local-video-point-list" aria-label={t('pro.video.pointsTitle')}>
          {visiblePoints.map((point) => {
            const binding = playbackBindings.get(point.point_id);
            const eligible = binding?.binding_status === 'BOUND';
            const checked = selectedPlaylistIds.includes(point.point_id);
            return <div className={`local-video-point-row ${selectedPointId === point.point_id ? 'active' : ''}`} key={point.point_id} data-point-id={point.point_id}>
              <button type="button" className={`local-video-point ${selectedPointId === point.point_id ? 'active' : ''}`} data-replay-status={eligible ? 'LOCAL_SESSION_ONLY' : 'SCORE_ONLY'} aria-pressed={selectedPointId === point.point_id} onClick={() => selectPoint(point)}>
                <span><strong>{localPointLabel(locale, point)}</strong><small>{formatTime(point.start_seconds, t('pro.video.unknown'))} – {formatTime(point.end_seconds, t('pro.video.unknown'))}</small>{point.observed_rally_stage && <small>{t('pro.video.observedRallyStage')}: {t(point.observed_rally_stage === 'END_AFTER_1_2_CONTACTS' ? 'pro.video.stageOneTwo' : point.observed_rally_stage === 'END_AFTER_3_4_CONTACTS' ? 'pro.video.stageThreeFour' : point.observed_rally_stage === 'END_AFTER_5_PLUS_CONTACTS' ? 'pro.video.stageFivePlus' : 'pro.video.unknown')}</small>}<small>{eligible ? t('pro.video.boundForSession') : t('pro.video.rangeNeedsConfirmation')}</small></span><span className="local-video-point-jump">{t('pro.video.jump')}</span>
              </button>
              <label className="local-video-queue-control"><input type="checkbox" aria-label={t('pro.video.addToPlaylist', { point: localPointLabel(locale, point) })} checked={checked} disabled={!eligible} onChange={(event) => togglePlaylistPoint(point, event.currentTarget.checked)} /><span>{t('pro.video.playlistAdd')}</span></label>
            </div>;
          })}
        </div>}
      </div>
    </div>}
  </section>;
}
