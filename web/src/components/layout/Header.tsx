'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import Icon, { type IconName } from '@/components/ui/Icon';
import { cx } from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';
import ThemeToggle from './ThemeToggle';

const LINKS: { href: string; label: string; icon: IconName }[] = [
  { href: '/workspace/api', label: 'API Workspace', icon: 'plug' },
  { href: '/workspace/test-cases', label: 'Test Cases', icon: 'flask' },
  { href: '/workspace/chat', label: 'Project Chat', icon: 'chat' },
  { href: '/workspace/activity', label: 'Activity', icon: 'pulse' },
];

/**
 * Render the workspace breadcrumb and the narrow-screen navigation strip.
 *
 * @returns Header element.
 */
export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { project } = useProject();
  const current = LINKS.find((link) => pathname === link.href || pathname.startsWith(link.href + '/'));
  const title = current ? current.label : 'Workspace';
  const signOut = async () => {
    await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
    router.replace('/login');
  };

  return (
    <header className="shrink-0 border-b border-line bg-rail">
      <div className="flex h-12 items-center gap-2 px-4">
        <span className="text-[12.5px] font-bold tracking-[-0.01em] text-text">Api-Agent</span>
        <Icon name="chevronRight" size={12} className="text-text-mute" />
        <span className="truncate text-[12px] font-medium text-text-dim">{title}</span>
        <span className="ml-auto hidden min-w-0 items-center gap-1.5 sm:flex">
          <Icon name="database" size={12} className="text-text-mute" />
          <span className="truncate font-mono text-[10.5px] text-text-mute">
            {project ? project.name : 'No project selected'}
          </span>
        </span>
        <span className="ml-auto md:hidden">
          <ThemeToggle compact className="border-0 bg-transparent" />
        </span>
        <button type="button" title="Sign out" aria-label="Sign out" onClick={() => void signOut()} className="rounded p-1.5 text-text-dim hover:bg-hover hover:text-text md:hidden">
          <Icon name="close" size={15} />
        </button>
      </div>
      <nav className="aa-scroll flex items-center gap-1 overflow-x-auto border-t border-line px-2 py-1.5 md:hidden">
        {LINKS.map((link) => {
          const active = pathname === link.href || pathname.startsWith(link.href + '/');
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cx(
                'inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[11.5px] font-semibold',
                active ? 'bg-accent-soft text-text' : 'text-text-dim hover:bg-hover hover:text-text',
              )}
            >
              <Icon name={link.icon} size={13} />
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
