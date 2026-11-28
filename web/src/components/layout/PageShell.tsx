'use client';

import React from 'react';

import { cx } from '@/components/ui/primitives';

/**
 * Scroll owner for a standard page.
 *
 * The workspace layout keeps the viewport fixed and the sidebar in place, so
 * each page has to declare its own scroll region. Chat does not use this shell
 * because its transcript scrolls independently of the composer.
 *
 * @param props - Page content and optional width classes.
 * @returns A bounded, scrollable page column.
 */
export default function PageShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="aa-scroll h-full overflow-y-auto">
      <div className={cx('mx-auto w-full max-w-[1500px] px-4 py-5 sm:px-6', className)}>{children}</div>
    </div>
  );
}

/**
 * Render a page heading with an optional description and actions.
 *
 * @param props - Heading text, supporting copy, and trailing controls.
 * @returns Page header block.
 */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
      <div className="min-w-0">
        <h1 className="text-[17px] font-bold leading-tight tracking-[-0.02em] text-text">{title}</h1>
        {description ? <p className="mt-0.5 text-[12px] text-text-dim">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
