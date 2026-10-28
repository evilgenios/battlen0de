export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  const diffMs = date.getTime() - Date.now();
  const diffSeconds = Math.round(diffMs / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 60 * 60 * 24 * 365],
    ['month', 60 * 60 * 24 * 30],
    ['day', 60 * 60 * 24],
    ['hour', 60 * 60],
    ['minute', 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

  for (const [unit, secondsInUnit] of units) {
    if (Math.abs(diffSeconds) >= secondsInUnit) {
      return formatter.format(Math.round(diffSeconds / secondsInUnit), unit);
    }
  }
  return formatter.format(diffSeconds, 'second');
}

/** started_at/last_connected_at on LiveSessionStatus are Unix seconds
 * (Python's time.time()), not ISO strings — see app/core/account_session.py. */
export function formatUnixSeconds(value: number | null | undefined): string {
  if (value == null) return '—';
  return formatDateTime(new Date(value * 1000).toISOString());
}

/** Formats a real server end_time (Unix seconds) as a countdown string
 * ("Ready" once passed) — this only formats a genuine server timestamp,
 * it never invents progress or a duration the server didn't provide. */
export function formatCountdown(endTimeUnixSeconds: number | null | undefined): string {
  if (!endTimeUnixSeconds) return '—';
  const remainingMs = endTimeUnixSeconds * 1000 - Date.now();
  if (remainingMs <= 0) return 'Ready';
  const totalSeconds = Math.floor(remainingMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`;
}

/** Progress 0-100 derived purely from two real server timestamps — never
 * fabricated, and returns null (not 0) when either timestamp is missing so
 * callers can distinguish "no real progress data" from "0% done". */
export function calculateProgress(startTime: number | null | undefined, endTime: number | null | undefined): number | null {
  if (!startTime || !endTime || endTime <= startTime) return null;
  const now = Date.now() / 1000;
  const fraction = (now - startTime) / (endTime - startTime);
  return Math.max(0, Math.min(100, fraction * 100));
}

export function formatEventType(eventType: string): string {
  return eventType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
