import { writeFileSync } from 'node:fs';
export function preserveBlockedEvidence(file, report, current, error) {
 report.status='BLOCKED'; if(current)current.status='BLOCKED';
 writeFileSync(file,JSON.stringify({...report,resource_block:error.message},null,2));
}
