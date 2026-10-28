'use client';

import { Badge } from '@/components/ui/Badge';
import { useHealth } from '@/lib/hooks/useHealth';

export function HealthIndicator() {
  const { health, isDown, isLoading } = useHealth();

  if (isLoading && !health) {
    return <Badge tone="neutral">Checking backend…</Badge>;
  }
  if (isDown) {
    return (
      <Badge tone="danger" dot>
        Backend unreachable
      </Badge>
    );
  }
  return (
    <Badge tone="success" dot>
      Backend online
    </Badge>
  );
}
