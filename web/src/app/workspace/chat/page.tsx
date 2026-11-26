'use client';

import React, { useEffect, useRef, useState } from 'react';

import ChatComposer from '@/components/chat/ChatComposer';
import KnowledgeHubPanel from '@/components/hub/KnowledgeHubPanel';
import MessageBubble, { formatDay } from '@/components/chat/MessageBubble';
import ThreadRail from '@/components/chat/ThreadRail';
import PageShell, { PageHeader } from '@/components/layout/PageShell';
import { Badge, Button, Card, EmptyState, Modal, Notice, Spinner, cx } from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';
import { api, LLM_TIMEOUT_MS } from '@/lib/api';
import type { ChatThread } from '@/types/api';

/**
 * Render the project chat surface.
 *
 * The layout is three flex children in a fixed height column: a scrolling rail,
 * a scrolling transcript, and a composer that never scrolls. The composer is
 * visible at any message count without `sticky` and without the transcript
 * owning the page scroll.
 *
 * @returns Chat page element.
 */
export default function ChatPage() {
  const { project, isLoadingProject } = useProject();
  const projectId = project?.id || '';

  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [view, setView] = useState<'conversation' | 'briefs'>('conversation');
  const [pendingDelete, setPendingDelete] = useState<ChatThread | null>(null);
  const [deleting, setDeleting] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Load the rail whenever the project changes.
  useEffect(() => {
    if (!projectId) {
      setThreads([]);
      setThread(null);
      setActiveId(null);
      return undefined;
    }
    let live = true;
    setLoading(true);
    setError(null);
    api
      .get<ChatThread[]>('/api/v1/projects/' + projectId + '/chat/threads?include_archived=true')
      .then(
        (rows) => {
          if (!live) return;
          setThreads(rows);
          setActiveId((current) => (
            current && rows.some((row) => row.id === current)
              ? current
              : (rows.find((row) => !row.archived)?.id ?? rows[0]?.id ?? null)
          ));
        },
        (caught: unknown) => {
          if (live) {
            setError(caught instanceof Error ? caught.message : 'Could not load threads');
          }
        },
      )
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [projectId]);

  // Load the transcript of the selected thread.
  useEffect(() => {
    if (!projectId || !activeId) {
      setThread(null);
      return undefined;
    }
    let live = true;
    setOpening(true);
    api
      .get<ChatThread>('/api/v1/projects/' + projectId + '/chat/threads/' + activeId)
      .then(
        (data) => {
          if (live) setThread(data);
        },
        (caught: unknown) => {
          if (live) {
            setError(caught instanceof Error ? caught.message : 'Could not load the thread');
          }
        },
      )
      .finally(() => {
        if (live) setOpening(false);
      });
    return () => {
      live = false;
    };
  }, [projectId, activeId]);

  // Follow the newest message.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [thread?.messages?.length]);

  /**
   * Create a thread and select it.
   */
  async function createThread(): Promise<void> {
    setError(null);
    try {
      const created = await api.post<ChatThread>(
        '/api/v1/projects/' + projectId + '/chat/threads',
        { title: 'New project chat' },
      );
      setThreads((current) => [created, ...current]);
      setActiveId(created.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create the thread');
    }
  }

  /**
   * Rename a thread in the rail and in the open header.
   *
   * @param id - Thread to rename.
   * @param title - New title.
   */
  async function renameThread(id: string, title: string): Promise<void> {
    setError(null);
    try {
      await api.put('/api/v1/projects/' + projectId + '/chat/threads/' + id, { title });
      setThreads((current) => current.map((row) => (row.id === id ? { ...row, title } : row)));
      setThread((current) => (current && current.id === id ? { ...current, title } : current));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not rename the thread');
    }
  }

  /**
   * Archive or restore a thread.
   *
   * @param row - Thread whose archive state should flip.
   */
  async function archiveThread(row: ChatThread): Promise<void> {
    const archived = !row.archived;
    setError(null);
    try {
      await api.put('/api/v1/projects/' + projectId + '/chat/threads/' + row.id, { archived });
      setThreads((current) => current.map((entry) => (
        entry.id === row.id ? { ...entry, archived } : entry
      )));
      setThread((current) => (
        current && current.id === row.id ? { ...current, archived } : current
      ));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not change the archive state');
    }
  }

  /**
   * Send the draft and adopt the thread the server returns.
   */
  async function send(): Promise<void> {
    const body = draft.trim();
    if (!body || !activeId || sending || thread?.archived) return;
    setSending(true);
    setError(null);
    setDraft('');
    try {
      const result = await api.post<{ thread: ChatThread }>(
        '/api/v1/projects/' + projectId + '/chat/threads/' + activeId + '/messages',
        { content: body },
        { timeoutMs: LLM_TIMEOUT_MS },
      );
      setThread(result.thread);
      setThreads((current) => current.map((row) => (
        row.id === result.thread.id
          ? { ...row, title: result.thread.title, updated_at: result.thread.updated_at }
          : row
      )));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The assistant could not answer');
      setDraft(body);
    } finally {
      setSending(false);
    }
  }

  /**
   * Delete a thread after the confirmation dialog accepts it.
   */
  async function confirmDelete(): Promise<void> {
    if (!pendingDelete) return;
    setDeleting(true);
    setError(null);
    try {
      await api.delete(
        '/api/v1/projects/' + projectId + '/chat/threads/' + pendingDelete.id,
      );
      const remaining = threads.filter((row) => row.id !== pendingDelete.id);
      setThreads(remaining);
      if (activeId === pendingDelete.id) {
        setActiveId(remaining.find((row) => !row.archived)?.id ?? remaining[0]?.id ?? null);
        setThread(null);
      }
      setPendingDelete(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the thread');
    } finally {
      setDeleting(false);
    }
  }

  const messages = thread?.messages ?? [];

  if (!project && !isLoadingProject) {
    return (
      <PageShell>
        <PageHeader title="Project Chat" description="Conversation with project context." />
        <EmptyState title="No project selected" body="Pick a project in the rail to open its chats." />
      </PageShell>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-line px-3 py-1.5">
        <div className="flex overflow-hidden rounded border border-line">
          {(['conversation', 'briefs'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={view === option}
              onClick={() => setView(option)}
              className={cx(
                'px-2.5 py-1 text-[10.5px] font-semibold',
                view === option
                  ? 'bg-accent-soft text-accent'
                  : 'bg-panel text-text-dim hover:bg-hover',
              )}
            >
              {option === 'conversation' ? 'Conversation' : 'Project briefs'}
            </button>
          ))}
        </div>
        {view === 'conversation' && thread ? (
          <span className="truncate text-[10.5px] text-text-mute">{thread.title}</span>
        ) : null}
      </div>

      {view === 'briefs' ? (
        <div className="aa-scroll min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <KnowledgeHubPanel projectId={projectId} threads={threads} />
        </div>
      ) : (
    <div className="flex min-h-0 flex-1">
      <ThreadRail
        threads={threads}
        activeId={activeId}
        loading={loading}
        onSelect={setActiveId}
        onCreate={() => void createThread()}
        onRename={(id, title) => void renameThread(id, title)}
        onArchive={(row) => void archiveThread(row)}
        onDelete={(row) => setPendingDelete(row)}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="shrink-0 px-4 pt-4">
          <PageHeader
            title={thread?.title || 'New conversation'}
            description="Answers cite the endpoints, Hub pages, and reviewed facts they used."
            actions={
              <>
                <Badge tone="neutral">{String(messages.length) + ' messages'}</Badge>
                {thread?.archived ? <Badge tone="warn">archived</Badge> : null}
              </>
            }
          />
          {error ? <div className="pb-2"><Notice tone="bad">{error}</Notice></div> : null}
        </div>

        <div className="aa-scroll min-h-0 flex-1 overflow-y-auto px-4 py-2">
          {opening ? <Spinner label="Opening thread" /> : null}
          {!opening && messages.length === 0 ? (
            <Card tone="quiet" className="p-4">
              <p className="text-[12px] text-text-dim">
                No messages yet. Ask about a requirement, an endpoint, or a gap in the Hub.
              </p>
            </Card>
          ) : null}
          <div className="flex flex-col gap-2">
            {messages.map((message, index, rows) => {
              const stamp = typeof rows[index ?? 0].created_at === 'string'
                ? String(rows[index ?? 0].created_at)
                : '';
              const day = formatDay(stamp);
              const previous = index > 0
                ? formatDay(String(rows[index - 1].created_at || ''))
                : '';
              return (
                <React.Fragment key={String(message.id || index)}>
                  {day && day !== previous ? (
                    <div className="my-2 text-center text-[9.5px] font-semibold uppercase tracking-[0.07em] text-text-mute">
                      {day}
                    </div>
                  ) : null}
                  <MessageBubble message={message} />
                </React.Fragment>
              );
            })}
            <div ref={endRef} />
          </div>
        </div>

        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSend={() => void send()}
          busy={sending}
          archived={Boolean(thread?.archived)}
          disabled={!activeId}
          disabledReason={!activeId ? 'Create or select a thread first.' : undefined}
        />
      </div>

      <Modal
        open={Boolean(pendingDelete)}
        title="Delete thread"
        description="This removes the transcript permanently. Archiving keeps it instead."
        onClose={() => setPendingDelete(null)}
        footer={
          <>
            <Button small onClick={() => setPendingDelete(null)} disabled={deleting}>
              Cancel
            </Button>
            <Button small tone="danger" onClick={() => void confirmDelete()} disabled={deleting}>
              {deleting ? 'Deleting' : 'Delete thread'}
            </Button>
          </>
        }
      >
        <p className="text-[12px] text-text-dim">
          {pendingDelete ? pendingDelete.title : ''}
        </p>
      </Modal>
    </div>
      )}
    </div>
  );
}
