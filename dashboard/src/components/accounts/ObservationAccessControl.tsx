'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { Eye, PauseCircle, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { describeError } from '@/components/ui/ErrorState';
import { useToast } from '@/components/ui/Toast';
import {
  authorizeObservation,
  getPilotActivation,
  pauseObservation,
} from '@/lib/api/accounts';

export function ObservationAccessControl({
  accountId,
  canAuthorize,
}: {
  accountId: string;
  canAuthorize: boolean;
}) {
  const toast = useToast();
  const [pending, setPending] = useState<'15' | '60' | 'pause' | null>(null);
  const [nowSeconds, setNowSeconds] = useState(0);
  const { data, error, isLoading, mutate } = useSWR(
    ['pilot-activation', accountId],
    () => getPilotActivation(accountId),
    { refreshInterval: 5_000, revalidateOnFocus: true },
  );

  useEffect(() => {
    if (data?.mode !== 'observe') return;
    const update = () => setNowSeconds(Date.now() / 1000);
    const firstUpdate = setTimeout(update, 0);
    const interval = setInterval(update, 30_000);
    return () => {
      clearTimeout(firstUpdate);
      clearInterval(interval);
    };
  }, [data?.mode, data?.expires_at]);

  const minutesLeft = useMemo(() => {
    if (!data?.expires_at || data.mode !== 'observe' || nowSeconds <= 0) return null;
    return Math.max(0, Math.ceil((data.expires_at - nowSeconds) / 60));
  }, [data?.expires_at, data?.mode, nowSeconds]);

  async function authorize(minutes: 15 | 60) {
    if (pending) return;
    setPending(String(minutes) as '15' | '60');
    try {
      await authorizeObservation(accountId, minutes);
      await mutate();
      toast.success(`Observation authorized for ${minutes} minutes`);
    } catch (cause) {
      toast.error('Observation authorization failed', describeError(cause));
    } finally {
      setPending(null);
    }
  }

  async function pause() {
    if (pending) return;
    setPending('pause');
    try {
      await pauseObservation(accountId);
      await mutate();
      toast.success('Observation paused');
    } catch (cause) {
      toast.error('Could not pause observation', describeError(cause));
    } finally {
      setPending(null);
    }
  }

  if (isLoading && !data) {
    return (
      <div className="data-chip inline-flex h-10 items-center gap-2 rounded-xl px-3 text-xs text-muted-foreground">
        <Eye className="h-3.5 w-3.5" />
        Checking observation access…
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="rounded-xl border border-danger/25 bg-danger/5 px-3 py-2 text-xs text-danger">
        Could not read observation access.
      </div>
    );
  }

  if (data?.mode === 'observe') {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-success/20 bg-success/5 px-3 py-2">
        <ShieldCheck className="h-4 w-4 text-success" />
        <Badge tone="success">Observation active</Badge>
        <span className="text-[11px] text-muted-foreground">
          {minutesLeft ?? '—'} min left · automation disabled; verified manual controls may be available
        </span>
        <Button
          size="sm"
          variant="ghost"
          icon={<PauseCircle className="h-3.5 w-3.5" />}
          loading={pending === 'pause'}
          disabled={pending !== null}
          onClick={pause}
        >
          Pause
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-warning/25 bg-warning/5 px-3 py-2">
      <Eye className="h-4 w-4 text-warning" />
      <Badge tone="warning">
        {data?.reason === 'expired' ? 'Observation expired' : 'Observation required'}
      </Badge>
      {canAuthorize ? (
        <>
          <Button
            size="sm"
            variant="outline"
            loading={pending === '15'}
            disabled={pending !== null}
            onClick={() => authorize(15)}
          >
            Authorize 15 min
          </Button>
          <Button
            size="sm"
            variant="primary"
            loading={pending === '60'}
            disabled={pending !== null}
            onClick={() => authorize(60)}
          >
            Authorize 60 min
          </Button>
        </>
      ) : (
        <span className="text-[11px] text-muted-foreground">
          An admin must authorize observation before this account can connect.
        </span>
      )}
    </div>
  );
}
