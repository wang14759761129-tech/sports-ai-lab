// Clock-gated adapter for the existing MOCK event reducer. No real-media claims.
import {arenaStep,pendingEvent} from './gex-moment/arena-events.mjs';
export function revealAt(state, seconds) {
 const event=pendingEvent(state);
 if (!event || !Number.isFinite(seconds) || seconds < event.timestamp) return state;
 return arenaStep(state,'reveal');
}
