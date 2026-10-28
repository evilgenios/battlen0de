/** Renders nothing (not a 0% bar) when `value` is null — a real progress
 * bar should only ever appear when it's backed by real timestamps; see
 * lib/utils/format.ts's calculateProgress. */
export function ProgressBar({ value, className = '' }: { value: number | null; className?: string }) {
  if (value == null) return null;
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-surface-muted ${className}`}>
      <div
        className="h-full rounded-full bg-accent transition-[width] duration-1000 ease-linear"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}
