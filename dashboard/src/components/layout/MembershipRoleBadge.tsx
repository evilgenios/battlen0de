'use client';

import { Badge } from '@/components/ui/Badge';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

export function MembershipRoleBadge() {
  const { user } = useAuthSession();
  if (!user) return null;
  if (user.role === 'admin') return <Badge tone="warning">Administrator</Badge>;
  if (!user.plan) return <Badge>Member</Badge>;
  return <Badge tone={user.plan === 'alliance' ? 'info' : 'accent'}>{user.plan === 'alliance' ? 'Alliance Member' : 'Individual Member'}</Badge>;
}
