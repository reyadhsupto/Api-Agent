'use client';

import React from 'react';
import Link from 'next/link';

import PageShell, { PageHeader } from '@/components/layout/PageShell';
import Icon, { type IconName } from '@/components/ui/Icon';
import { Card, EmptyState, cx } from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';

interface Module {
  href: string;
  label: string;
  icon: IconName;
  body: string;
}

const MODULES: Module[] = [
  { href: '/workspace/api', label: 'API Workspace', icon: 'plug', body: 'Compose requests, keep collections, and inspect raw responses.' },
  { href: '/workspace/test-cases', label: 'Test Cases', icon: 'flask', body: 'Generate suites from saved requests, edit assertions, and run them.' },
  { href: '/workspace/chat', label: 'Project Chat', icon: 'chat', body: 'Discuss behavior with the project context, then turn it into knowledge.' },
  { href: '/workspace/activity', label: 'Activity', icon: 'pulse', body: 'Audit generation and knowledge-extraction runs with their full payloads.' },
];

/**
 * Render the workspace landing surface with project statistics.
 *
 * @returns Workspace page element.
 */
export default function WorkspacePage() {
  const { project, isLoadingProject } = useProject();

  const stats = [
    { label: 'Collections', value: project?.collections?.length ?? 0 },
    { label: 'Saved requests', value: project?.endpoints?.length ?? 0 },
    { label: 'Test cases', value: project?.test_cases?.length ?? 0 },
  ];

  return (
    <PageShell>
      <PageHeader
        title="Workspace"
        description="Compose API requests, generate test coverage, and review what the model produced."
      />

      {!project && !isLoadingProject ? (
        <EmptyState title="No project selected" body="Pick a project in the rail, or create one to begin." />
      ) : (
        <>
          <div className="mb-4 grid grid-cols-3 gap-2 sm:max-w-md">
            {stats.map((stat) => (
              <Card key={stat.label} tone="quiet" className="px-3 py-2 text-center">
                <span className="block text-[17px] font-bold leading-none text-text">{stat.value}</span>
                <span className="mt-1 block text-[9.5px] font-semibold uppercase tracking-[0.07em] text-text-mute">
                  {stat.label}
                </span>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {MODULES.map((module) => (
              <Link key={module.href} href={module.href} className="group">
                <Card className={cx('h-full p-4 transition-colors', 'hover:border-line-accent hover:bg-panel-alt')}>
                  <span className="flex items-center gap-2">
                    <Icon name={module.icon} size={15} className="text-accent" />
                    <span className="text-[13px] font-bold text-text">{module.label}</span>
                    <Icon name="chevronRight" size={13} className="ml-auto text-text-mute" />
                  </span>
                  <span className="mt-1.5 block text-[11.5px] leading-relaxed text-text-dim">{module.body}</span>
                </Card>
              </Link>
            ))}
          </div>
        </>
      )}
    </PageShell>
  );
}
