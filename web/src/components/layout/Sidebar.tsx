'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import Icon, { type IconName } from '@/components/ui/Icon';
import { Button, Input, cx } from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';
import { api } from '@/lib/api';
import ThemeToggle from './ThemeToggle';

interface NavEntry {
  label: string;
  href: string;
  icon: IconName;
  hint: string;
}

const NAV: NavEntry[] = [
  { label: 'API Workspace', href: '/workspace/api', icon: 'plug', hint: 'Compose and send requests' },
  { label: 'Test Cases', href: '/workspace/test-cases', icon: 'flask', hint: 'Generate and run suites' },
  { label: 'Project Chat', href: '/workspace/chat', icon: 'chat', hint: 'Talk through the product' },
  { label: 'Activity', href: '/workspace/activity', icon: 'pulse', hint: 'Generation and extraction logs' },
];

/**
 * Render the persistent project rail and workspace navigation.
 *
 * Hidden below md because the header repeats these links as a horizontal strip
 * on narrow screens; showing both would spend the viewport twice.
 *
 * @returns Sidebar element.
 */
export default function Sidebar() {
  const pathname = usePathname();
  const { projects, selectedProjectId, setSelectedProjectId, isLoading, refreshProjects } = useProject();
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Create a project from the rail and select it. */
  const createProject = async () => {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<{ id: string; name: string }>('/api/v1/projects', {
        name: trimmed,
        description: '',
      });
      await refreshProjects();
      setSelectedProjectId(created.id);
      setName('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not create project');
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-rail md:flex">
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-line-accent bg-accent-soft text-[12px] font-extrabold tracking-tight text-text">
          AA
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[13px] font-bold leading-tight text-text">Api-Agent</span>
          <span className="block text-[10px] font-semibold uppercase tracking-[0.09em] text-text-mute">
            QA Workbench
          </span>
        </span>
      </div>

      <div className="border-b border-line px-3 py-3">
        <label
          htmlFor="sidebar-project"
          className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.09em] text-text-mute"
        >
          Project
        </label>
        <select
          id="sidebar-project"
          value={selectedProjectId || ''}
          onChange={(event) => setSelectedProjectId(event.target.value || null)}
          disabled={isLoading || projects.length === 0}
          className={cx(
            'h-9 w-full cursor-pointer rounded-md border border-line-strong bg-panel-alt px-2 text-[12.5px] font-medium text-text',
            'hover:border-line-contrast focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {isLoading ? <option>Loading projects</option> : null}
          {!isLoading && projects.length === 0 ? <option>No projects yet</option> : null}
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name + ' / ' + project.id.slice(0, 8)}
            </option>
          ))}
        </select>

        <details className="mt-2">
          <summary className="flex cursor-pointer list-none items-center gap-1 text-[11px] font-semibold text-text-dim hover:text-text [&::-webkit-details-marker]:hidden">
            <Icon name="plus" size={12} />
            New project
          </summary>
          <div className="mt-2 flex flex-col gap-1.5">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void createProject();
              }}
              placeholder="Project name"
              aria-label="New project name"
            />
            <Button
              tone="primary"
              small
              icon="plus"
              onClick={() => void createProject()}
              disabled={busy || !name.trim()}
              className="w-full"
            >
              {busy ? 'Creating' : 'Create project'}
            </Button>
            {error ? <p className="text-[11px] text-bad">{error}</p> : null}
          </div>
        </details>
      </div>

      <nav className="aa-scroll flex-1 overflow-y-auto p-2">
        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? 'page' : undefined}
                  className={cx(
                    'flex items-start gap-2.5 rounded-md border px-2.5 py-2 transition-colors',
                    active
                      ? 'border-line-accent bg-accent-soft text-text'
                      : 'border-transparent text-text-dim hover:bg-hover hover:text-text',
                  )}
                >
                  <Icon name={item.icon} size={15} className="mt-0.5 shrink-0" />
                  <span className="min-w-0">
                    <span className="block truncate text-[12.5px] font-semibold">{item.label}</span>
                    <span className="block truncate text-[10.5px] text-text-mute">{item.hint}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-line px-3 py-3">
        <ThemeToggle />
        <p className="mt-2 text-[10px] text-text-mute">v0.2.0 / FastAPI + Next.js</p>
      </div>
    </aside>
  );
}
