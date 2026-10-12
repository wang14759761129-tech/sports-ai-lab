export function folderScanCountText(status: string, candidateCount: number): string {
  if (status === 'QUEUED' || status === 'RUNNING') {
    return '扫描尚未完成，媒体数量将在完成后显示';
  }
  return `发现 ${candidateCount} 个支持的媒体文件`;
}
