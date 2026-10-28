'use client';

import { useState } from 'react';
import { Bug } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { getRawSnapshot, startDebugCapture, stopDebugCapture } from '@/lib/api/intel';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

const inputClass =
  'w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50';

/** Section 16/22's Diagnostics card: admin-only (enforced server-side by
 * require_admin — this component's own role check is a UX convenience,
 * never the actual boundary). Bounded debug capture using only the
 * existing safe snapshot requests, and a redacted raw account_snapshot —
 * never an arbitrary packet-construction "raw" console. */
export function DiagnosticsPanel({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { user } = useAuthSession();
  const [seconds, setSeconds] = useState('10');
  const [capturing, setCapturing] = useState(false);
  const [captureResult, setCaptureResult] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const isAdmin = user?.role === 'admin';

  async function handleStart() {
    setPending(true);
    setError(null);
    try {
      await startDebugCapture(accountId, Number(seconds) || 10);
      setCapturing(true);
      setCaptureResult(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start capture.');
    } finally {
      setPending(false);
    }
  }

  async function handleStop() {
    setPending(true);
    setError(null);
    try {
      const result = await stopDebugCapture(accountId);
      setCapturing(false);
      setCaptureResult(`Captured ${result.message_count} message(s)${result.log_path ? ` — ${result.log_path}` : ''}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not stop capture.');
    } finally {
      setPending(false);
    }
  }

  async function handleRawSnapshot() {
    setPending(true);
    setError(null);
    try {
      const result = await getRawSnapshot(accountId);
      setSnapshot(JSON.stringify(result.snapshot, null, 2));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load snapshot.');
    } finally {
      setPending(false);
    }
  }

  if (!isAdmin) return null;

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Bug className="h-4 w-4 text-muted-foreground" />
            Diagnostics
          </span>
        }
        description="Admin-only. Bounded protocol capture and a redacted account snapshot — never raw packet construction."
      />
      <CardContent className="space-y-4">
        <div>
          <p className="mb-2 text-sm font-medium text-foreground">Debug capture</p>
          <div className="flex items-center gap-2">
            <input
              className={`${inputClass} w-24`}
              type="number"
              min={1}
              max={60}
              value={seconds}
              onChange={(e) => setSeconds(e.target.value)}
              aria-label="Capture duration (seconds)"
              disabled={capturing}
            />
            {capturing ? (
              <Button size="sm" variant="danger" loading={pending} onClick={handleStop}>Stop capture</Button>
            ) : (
              <Button size="sm" variant="secondary" disabled={!connected} loading={pending} onClick={handleStart}>Start capture</Button>
            )}
          </div>
          {captureResult && <p className="mt-2 text-xs text-muted-foreground">{captureResult}</p>}
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-foreground">Raw snapshot</p>
          <Button size="sm" variant="outline" loading={pending} onClick={handleRawSnapshot}>Load redacted snapshot</Button>
          {snapshot && (
            <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-surface-muted p-3 text-xs text-foreground">{snapshot}</pre>
          )}
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}
      </CardContent>
    </Card>
  );
}
