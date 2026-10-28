'use client';

import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/Button';

const STORAGE_KEY = 'warpath-dashboard-theme';

function applyTheme(theme: 'light' | 'dark') {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark' | null>(null);

  useEffect(() => {
    // Reads a client-only value (the class the blocking THEME_INIT_SCRIPT
    // already applied to <html> before hydration — see ThemeToggle.tsx's
    // other export). This can't be a lazy useState initializer instead:
    // that would run during SSR too (where `document` doesn't exist) and
    // then again differently on the client's first render, producing a
    // hydration mismatch. Rendering null -> setting the real value here is
    // the standard fix for exactly that class of problem.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  }, []);

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    applyTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private browsing / storage disabled — theme just won't persist.
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggle}
      aria-label="Toggle color theme"
      className="w-9 justify-center px-0"
    >
      {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

/** Inline, blocking script rendered in <head> so the correct theme class is
 * on <html> before first paint — avoids a light-then-dark flash. Must stay
 * a plain string (no external state) since it runs before React hydrates. */
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}');
    var theme = stored === 'dark' || stored === 'light'
      ? stored
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    if (theme === 'dark') document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;
