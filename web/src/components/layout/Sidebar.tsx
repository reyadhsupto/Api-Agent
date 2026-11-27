'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useRouter } from 'next/navigation';

import Icon, { type IconName } from '@/components/ui/Icon';
import { Badge, Button, Input, Modal, cx } from '@/components/ui/primitives';
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
  { label: 'Home', href: '/workspace', icon: 'home', hint: 'Workspace overview' },
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
  const router = useRouter();
  const { projects, selectedProjectId, setSelectedProjectId, isLoading, refreshProjects } = useProject();
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');

  useEffect(() => {
    setCollapsed(window.localStorage.getItem('aa-sidebar-collapsed') === 'true');
  }, []);

  /** Persist the rail mode so navigation stays predictable after reload. */
  const toggleCollapsed = () => {
    setCollapsed((value) => {
      window.localStorage.setItem('aa-sidebar-collapsed', String(!value));
      return !value;
    });
  };

  /** Sign out through the same-origin auth handler. */
  const signOut = async () => {
    await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
    router.replace('/login');
  };

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

  const visibleProjects = projects.filter((project) => {
    const query = projectSearch.trim().toLowerCase();
    return !query || `${project.name} ${project.id}`.toLowerCase().includes(query);
  });

  return (
    <aside className={cx(
      'hidden shrink-0 flex-col border-r border-line bg-rail md:flex',
      collapsed ? 'w-16' : 'w-64',
    )}>
      <div className={cx('flex items-center gap-2.5 border-b border-line py-3.5', collapsed ? 'justify-center px-2' : 'px-4')}>
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-line-accent bg-accent-soft text-[12px] font-extrabold tracking-tight text-text">
          AA
        </span>
        {!collapsed && (
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-bold leading-tight text-text">Api-Agent</span>
            <span className="block text-[10px] font-semibold uppercase tracking-[0.09em] text-text-mute">
              QA Workbench
            </span>
          </span>
        )}
        {!collapsed ? (
          <Button small icon="chevronRight" onClick={toggleCollapsed} aria-label="Collapse sidebar" className="ml-auto rotate-180" />
        ) : null}
      </div>

      <div className={cx('border-b border-line py-3', collapsed ? 'px-2' : 'px-3')}>
        {collapsed ? (
          <div className="flex justify-center">
            <button
              type="button"
              title="Change project"
              aria-label="Change project"
              onClick={() => { setProjectSearch(''); setProjectPickerOpen(true); }}
              className="flex h-9 w-9 items-center justify-center rounded-md border border-transparent text-text-dim hover:border-line hover:bg-hover hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              <Icon name="database" size={16} />
            </button>
          </div>
        ) : null}
        {!collapsed ? <>
        <label
          htmlFor="sidebar-project"
          className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.09em] text-text-mute"
        >
          Project
        </label>
        <select
          id="sidebar-project"
          value={selectedProjectId || ''}
          title="Choose which project's requests, cases, chat, and Knowledge Hub are open."
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

        {!collapsed && (
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
        )}
        </> : null}
      </div>

      <nav className="aa-scroll flex-1 overflow-y-auto p-2">
        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = pathname === item.href || (
              item.href !== '/workspace' && pathname.startsWith(item.href + '/')
            );
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? 'page' : undefined}
                  title={collapsed ? `${item.label} · ${item.hint}` : undefined}
                  aria-label={collapsed ? item.label : undefined}
                  className={cx(
                    'flex items-center gap-2 rounded-md border px-2 py-2 transition-colors',
                    collapsed && 'justify-center px-1',
                    'overflow-hidden',
                    active
                      ? 'border-line-accent bg-accent-soft text-text'
                      : 'border-transparent text-text-dim hover:bg-hover hover:text-text',
                  )}
                >
                  <div className="shrink-0"><Icon name={item.icon} size={15} /></div>
                  {!collapsed && (
                    <span className="min-w-0 overflow-hidden">
                      <span className="block truncate text-[12.5px] font-semibold">{item.label}</span>
                      <span className="block truncate text-[10.5px] text-text-mute">{item.hint}</span>
                    </span>
                  )}
                  {collapsed ? <span className="sr-only">{item.label}: {item.hint}</span> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className={cx('border-t border-line py-3', collapsed ? 'px-2' : 'px-3')}>
        {collapsed ? (
          <Button small icon="chevronRight" onClick={toggleCollapsed} aria-label="Expand sidebar" className="mb-2 w-full" />
        ) : null}
        <ThemeToggle compact={collapsed} />
        <Button
          small
          icon="close"
          title="Sign out"
          aria-label="Sign out"
          onClick={() => void signOut()}
          className={collapsed ? 'w-full' : 'mt-2 w-full'}
        >
          {!collapsed ? 'Sign out' : null}
        </Button>
        {!collapsed && (
          <p className="mt-2 text-[10px] text-text-mute">v0.2.0 / FastAPI + Next.js</p>
        )}
      </div>
      <Modal
        open={collapsed && projectPickerOpen}
        title="Change project"
        description="Choose the project to open across the workspace."
        onClose={() => setProjectPickerOpen(false)}
      >
        <div className="flex flex-col gap-2">
          <Input
            value={projectSearch}
            onChange={(event) => setProjectSearch(event.target.value)}
            placeholder="Search projects"
            aria-label="Search projects"
            autoFocus
          />
          <div className="aa-scroll max-h-[50vh] overflow-y-auto rounded-md border border-line-soft">
            {visibleProjects.map((project) => {
              const selected = project.id === selectedProjectId;
              return (
                <button
                  key={project.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => {
                    setSelectedProjectId(project.id);
                    setProjectPickerOpen(false);
                  }}
                  className={cx(
                    'flex w-full items-center gap-3 border-b border-line-soft px-3 py-2.5 text-left last:border-b-0',
                    selected ? 'bg-accent-soft text-text' : 'text-text-dim hover:bg-hover hover:text-text',
                  )}
                >
                  <Icon name={selected ? 'check' : 'database'} size={14} className={selected ? 'text-accent' : 'text-text-mute'} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12px] font-semibold">{project.name}</span>
                    <span className="block truncate font-mono text-[9px] text-text-mute">{project.id}</span>
                  </span>
                  {selected ? <Badge tone="accent" dot={false}>Current</Badge> : null}
                </button>
              );
            })}
            {visibleProjects.length === 0 ? (
              <p className="px-3 py-4 text-center text-[11px] text-text-mute">
                {projects.length ? 'No projects match your search.' : 'No projects available.'}
              </p>
            ) : null}
          </div>
        </div>
      </Modal>
    </aside>
  );
}
