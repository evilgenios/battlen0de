'use client';

import { Play, Power, RotateCw } from 'lucide-react';
import { Button, type ButtonSize } from '@/components/ui/Button';
import { useAccountActions } from '@/lib/hooks/useAccountActions';
import type { SessionState } from '@/lib/api/types';

const CONNECTABLE_STATES: (SessionState | null)[] = [null, 'idle', 'stopped', 'failed', 'restricted'];
const DISCONNECTABLE_STATES: SessionState[] = ['connected', 'connecting', 'reconnecting'];

export function ConnectionControls({
  accountId,
  liveState,
  size = 'sm',
}: {
  accountId: string;
  liveState: SessionState | null | undefined;
  size?: ButtonSize;
}) {
  const actions = useAccountActions(accountId);
  const state = liveState ?? null;

  const canConnect = CONNECTABLE_STATES.includes(state);
  const canDisconnect = DISCONNECTABLE_STATES.includes(state as SessionState);
  const canReconnect = state !== null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        size={size}
        variant="primary"
        icon={<Play className="h-3.5 w-3.5" />}
        disabled={!canConnect}
        loading={actions.pending === 'connect'}
        onClick={actions.connect}
      >
        Connect
      </Button>
      <Button
        size={size}
        variant="outline"
        icon={<Power className="h-3.5 w-3.5" />}
        disabled={!canDisconnect}
        loading={actions.pending === 'disconnect'}
        onClick={actions.disconnect}
      >
        Disconnect
      </Button>
      <Button
        size={size}
        variant="outline"
        icon={<RotateCw className="h-3.5 w-3.5" />}
        disabled={!canReconnect}
        loading={actions.pending === 'reconnect'}
        onClick={actions.reconnect}
      >
        Reconnect
      </Button>
    </div>
  );
}
