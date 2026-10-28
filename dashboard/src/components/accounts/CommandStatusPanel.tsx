'use client';

import useSWR from 'swr';
import { getCommandStatus } from '@/lib/api/actions';
import type { CommandObservation } from '@/lib/api/types';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { formatUnixSeconds } from '@/lib/utils/format';

const reasons: Record<CommandObservation['reason'], string> = {
  waiting_for_reply: 'Waiting for a matching reply',
  timeout: 'No matching reply before the wait ended',
  cancelled: 'Waiting was cancelled; a sent command may still execute',
  disconnected: 'Connection closed; a sent command may still execute',
  send_uncertain: 'Send outcome unknown',
  confirmed_reply: 'Matching reply observed',
  explicit_rejection: 'Matching rejection observed',
  not_sent: 'Failed before sending',
  awaiting_idle_observation: 'Dispatch confirmed; truck held until a subsequent idle observation',
  idle_observed: 'Subsequent idle observation released the truck',
};
const names = { collect: 'Collection', gather: 'Gather', search: 'Mine search', vehicles: 'Vehicle observation' };

function Observation({ item }: { item: CommandObservation }) {
  return (
    <li className="border-b border-border py-2 text-sm">
      <p className="font-medium">
        {names[item.kind]} — {item.status.replaceAll('_', ' ')}
        {item.vehicle_id != null && ` · truck ${item.vehicle_id}`}
        {item.building_id != null && ` · building ${item.building_id}`}
      </p>
      <p>{reasons[item.reason]}</p>
      <p className="text-muted-foreground">
        {Math.floor(item.age_seconds)}s since request
        {item.reservation !== 'none' && ` · ${item.reservation} reservation held`}
      </p>
    </li>
  );
}

export function CommandStatusPanel({ accountId }: { accountId: string }) {
  const { data, error, isLoading, mutate } = useSWR(
    ['command-status', accountId], () => getCommandStatus(accountId),
    { refreshInterval: 5_000 },
  );
  return (
    <Card>
      <CardHeader title="Command confirmation" description="Read-only report. Updating it sends no game requests and releases no reservations." />
      <CardContent className="space-y-3">
        <p className="text-sm">Upstream confirmation evidence remains unverified. Do not retry an uncertain command or reconnect just to clear a reservation.</p>
        {error ? <ErrorState error={error} title="Command report unavailable" onRetry={() => mutate()} />
          : isLoading || !data ? <p>Loading command report…</p> : <>
            <p className="text-sm text-muted-foreground">
              History covers only the current connection, with at most 50 completed observations.
              Empty results do not establish the outcome of earlier commands. Restart or reconnect clears this history.
            </p>
            <p className="text-sm">{data.connected ? 'Connected' : 'Disconnected'} · Observation started: {formatUnixSeconds(data.tracking_started_at)}</p>
            {!data.observation_id && <p>No connection history is available.</p>}
            <p className="text-sm">Tracking capacity: {data.tracked_requests}/{data.tracking_limit}. {data.recent_dropped} older completed observations omitted.</p>
            {data.tracked_requests >= data.tracking_limit && <p role="alert">Tracking capacity reached. New tracked sends are refused; operator reconciliation is required.</p>}
            {data.active.length === 0 ? <p>No active reservations observed in this connection.</p> : <>
              <p className="font-medium">Active observations ({data.active.length})</p>
              <ul>{data.active.slice(0, 50).map(item => <Observation key={item.operation_id} item={item} />)}</ul>
              {data.active.length > 50 && <details>
                <summary>More active observations ({data.active.length - 50})</summary>
                <ul>{data.active.slice(50).map(item => <Observation key={item.operation_id} item={item} />)}</ul>
              </details>}
            </>}
            {data.recent.length > 0 && <details>
              <summary>Recent completed observations ({data.recent.length})</summary>
              <ul>{data.recent.map(item => <Observation key={item.operation_id} item={item} />)}</ul>
            </details>}
            <button type="button" className="text-sm underline" onClick={() => mutate()}>Update report</button>
          </>}
      </CardContent>
    </Card>
  );
}
