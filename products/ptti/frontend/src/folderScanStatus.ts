export function folderScanCountText(status: string, candidateCount: number): string {
  if (status === 'QUEUED' || status === 'RUNNING') {
    return '扫描尚未完成，媒体数量将在完成后显示';
  }
  if (status === 'FAILED') return '预览未完成，请查看错误提示后重试';
  if (status === 'INTERRUPTED') return `预览已中断，保留 ${candidateCount} 个已读取文件`;
  return `发现 ${candidateCount} 个支持的媒体文件`;
}

export function pendingVideoReviews(scan: {candidates?: {registered_video_id?: string; duplicate_of_candidate_id?: string}[]}): number {
  return (scan.candidates || []).filter(c => !c.registered_video_id && !c.duplicate_of_candidate_id).length;
}

export function selectFolderPreview<T extends {scan_id: string; status: string; candidates?: {registered_video_id?: string; duplicate_of_candidate_id?: string}[]}>(scans: T[], selectedId: string): T | undefined {
  return scans.find(s => s.scan_id === selectedId) ||
    scans.find(s => ['QUEUED','RUNNING'].includes(s.status)) ||
    scans.find(s => ['COMPLETED','INTERRUPTED'].includes(s.status) && pendingVideoReviews(s) > 0) || scans[0];
}

export function canRegisterLocalVideo(draft: {rights_confirmed?: boolean; rights_status?: string; source_note?: string}): boolean {
  return draft.rights_confirmed === true &&
    ['USER_OWNED','LICENSED','USER_SELF_CAPTURED','LICENSED_FOR_ANALYSIS','PERSONAL_VIEW_ONLY','RESEARCH_NONCOMMERCIAL'].includes(draft.rights_status || '') &&
    !!draft.source_note?.trim() && draft.source_note.trim() !== '来源待逐条核实';
}

export function updateVideoReview(draft: Record<string,any>, patch: Record<string,any>): Record<string,any> {
  return {...draft, ...patch, ...('rights_status' in patch || 'source_note' in patch ? {rights_confirmed:false} : {})};
}
