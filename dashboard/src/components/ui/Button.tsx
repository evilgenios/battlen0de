'use client';

import { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
export type ButtonSize = 'sm' | 'md';

const VARIANT_STYLES: Record<ButtonVariant, string> = {
  primary:
    'border border-accent/45 bg-[linear-gradient(135deg,var(--color-accent),color-mix(in_srgb,var(--color-accent)_68%,var(--color-info)))] text-white shadow-[0_10px_30px_color-mix(in_srgb,var(--color-accent)_22%,transparent)] hover:-translate-y-0.5 hover:brightness-110 disabled:opacity-50',
  secondary:
    'border border-border/80 bg-surface-muted/80 text-foreground hover:border-accent/25 hover:bg-surface-muted disabled:opacity-50',
  outline:
    'border border-border/90 bg-surface/30 text-foreground backdrop-blur-sm hover:border-accent/40 hover:bg-accent/5 disabled:opacity-50',
  ghost:
    'border border-transparent bg-transparent text-foreground hover:border-border/60 hover:bg-surface-muted/70 disabled:opacity-40',
  danger:
    'border border-danger/35 bg-danger text-white shadow-[0_8px_24px_color-mix(in_srgb,var(--color-danger)_18%,transparent)] hover:brightness-110 disabled:opacity-50',
};

const SIZE_STYLES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', loading = false, icon, disabled, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-xl font-semibold tracking-[-0.01em] transition-[transform,filter,background-color,border-color,box-shadow] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:cursor-not-allowed disabled:transform-none',
        VARIANT_STYLES[variant],
        SIZE_STYLES[size],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});
