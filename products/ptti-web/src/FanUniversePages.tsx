import { useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type { FanMatch } from './fan-catalog.mjs';
import { message } from './i18n';
import { FanArtwork } from './FanArtwork';
import { usePublicFanCatalog } from './PublicFanCatalog';
import type { Locale, MessageKey } from './i18n';
import { parseFanLocalDataBackup, serializeFanLocalDataBackup, validateFanLocalDataReferences } from './fan-local-data.mjs';
import type { FanLocalData, FanLocalNote } from './fan-local-data.mjs';

function copy(locale: Locale, key: string) { return message(locale, key as MessageKey); }

function usePublicMatches() {
  const { catalog, loading, error } = usePublicFanCatalog();
  return { catalog, matches: catalog?.matches ?? [], loading, error };
}

function createId() {
  try { return crypto.randomUUID(); } catch { return `local-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`; }
}

function LocalBackup({ locale, data, onReplace }: { locale: Locale; data: FanLocalData; onReplace: (data: FanLocalData) => boolean }) {
  const { catalog, loading, error } = usePublicMatches();
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState('');

  function exportBackup() {
    try {
      const blob = new Blob([serializeFanLocalDataBackup(data)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'ptti-fan-local-backup.json';
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setStatus(copy(locale, 'universe.backup.exported'));
    } catch {
      setStatus(copy(locale, 'universe.backup.failed'));
    }
  }

  async function importBackup(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = parseFanLocalDataBackup(await file.text());
      if (!catalog) throw new Error('public-catalog-unavailable');
      const accepted = validateFanLocalDataReferences(parsed, { matchIds: catalog.matches.map((match) => match.match_id), athleteIds: catalog.stars.map((star) => star.athlete_id) });
      if (!window.confirm(copy(locale, 'universe.backup.confirmReplace'))) return;
      setStatus(onReplace(accepted) ? copy(locale, 'universe.backup.imported') : copy(locale, 'universe.storage.warning'));
    } catch {
      setStatus(copy(locale, 'universe.backup.invalid'));
    } finally {
      if (input.current) input.current.value = '';
    }
  }

  return <div className="universe-backup">
    <div><strong>{copy(locale, 'universe.backup.title')}</strong><small>{copy(locale, 'universe.backup.privacy')}</small></div>
    <div className="universe-actions"><button type="button" className="button button-outline" onClick={exportBackup}>{copy(locale, 'universe.backup.export')}</button>
      <button type="button" className="button button-outline" disabled={!catalog} onClick={() => input.current?.click()}>{copy(locale, 'universe.backup.import')}</button>
      <input ref={input} id={inputId} className="sr-only" type="file" accept="application/json,.json" onChange={(event) => void importBackup(event.currentTarget.files?.[0])} />
    </div>
    {loading && <p role="status" className="universe-inline-status">{copy(locale, 'fan.loading')}</p>}{error && <p role="alert" className="universe-inline-status">{copy(locale, 'fan.loadError')}</p>}
    {status && <p role="status" className="universe-inline-status">{status}</p>}
  </div>;
}

type NoteKind = 'training' | 'match' | 'coach' | 'fan';
const noteKeys: Record<NoteKind, 'training_notes' | 'match_notes' | 'coach_notes' | 'fan_notes'> = {
  training: 'training_notes', match: 'match_notes', coach: 'coach_notes', fan: 'fan_notes',
};
const noteTranslations: Record<NoteKind, { kicker: MessageKey; title: MessageKey; intro: MessageKey; topic: MessageKey; question: MessageKey; summary: MessageKey; next: MessageKey; submit: MessageKey; add: MessageKey }> = {
  training: { kicker: 'universe.train.kicker', title: 'universe.train.notesTitle', intro: 'universe.train.notesIntro', topic: 'universe.train.topic', question: 'universe.train.question', summary: 'universe.train.summary', next: 'universe.train.next', submit: 'universe.train.save', add: 'universe.train.add' },
  match: { kicker: 'universe.matchNotes.title', title: 'universe.matchNotes.title', intro: 'universe.matchNotes.intro', topic: 'universe.matchNotes.topic', question: 'universe.matchNotes.question', summary: 'universe.matchNotes.summary', next: 'universe.matchNotes.next', submit: 'universe.matchNotes.save', add: 'universe.matchNotes.add' },
  coach: { kicker: 'universe.coachNotes.title', title: 'universe.coachNotes.title', intro: 'universe.coachNotes.intro', topic: 'universe.coachNotes.topic', question: 'universe.coachNotes.question', summary: 'universe.coachNotes.summary', next: 'universe.coachNotes.next', submit: 'universe.coachNotes.save', add: 'universe.coachNotes.add' },
  fan: { kicker: 'universe.community.kicker', title: 'universe.community.notesTitle', intro: 'universe.community.notesIntro', topic: 'universe.community.topic', question: 'universe.community.question', summary: 'universe.community.summary', next: 'universe.community.next', submit: 'universe.community.save', add: 'universe.community.add' },
};
function LocalNotes({ locale, kind, data, matches, onChange, onOpenMatch }: {
  locale: Locale; kind: NoteKind; data: FanLocalData; matches: FanMatch[];
  onChange: (next: FanLocalData) => boolean; onOpenMatch: (id: string) => void;
}) {
  const key = noteKeys[kind];
  const notes = data[key];
  const [editing, setEditing] = useState<FanLocalNote | null>(null);
  const [status, setStatus] = useState('');
  const labels = noteTranslations[kind];

  function beginNew() {
    setEditing({ id: createId(), date: new Date().toISOString().slice(0, 10), topic: '', technical_question: '', summary: '', next_goal: '', match_id: null });
    setStatus('');
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const form = new FormData(event.currentTarget);
    const note: FanLocalNote = {
      id: editing.id,
      date: String(form.get('date') ?? ''),
      topic: String(form.get('topic') ?? '').trim().slice(0, 120),
      technical_question: String(form.get('technical_question') ?? '').trim().slice(0, 1000),
      summary: String(form.get('summary') ?? '').trim().slice(0, 2000),
      next_goal: String(form.get('next_goal') ?? '').trim().slice(0, 1000),
      match_id: String(form.get('match_id') ?? '') || null,
    };
    const nextNotes = notes.some((item) => item.id === note.id) ? notes.map((item) => item.id === note.id ? note : item) : [note, ...notes];
    const success = onChange({ ...data, [key]: nextNotes });
    setEditing(null);
    setStatus(success ? copy(locale, 'universe.storage.saved') : copy(locale, 'universe.storage.warning'));
  }

  function remove(id: string) {
    const success = onChange({ ...data, [key]: notes.filter((item) => item.id !== id) });
    setStatus(success ? copy(locale, 'universe.storage.deleted') : copy(locale, 'universe.storage.warning'));
    if (editing?.id === id) setEditing(null);
  }

  const hasObservationFields = kind !== 'fan';
  return <section className="universe-notes" aria-labelledby={`${kind}-notes-title`} data-note-kind={kind}>
    <div className="universe-section-head"><div><p className="eyebrow">{copy(locale, labels.kicker)}</p><h2 id={`${kind}-notes-title`}>{copy(locale, labels.title)}</h2><p>{copy(locale, labels.intro)}</p></div>
      {!editing && <button className="button button-primary" type="button" onClick={beginNew}>{copy(locale, labels.add)}</button>}</div>
    {editing && <form key={editing.id} className="universe-note-form" onSubmit={submit}>
      <label>{copy(locale, 'universe.note.date')}<input name="date" type="date" defaultValue={editing.date} required /></label>
      <label>{copy(locale, labels.topic)}<input name="topic" maxLength={120} defaultValue={editing.topic} required /></label>
      {hasObservationFields && <label>{copy(locale, labels.question)}<textarea name="technical_question" maxLength={1000} defaultValue={editing.technical_question} rows={2} /></label>}
      <label>{copy(locale, labels.summary)}<textarea name="summary" maxLength={2000} defaultValue={editing.summary} rows={3} required /></label>
      {hasObservationFields && <label>{copy(locale, labels.next)}<textarea name="next_goal" maxLength={1000} defaultValue={editing.next_goal} rows={2} /></label>}
      <label>{copy(locale, 'universe.note.match')}<select name="match_id" defaultValue={editing.match_id ?? ''}><option value="">{copy(locale, 'universe.note.noMatch')}</option>{matches.map((match) => <option value={match.match_id} key={match.match_id}>{match.event} · {match.round}</option>)}</select></label>
      <p className="universe-form-note">{copy(locale, 'universe.storage.localOnly')}</p>
      <div className="universe-actions"><button className="button button-primary" type="submit">{copy(locale, labels.submit)}</button><button className="button button-outline" type="button" onClick={() => setEditing(null)}>{copy(locale, 'universe.note.cancel')}</button></div>
    </form>}
    {status && <p className="universe-inline-status" role="status">{status}</p>}
    {notes.length === 0 ? <div className="universe-empty"><strong>{copy(locale, 'universe.notes.emptyTitle')}</strong><p>{copy(locale, 'universe.notes.emptyBody')}</p></div> : <div className="universe-note-grid">{notes.map((note) => <article className="universe-note-card" key={note.id}>
      <div className="universe-note-meta"><span>{note.date}</span><span>{note.match_id ? copy(locale, 'universe.note.matchLinked') : copy(locale, 'universe.note.personal')}</span></div>
      <h3>{note.topic}</h3>
      {hasObservationFields && note.technical_question && <p><b>{copy(locale, labels.question)}:</b> {note.technical_question}</p>}
      <p>{note.summary}</p>
      {hasObservationFields && note.next_goal && <p><b>{copy(locale, labels.next)}:</b> {note.next_goal}</p>}
      <div className="universe-actions">{note.match_id && matches.some((match) => match.match_id === note.match_id) && <button className="text-button" type="button" onClick={() => onOpenMatch(note.match_id!)}>{copy(locale, 'universe.note.openMatch')} ↗</button>}
        <button className="text-button" type="button" onClick={() => setEditing(note)}>{copy(locale, 'universe.note.edit')}</button><button className="text-button danger" type="button" onClick={() => remove(note.id)}>{copy(locale, 'universe.note.delete')}</button></div>
    </article>)}</div>}
  </section>;
}

function NoteWorkspace({ locale, data, matches, onChange, onOpenMatch, kinds, initialKind }: {
  locale: Locale; data: FanLocalData; matches: FanMatch[]; onChange: (next: FanLocalData) => boolean;
  onOpenMatch: (id: string) => void; kinds: NoteKind[]; initialKind: NoteKind;
}) {
  const [selectedKind, setSelectedKind] = useState(initialKind);
  const id = useId();
  const noteLabels: Record<NoteKind, string> = { training: 'gm.trainingNotes', match: 'gm.matchNotes', coach: 'gm.coachNotes', fan: 'gm.fanNotes' };
  return <div className="universe-note-workspace">
    <nav className="universe-note-tabs" aria-label={copy(locale, 'gm.notes')}>{kinds.map((kind) => <button type="button" key={kind} aria-pressed={selectedKind === kind} aria-controls={`${id}-${kind}`} onClick={() => setSelectedKind(kind)}>{copy(locale, noteLabels[kind])}<span>{data[noteKeys[kind]].length}</span></button>)}</nav>
    {kinds.map((kind) => <div id={`${id}-${kind}`} key={kind} hidden={selectedKind !== kind}><LocalNotes locale={locale} kind={kind} data={data} matches={matches} onChange={onChange} onOpenMatch={onOpenMatch} /></div>)}
  </div>;
}

export function TrainingPage({ locale, data, onChange, onReplace, onGoPro, onOpenMatch }: {
  locale: Locale; data: FanLocalData; onChange: (next: FanLocalData) => boolean; onReplace: (next: FanLocalData) => boolean;
  onGoPro: (focus: 'insight' | 'review') => void; onOpenMatch: (id: string) => void;
}) {
  const { matches } = usePublicMatches();
  return <section className="universe-page" data-universe-page="train">
    <header className="universe-hero compact"><FanArtwork locale={locale} kind="match" identity="ptti:training-journal" decorative /><p className="eyebrow">PTTI · TRAIN</p><h1>{copy(locale, 'universe.train.title')}</h1><p>{copy(locale, 'gm.journalIntro')}</p>
      <div className="universe-actions"><button type="button" className="button button-primary" onClick={() => onGoPro('review')}>{copy(locale, 'universe.train.openReview')}</button><button type="button" className="button button-outline" onClick={() => onGoPro('insight')}>{copy(locale, 'universe.train.openInsight')}</button></div></header>
    <NoteWorkspace locale={locale} data={data} matches={matches} onChange={onChange} onOpenMatch={onOpenMatch} kinds={['training', 'match', 'coach']} initialKind="training" />
    <LocalBackup locale={locale} data={data} onReplace={onReplace} />
  </section>;
}

export function MyCornerPage({ locale, data, onChange, onReplace, onOpenMatch, onOpenStar, onDiscover }: {
  locale: Locale; data: FanLocalData; onChange: (next: FanLocalData) => boolean; onReplace: (next: FanLocalData) => boolean;
  onOpenMatch: (id: string) => void; onOpenStar: (id: string) => void; onDiscover: () => void;
}) {
  const { catalog, matches, loading, error } = usePublicMatches();
  const matchById = new Map(matches.map((match) => [match.match_id, match]));
  const starById = new Map((catalog?.stars ?? []).map((star) => [star.athlete_id, star]));
  const allNotes = [...data.training_notes, ...data.match_notes, ...data.coach_notes, ...data.fan_notes];
  const noteCount = allNotes.length;
  const matchName = (match: FanMatch) => locale === 'zh-CN' && match.display_title_zh ? match.display_title_zh : match.participants.map((person) => { const star = person.athlete_id ? starById.get(person.athlete_id) : null; return (locale === 'zh-CN' ? star?.name_zh : star?.name_en) || person.name_en || person.athlete_id || person.side; }).join(' vs ');
  const localName = (star: NonNullable<ReturnType<typeof starById.get>>) => locale === 'zh-CN'
    ? star.name_zh || star.name_en || star.athlete_id
    : star.name_en || star.name_zh || star.athlete_id;
  return <section className="universe-page" data-universe-page="corner">
    <header className="universe-hero compact"><FanArtwork locale={locale} kind="star" identity="ptti:my-corner" decorative /><p className="eyebrow">{copy(locale, 'gm.cornerKicker')}</p><h1>{copy(locale, 'universe.corner.title')}</h1><p>{copy(locale, 'universe.corner.description')}</p>
      <button type="button" className="button button-primary" onClick={onDiscover}>{copy(locale, 'universe.corner.discover')}</button></header>
    <section className="universe-corner-grid" aria-label={copy(locale, 'universe.corner.title')}>
      <section className="universe-community-section"><div className="universe-section-head"><div><p className="eyebrow">PTTI · SAVED</p><h2>{copy(locale, 'universe.corner.savedMatches')}</h2></div><span>{data.saved_match_ids.length}</span></div>
        {loading ? <p role="status">{copy(locale, 'fan.loading')}</p> : error ? <p role="alert">{copy(locale, 'fan.loadError')}</p> : data.saved_match_ids.length === 0 ? <p className="universe-empty" role="status">{copy(locale, 'universe.corner.emptySaved')}</p> : <div className="universe-note-grid">{data.saved_match_ids.map((id) => {
          const match = matchById.get(id);
          return <article className="universe-note-card universe-saved-card" key={id} data-saved-match-id={id}>{match && <button type="button" className="universe-saved-art" onClick={() => onOpenMatch(id)} aria-label={copy(locale, 'fan.openMatch')}><FanArtwork locale={locale} kind="match" identity={id} title={matchName(match)} subtitle={locale === 'zh-CN' ? match.event_zh || match.event : match.event} /></button>}
            {match ? <><p className="eyebrow">{match.event} · {match.round}</p><h3>{matchName(match)}</h3><div className="universe-actions"><button type="button" className="button button-outline" onClick={() => onOpenMatch(id)}>{copy(locale, 'fan.openMatch')}</button><button type="button" className="text-button danger" onClick={() => onChange({ ...data, saved_match_ids: data.saved_match_ids.filter((item) => item !== id) })}>{copy(locale, 'gm.removeSaved')}</button></div></>
              : <><p role="status">{copy(locale, 'universe.corner.staleMatch')}</p><code>{id}</code><button type="button" className="text-button danger" onClick={() => onChange({ ...data, saved_match_ids: data.saved_match_ids.filter((item) => item !== id) })}>{copy(locale, 'gm.removeSaved')}</button></>}
          </article>;
        })}</div>}
      </section>
      <section className="universe-community-section"><div className="universe-section-head"><div><p className="eyebrow">PTTI · FOLLOWING</p><h2>{copy(locale, 'universe.corner.followedStars')}</h2></div><span>{data.followed_athlete_ids.length}</span></div>
        {loading ? <p role="status">{copy(locale, 'fan.loading')}</p> : error ? <p role="alert">{copy(locale, 'fan.loadError')}</p> : data.followed_athlete_ids.length === 0 ? <p className="universe-empty" role="status">{copy(locale, 'universe.corner.emptyFollowed')}</p> : <div className="universe-note-grid">{data.followed_athlete_ids.map((id) => {
          const star = starById.get(id);
          return <article className="universe-note-card universe-followed-card" key={id} data-followed-athlete-id={id}>{star && <button type="button" className="universe-saved-art" onClick={() => onOpenStar(id)} aria-label={copy(locale, 'fan.openStar')}><FanArtwork locale={locale} kind="star" identity={id} title={localName(star)} subtitle={star.association || undefined} /></button>}
            {star ? <><h3>{localName(star)}</h3><small>{star.association || copy(locale, 'metadata.noBiography')}</small><div className="universe-actions"><button type="button" className="button button-outline" onClick={() => onOpenStar(id)}>{copy(locale, 'universe.corner.openStar')}</button><button type="button" className="text-button danger" onClick={() => onChange({ ...data, followed_athlete_ids: data.followed_athlete_ids.filter((item) => item !== id) })}>{copy(locale, 'gm.unfollow')}</button></div></>
              : <><p role="status">{copy(locale, 'universe.corner.staleStar')}</p><code>{id}</code><button type="button" className="text-button danger" onClick={() => onChange({ ...data, followed_athlete_ids: data.followed_athlete_ids.filter((item) => item !== id) })}>{copy(locale, 'gm.unfollow')}</button></>}
          </article>;
        })}</div>}
      </section>
    </section>
    <section className="universe-community-section" aria-labelledby="corner-notes-title"><div className="universe-section-head"><div><p className="eyebrow">PTTI · NOTES</p><h2 id="corner-notes-title">{copy(locale, 'universe.corner.notes')}</h2></div><span>{noteCount}</span></div>
      <NoteWorkspace locale={locale} data={data} matches={matches} onChange={onChange} onOpenMatch={onOpenMatch} kinds={['fan', 'training', 'match', 'coach']} initialKind="fan" />
    </section>
    <LocalBackup locale={locale} data={data} onReplace={onReplace} />
  </section>;
}

interface GearRecord { id: string; category: string; name: string; sourceUrl: string; evidence: string }
function GearCard({ locale, item }: { locale: Locale; item: GearRecord }) {
  return <article className="universe-gear-card"><p className="eyebrow">{item.category}</p><h3>{item.name}</h3><p>{item.evidence}</p><a className="button button-outline" href={item.sourceUrl} target="_blank" rel="noopener noreferrer">{copy(locale, 'universe.gear.openSource')} ↗</a></article>;
}

function EquipmentGraphic({ category }: { category: string }) {
  return <svg className="universe-equipment-art" viewBox="0 0 400 300" aria-hidden="true">
    <circle cx="200" cy="150" r="112" fill="none" stroke="#d1576840"/><circle cx="200" cy="150" r="95" fill="#aa354511"/>
    <g fill="#171d29" stroke="#cf8b82" strokeWidth="2" strokeLinejoin="round">
      {category === 'Racket' && <g transform="rotate(-28 200 150)"><path d="M184 184h32l-2 88h-28Z" fill="#c78d65"/><ellipse cx="200" cy="116" rx="70" ry="85" fill="#9d364b"/><ellipse cx="200" cy="116" rx="60" ry="74" fill="none" stroke="#e4b39c66"/></g>}
      {category === 'Rubber' && <g><path d="m113 54 190 17-15 190-190-17Z" fill="#a4354a"/><path d="m127 47 190 17-15 190" fill="none" stroke="#d9b68e"/><path d="m117 85 150 14m-153 20 150 14m-153 20 150 14m-153 20 150 14" stroke="#f6a8a328"/></g>}
      {category === 'Shoes' && <g><path d="m76 182 50-76 57 36 50 9 30 31 62 19 4 38H72Z"/><path d="M76 221h250v18H72Z" fill="#d9bdaa"/><path d="m141 149 38 32m-23-43 40 31m-24-39 37 31" stroke="#efc4ac"/><path d="m113 188 50 17h49" fill="none" stroke="#dc465e" strokeWidth="6"/></g>}
      {category === 'Apparel' && <g><path d="m151 48-73 38 32 68 35-17-8 123h127l-8-123 35 17 31-68-72-38-49 23Z"/><path d="m151 48 50 56 49-56M158 69l43 35 43-35" fill="none" stroke="#eac4b2"/><path d="m143 184 113-51v35l-115 50Z" fill="#b83e53" stroke="none"/></g>}
    </g>
  </svg>;
}

export function GearPage({ locale }: { locale: Locale }) {
  const [category, setCategory] = useState('Racket');
  const categories = ['Racket', 'Rubber', 'Shoes', 'Apparel'];
  const labels: Record<string, string> = { Racket: 'universe.gear.racket', Rubber: 'universe.gear.rubber', Shoes: 'universe.gear.shoes', Apparel: 'universe.gear.apparel' };
  const reviewedItems: GearRecord[] = [];
  return <section className="universe-page" data-universe-page="gear"><header className="universe-hero compact"><FanArtwork locale={locale} kind="star" identity="ptti:gear" decorative /><p className="eyebrow">PTTI · GEAR</p><h1>{copy(locale, 'gm.gearHeadline')}</h1><p>{copy(locale, 'gm.gearSub')}</p></header>
    <nav className="universe-category-nav" aria-label={copy(locale, 'universe.gear.categories')}>{categories.map((item) => <button type="button" key={item} className={category === item ? 'active' : ''} aria-pressed={category === item} onClick={() => setCategory(item)}>{copy(locale, labels[item])}</button>)}</nav>
    {reviewedItems.filter((item) => item.category === category).map((item) => <GearCard item={item} locale={locale} key={item.id} />)}
    {reviewedItems.length === 0 && <div className="universe-empty universe-gear-discovery" role="status" data-gear-category={category}><EquipmentGraphic category={category} /><div><p className="eyebrow">PTTI · GEAR</p><h2>{copy(locale, labels[category])}</h2><strong>{copy(locale, 'universe.gear.emptyTitle')}</strong><p>{copy(locale, 'universe.gear.emptyBody')}</p><small>{copy(locale, 'universe.gear.evidenceRule')}</small></div></div>}
  </section>;
}

export function CommunityPage({ locale, data, onChange, onReplace, onOpenMatch }: {
  locale: Locale; data: FanLocalData; onChange: (next: FanLocalData) => boolean; onReplace: (next: FanLocalData) => boolean; onOpenMatch: (id: string) => void;
}) {
  const { catalog, matches } = usePublicMatches();
  const currentMatch = matches[0];
  return <section className="universe-page" data-universe-page="community"><header className="universe-hero compact"><FanArtwork locale={locale} kind="match" identity="ptti:community" decorative /><p className="eyebrow">PTTI · COMMUNITY</p><h1>{copy(locale, 'gm.communityHeadline')}</h1><p>{copy(locale, 'universe.community.description')}</p></header>
    <nav className="universe-community-nav" aria-label={copy(locale, 'universe.community.sections')}><a href="#official-news">{copy(locale, 'universe.community.officialNews')}</a><a href="#global-discussions">{copy(locale, 'universe.community.discussions')}</a><a href="#fan-notes">{copy(locale, 'universe.community.fanNotes')}</a><a href="#community-links">{copy(locale, 'universe.community.links')}</a></nav>
    <section id="official-news" className="universe-community-section"><p className="eyebrow">{copy(locale, 'universe.community.officialNews')}</p><h2>{copy(locale, 'universe.community.officialSourceTitle')}</h2>
      {currentMatch?.reference_url ? <article className="universe-source-card"><span>{copy(locale, 'universe.community.sourceKind')}</span><h3>{currentMatch.event} · {currentMatch.round}</h3><p>{copy(locale, 'universe.community.sourceNotice')}</p><div className="universe-actions"><a className="button button-outline" href={currentMatch.reference_url} target="_blank" rel="noopener noreferrer">{copy(locale, 'universe.community.openOfficial')} ↗</a><button type="button" className="text-button" onClick={() => onOpenMatch(currentMatch.match_id)}>{copy(locale, 'universe.note.openMatch')}</button></div></article> : <div className="universe-empty"><strong>{copy(locale, 'universe.community.emptyTitle')}</strong><p>{copy(locale, 'universe.community.emptyBody')}</p></div>}</section>
    <section id="global-discussions" className="universe-community-section"><p className="eyebrow">{copy(locale, 'universe.community.discussions')}</p><div className="universe-empty"><strong>{copy(locale, 'universe.community.noDiscussions')}</strong><p>{copy(locale, 'universe.community.noDiscussionsBody')}</p></div></section>
    <section id="fan-notes" className="universe-community-section"><LocalNotes locale={locale} kind="fan" data={data} matches={matches} onChange={onChange} onOpenMatch={onOpenMatch} /></section>
    <section id="community-links" className="universe-community-section"><p className="eyebrow">{copy(locale, 'universe.community.links')}</p><h2>{copy(locale, 'universe.community.linksTitle')}</h2>
      {catalog?.sources.filter((source) => source.external_viewing === 'ALLOWED' && source.url).map((source) => <article className="universe-source-card" key={source.source_id}><span>{source.platform} · {copy(locale, 'universe.community.externalLink')}</span><h3>{source.title}</h3><a className="button button-outline" href={source.url!} target="_blank" rel="noopener noreferrer">{copy(locale, 'universe.community.openOriginal')} ↗</a></article>)}
      {!catalog?.sources.some((source) => source.external_viewing === 'ALLOWED' && source.url) && <div className="universe-empty"><strong>{copy(locale, 'universe.community.emptyLinks')}</strong><p>{copy(locale, 'universe.community.noAutoSync')}</p></div>}
    </section><LocalBackup locale={locale} data={data} onReplace={onReplace} />
  </section>;
}
