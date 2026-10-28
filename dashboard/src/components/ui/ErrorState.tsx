import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return error.message;
    return `${error.message} (HTTP ${error.status})`;
  }
  if (error instanceof Error) return error.message;
  return 'Something went wrong.';
}

export function ErrorState({
  error,
  onRetry,
  title = 'Could not load this data',
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger/10">
        <AlertTriangle className="h-6 w-6 text-danger" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{describeError(error)}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export { describeError };
