import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { formatEventType } from '@/lib/utils/format';

export type EventOutcome = 'success' | 'error' | 'info';

/** The backend doesn't attach a structured "outcome" to events (see
 * app/main.py's _SESSION_EVENT_TYPE and app/api/*.py's repo.add_event
 * calls) — it's inferred here from the event_type naming convention, which
 * is consistent across the whole backend (…_failed / …_restricted read as
 * errors, …_requested / …_started read as in-progress, everything else as
 * a completed, successful action). */
export function classifyEvent(eventType: string): EventOutcome {
  if (eventType.includes('failed') || eventType.includes('restricted')) return 'error';
  if (eventType.includes('requested') || eventType.includes('started')) return 'info';
  return 'success';
}

const OUTCOME_TONE: Record<EventOutcome, BadgeTone> = {
  success: 'success',
  error: 'danger',
  info: 'info',
};

export function EventTypeBadge({ eventType }: { eventType: string }) {
  const outcome = classifyEvent(eventType);
  return <Badge tone={OUTCOME_TONE[outcome]}>{formatEventType(eventType)}</Badge>;
}
