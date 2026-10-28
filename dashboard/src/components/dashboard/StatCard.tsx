import type { LucideIcon } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils/cn';

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'neutral',
  loading = false,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  tone?: 'neutral' | 'success' | 'warning' | 'danger';
  loading?: boolean;
}) {
  const toneStyles: Record<string, string> = {
    neutral: 'border-info/15 bg-info/8 text-info',
    success: 'border-success/20 bg-success/10 text-success',
    warning: 'border-warning/20 bg-warning/10 text-warning',
    danger: 'border-danger/20 bg-danger/10 text-danger',
  };

  return (
    <Card className="premium-lift group p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">{label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground">
            {loading ? <span className="skeleton inline-block h-8 w-14 rounded-lg" /> : value}
          </p>
        </div>
        <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl border shadow-inner', toneStyles[tone])}>
          <Icon className="h-[18px] w-[18px]" />
        </div>
      </div>
      <div className="mt-5 h-px overflow-hidden bg-border/65">
        <div className="h-full w-1/3 bg-gradient-to-r from-accent via-info to-transparent opacity-60 transition-all duration-500 group-hover:w-2/3" />
      </div>
    </Card>
  );
}
