'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Trash2 } from 'lucide-react';
import { Button, type ButtonSize } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useAccountActions } from '@/lib/hooks/useAccountActions';

export function DeleteAccountButton({
  accountId,
  accountLabel,
  size = 'sm',
  redirectAfterDelete = false,
}: {
  accountId: string;
  accountLabel: string;
  size?: ButtonSize;
  /** From the details page: leave the (now 404) page after deleting. */
  redirectAfterDelete?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const actions = useAccountActions(accountId);
  const router = useRouter();

  const handleConfirm = async () => {
    const outcome = await actions.remove();
    setOpen(false);
    if (outcome.ok && redirectAfterDelete) {
      router.push('/accounts');
    }
  };

  return (
    <>
      <Button
        size={size}
        variant="ghost"
        icon={<Trash2 className="h-3.5 w-3.5" />}
        onClick={() => setOpen(true)}
        className="text-danger hover:bg-danger/10"
      >
        Delete
      </Button>
      <ConfirmDialog
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={handleConfirm}
        title="Delete account"
        description={
          <>
            Permanently delete <span className="font-medium text-foreground">{accountLabel}</span>? This
            disconnects it immediately and removes it from the dashboard. This cannot be undone.
          </>
        }
        confirmLabel="Delete account"
        destructive
      />
    </>
  );
}
