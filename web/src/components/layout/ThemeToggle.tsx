'use client';

import React from 'react';

import Icon from '@/components/ui/Icon';
import { cx } from '@/components/ui/primitives';
import { useTheme } from '@/lib/theme';

/**
 * Render the Dark/Light appearance switch.
 *
 * The palette is applied by toggling a class on the document element, so
 * every token, including the ones Tailwind generates utilities from, changes at
 * once and nothing is left on the previous theme.
 *
 * @returns A pressable theme switch with the active palette named.
 */
export default function ThemeToggle({ className, compact = false }: { className?: string; compact?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === 'dark';
  const next = dark ? 'light' : 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-pressed={dark}
      aria-label={'Switch to ' + next + ' theme'}
      title={'Switch to ' + next + ' theme'}
      className={cx(
        'flex items-center gap-2 rounded-md border border-line-strong bg-panel-alt font-semibold text-text-dim transition-colors',
        compact ? 'h-8 w-8 justify-center p-1.5 text-[11px]' : 'w-full justify-between px-2.5 py-1.5 text-[11.5px]',
        'hover:border-line-contrast hover:bg-hover hover:text-text',
        className,
      )}
    >
      <span className="inline-flex items-center gap-2">
        <Icon name={dark ? 'moon' : 'sun'} size={14} />
        {!compact ? 'Appearance' : null}
      </span>
      {!compact ? (
        <span className="rounded-pill border border-chip-line bg-chip-fill px-1.5 py-0.5 text-[10px] uppercase tracking-[0.06em] text-text">
          {dark ? 'Dark' : 'Light'}
        </span>
      ) : null}
    </button>
  );
}
