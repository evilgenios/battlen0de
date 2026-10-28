'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut } from 'lucide-react';
import { Button, type ButtonSize } from '@/components/ui/Button';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { logout } from '@/lib/api/auth';
import { useToast } from '@/components/ui/Toast';

export function LogoutButton({ size = 'sm' }: { size?: ButtonSize }) {
  const [pending, setPending] = useState(false);
  const router = useRouter();
  const toast = useToast();
  const { clear } = useAuthSession();

  async function handleLogout() {
    if (pending) return;
    setPending(true);
    try {
      await logout();
      clear();
      router.push('/login');
      router.refresh();
    } catch {
      toast.error('Logout failed', 'Could not reach the dashboard server.');
    } finally {
      setPending(false);
    }
  }

  return (
    <Button size={size} variant="outline" icon={<LogOut className="h-3.5 w-3.5" />} loading={pending} onClick={handleLogout}>
      Log out
    </Button>
  );
}
