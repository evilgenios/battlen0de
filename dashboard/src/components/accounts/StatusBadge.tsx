import { Badge, type BadgeTone } from '@/components/ui/Badge';
import type { SessionState } from '@/lib/api/types';

const STATE_LABEL: Record<SessionState, string> = {
  idle: 'Idle',
  connecting: 'Connecting',
  connected: 'Connected',
  reconnecting: 'Reconnecting',
  stopped: 'Disconnected',
  failed: 'Failed',
  restricted: 'Restricted',
};

const STATE_TONE: Record<SessionState, BadgeTone> = {
  idle: 'neutral',
  connecting: 'info',
  connected: 'success',
  reconnecting: 'warning',
  stopped: 'neutral',
  failed: 'danger',
  restricted: 'danger',
};

/** `state` is null when this worker process has never registered a live
 * AccountSession for the account (e.g. created but never connected). */
export function StatusBadge({ state }: { state: SessionState | null | undefined }) {
  if (!state) {
    return (
      <Badge tone="neutral" dot>
        Never connected
      </Badge>
    );
  }
  return (
    <Badge tone={STATE_TONE[state]} dot>
      {STATE_LABEL[state]}
    </Badge>
  );
}
