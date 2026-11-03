/** Convert source-player seconds to the optional millisecond draft field. */
export function scoreSecondsDraft(value: string): string {
  if (value === '') return '';
  return String(Math.round(Number(value) * 1000));
}
