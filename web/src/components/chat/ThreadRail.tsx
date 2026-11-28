'use client';

import React, { useState } from 'react';

import { Badge, Button, Input, Menu, cx } from '@/components/ui/primitives';
import { relativeTime } from '@/lib/format';
import type { ChatThread } from '@/types/api';

/**
 * Render the conversation rail: search, scope filter, and one row per thread.
 *
 * @param props - Threads, current selection, and row actions.
 * @returns Thread rail element.
 */
export default function ThreadRail({
  threads,
  activeId,
  loading,
  onSelect,
  onCreate,
  onRename,
  onArchive,
  onDelete,
}: {
  threads: ChatThread[];
  activeId: string | null;
  loading?: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, title: string) => void;
  onArchive: (thread: ChatThread) => void;
  onDelete: (thread: ChatThread) => void;
}) {
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<'active' | 'all' | 'archived'>('active');
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');

  const visible = threads.filter((thread) => {
    if (scope === 'active' && thread.archived) return false;
    if (scope === 'archived' && !thread.archived) return false;
    if (!query.trim()) return true;
    return thread.title.toLowerCase().includes(query.trim().toLowerCase());
  });

  const counts = {
    active: threads.filter((item) => !item.archived).length,
    archived: threads.filter((item) => item.archived).length,
  };

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-line bg-rail">
      <div className="shrink-0 border-b border-line p-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[11px] font-bold uppercase tracking-[0.07em] text-text-dim">
            Threads
          </h2>
          <Button small icon="plus" onClick={onCreate}>
            New
          </Button>
        </div>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search threads"
          aria-label="Search threads"
          className="mt-1.5 h-7 text-[11px]"
        />
        <div className="mt-1.5 flex gap-1">
          {(['active', 'all', 'archived'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setScope(option)}
              className={cx(
                'rounded px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.05em]',
                scope === option
                  ? 'bg-accent-soft text-accent'
                  : 'text-text-mute hover:bg-hover hover:text-text-dim',
              )}
            >
              {option === 'active' ? 'Active ' + String(counts.active) : null}
              {option === 'all' ? 'All ' + String(threads.length) : null}
              {option === 'archived' ? 'Archived ' + String(counts.archived) : null}
            </button>
          ))}
        </div>
      </div>

      <div className="aa-scroll min-h-0 flex-1 overflow-y-auto p-1.5">
        {loading ? <p className="px-1 text-[10.5px] text-text-mute">Loading threads</p> : null}
        {!loading && visible.length === 0 ? (
          <p className="px-1 text-[10.5px] text-text-mute">No threads match.</p>
        ) : null}

        {visible.map((thread) => (
          <div
            key={thread.id}
            className={cx(
              'mb-1 rounded border px-1.5 py-1',
              thread.id === activeId
                ? 'border-line-accent bg-accent-soft'
                : 'border-line-soft bg-panel hover:border-line',
            )}
          >
            {editing === thread.id ? (
              <div className="flex items-center gap-1">
                <Input
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  className="h-6 text-[10.5px]"
                  aria-label="Thread title"
                />
                <Button
                  small
                  tone="primary"
                  onClick={() => {
                    if (draft.trim()) onRename(thread.id, draft.trim());
                    setEditing(null);
                  }}
                >
                  Save
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onSelect(thread.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-[11px] font-semibold text-text">
                    {thread.title}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1">
                    {thread.archived ? <Badge tone="warn">archived</Badge> : null}
                    <span className="truncate text-[9px] text-text-mute">
                      {relativeTime(thread.updated_at) || 'no activity yet'}
                    </span>
                  </span>
                </button>
                <Menu
                  label={'Actions for ' + thread.title}
                  items={[
                    {
                      label: 'Rename',
                      onSelect: () => {
                        setEditing(thread.id);
                        setDraft(thread.title);
                      },
                    },
                    {
                      label: thread.archived ? 'Restore' : 'Archive',
                      icon: 'edit',
                      onSelect: () => onArchive(thread),
                    },
                    {
                      label: 'Delete',
                      danger: true,
                      onSelect: () => onDelete(thread),
                    },
                  ]}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
