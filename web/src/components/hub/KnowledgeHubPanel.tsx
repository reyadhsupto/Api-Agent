'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';

import DiffView from '@/components/ui/DiffView';
import Markdown from '@/components/ui/Markdown';
import {
  Badge, Button, Checkbox, EmptyState, Field, Input, Modal, Notice, Select,
  Spinner, Tabs, Textarea, cx,
} from '@/components/ui/primitives';
import { formatTimestamp, relativeTime, shortId } from '@/lib/format';
import {
  compareVersions, createBrief, draftFromThread, linkFeatureServices, listBriefs, listBriefVersions,
  restoreBriefVersion, saveBriefVersion, saveHubDraft,
} from '@/lib/hub';
import type {
  BriefScope, BriefVersion, ChatThread, HubDraftPage, HubDraftResponse, SectionDiff,
} from '@/types/api';

/** One page kind label for the scope chip. */
const SCOPE_LABEL: Record<string, string> = {
  project: 'Project',
  feature: 'Feature',
  microservice: 'Service',
};

/**
 * Render one brief page card in the list.
 *
 * @param props - Page, selection state, and actions.
 * @returns Page row.
 */
/**
 * Render the project briefs and Knowledge Hub workspace.
 *
 * Both surfaces are the same backend entity, so this panel is the single place
 * pages are read, edited, versioned, restored, linked, and drafted from chat.
 *
 * @param props - Owning project and the project's chat threads.
 * @returns Hub panel element.
 */
export default function KnowledgeHubPanel({
  projectId,
  threads,
}: {
  projectId: string;
  threads: ChatThread[];
}) {
  const [pages, setPages] = useState<BriefScope[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [openScopeId, setOpenScopeId] = useState<string | null>(null);
  const [tab, setTab] = useState<'current' | 'history'>('current');
  const [versions, setVersions] = useState<BriefVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const [editText, setEditText] = useState<string | null>(null);
  const [previewEdit, setPreviewEdit] = useState(false);
  const [busy, setBusy] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createType, setCreateType] = useState<'feature' | 'microservice'>('feature');
  const [createName, setCreateName] = useState('');

  const [linkIds, setLinkIds] = useState<string[]>([]);

  const [draftOpen, setDraftOpen] = useState(false);
  const [draftThreadId, setDraftThreadId] = useState('');
  const [draftScopeIds, setDraftScopeIds] = useState<string[]>([]);
  const [draftResult, setDraftResult] = useState<HubDraftResponse | null>(null);
  const [draftInclude, setDraftInclude] = useState<Record<string, boolean>>({});
  const [draftBodies, setDraftBodies] = useState<Record<string, string>>({});

  const [compareFrom, setCompareFrom] = useState('');
  const [compareTo, setCompareTo] = useState('');
  const [compareDiffs, setCompareDiffs] = useState<SectionDiff[] | null>(null);

  const activePage = useMemo(
    () => pages.find((item) => item.id === openScopeId) || null,
    [pages, openScopeId],
  );

  const services = pages.filter((item) => item.scope_type === 'microservice');
  const overview = pages.find((item) => item.scope_type === 'project') || null;

  /**
   * Reload every page in the project.
   */
  const load = useCallback(async (): Promise<void> => {
    if (!projectId) {
      setPages([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setPages(await listBriefs(projectId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load project briefs');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Reload when the project changes.
  useEffect(() => {
    void load();
  }, [load]);

  /**
   * Reload versions for one page.
   *
   * @param scopeId - Page whose history is wanted.
   */
  const loadVersions = useCallback(async (scopeId: string): Promise<void> => {
    setVersionsLoading(true);
    setError(null);
    try {
      const rows = await listBriefVersions(projectId, scopeId);
      const sorted = [...rows].sort((left, right) => (
        Number(right.version_number) - Number(left.version_number)
      ));
      setVersions(sorted);
      setLinkIds(pages.find((item) => item.id === scopeId)?.microservice_scope_ids || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load page history');
    } finally {
      setVersionsLoading(false);
    }
  }, [pages, projectId]);

  /**
   * Open one page at its current version.
   *
   * @param scope - Page to open.
   */
  function openPage(scope: BriefScope): void {
    setOpenScopeId(scope.id);
    setTab('current');
    setEditText(null);
    setPreviewEdit(false);
    setCompareDiffs(null);
    setCompareFrom('');
    setCompareTo('');
    void loadVersions(scope.id);
  }

  /**
   * Save edited Markdown as a new immutable version.
   *
   * @param content - Reviewed page body.
   * @param sourceThreadId - Thread the content came from, when known.
   */
  async function saveContent(content: string, sourceThreadId?: string | null): Promise<void> {
    if (!activePage) return;
    setBusy(true);
    setError(null);
    try {
      await saveBriefVersion(projectId, activePage.id, content, sourceThreadId || null);
      setEditText(null);
      setPreviewEdit(false);
      await load();
      await loadVersions(activePage.id);
      setTab('current');
      setNotice('Saved version v' + String(Number(activePage.current_version_number || 0) + 1) + ' for ' + activePage.name + '.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the brief');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Create one feature or microservice page.
   */
  async function createPage(): Promise<void> {
    if (!createName.trim()) {
      setError('Enter a page name.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createBrief(projectId, createType, createName);
      setCreateName('');
      setCreateOpen(false);
      await load();
      setNotice('Created ' + createType + ' page ' + created.name + '.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create the page');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Persist the microservice links chosen for the open feature page.
   */
  async function saveLinks(): Promise<void> {
    if (!activePage) return;
    setBusy(true);
    setError(null);
    try {
      await linkFeatureServices(projectId, activePage.id, linkIds);
      await load();
      setNotice('Linked ' + String(linkIds.length) + ' microservice page(s) to ' + activePage.name + '.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the page links');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Restore one older version as the new current version.
   *
   * @param version - Version to restore.
   */
  async function restoreVersion(version: BriefVersion): Promise<void> {
    if (!activePage) return;
    setBusy(true);
    setError(null);
    try {
      await restoreBriefVersion(projectId, activePage.id, version.id);
      await load();
      await loadVersions(activePage.id);
      setNotice('Restored v' + String(version.version_number) + ' as the current version of ' + activePage.name + '.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not restore the version');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Compare two saved versions of the open page.
   */
  async function compareSelected(): Promise<void> {
    if (!activePage || !compareFrom || !compareTo) {
      setError('Choose both versions to compare.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await compareVersions(projectId, activePage.id, compareFrom, compareTo);
      setCompareDiffs(result.section_diffs || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not compare the versions');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Ask the model to propose updates to the selected pages from a thread.
   */
  async function prepareDraft(): Promise<void> {
    if (!draftThreadId || draftScopeIds.length === 0) {
      setError('Choose a chat thread and at least one page to update.');
      return;
    }
    setBusy(true);
    setError(null);
    setDraftResult(null);
    try {
      const result = await draftFromThread(projectId, draftThreadId, draftScopeIds);
      const include: Record<string, boolean> = {};
      const bodies: Record<string, string> = {};
      const drafts: HubDraftPage[] = Array.isArray(result?.pages) ? result.pages : [];
      drafts.forEach((item) => {
        include[item.scope_id] = true;
        bodies[item.scope_id] = String(item.draft || '');
      });
      setDraftInclude(include);
      setDraftBodies(bodies);
      setDraftResult({ ...result, pages: drafts });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not prepare an update from the thread');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Save the reviewed drafts as immutable versions.
   */
  async function saveDrafts(): Promise<void> {
    if (!draftResult) return;
    const pagesToSave = (draftResult.pages || [])
      .filter((item) => draftInclude[item.scope_id])
      .map((item) => ({ scope_id: item.scope_id, content: String(draftBodies[item.scope_id] ?? item.draft ?? '') }))
      .filter((item) => item.content.trim());
    if (pagesToSave.length === 0) {
      setError('Include at least one page with content to save.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await saveHubDraft(projectId, draftResult.source_thread_id, draftResult.draft_event_id || null, pagesToSave);
      setDraftResult(null);
      setDraftOpen(false);
      setDraftScopeIds([]);
      await load();
      if (activePage) await loadVersions(activePage.id);
      setNotice('Saved ' + String(pagesToSave.length) + ' page version(s) from the conversation.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the page updates');
    } finally {
      setBusy(false);
    }
  }

  if (!projectId) {
    return (
      <EmptyState title="No project selected" body="Pick a project in the rail to open its briefs." />
    );
  }

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0">
          <h2 className="text-[14px] font-bold tracking-[-0.01em] text-text">Project briefs</h2>
          <p className="text-[11px] text-text-mute">
            {String(pages.length) + ' page(s). These are the source of truth for generated tests.'}
          </p>
        </div>
        <span className="ml-auto flex flex-wrap items-center gap-1.5">
          <Button small icon="refresh" disabled={loading} onClick={() => void load()}>
            Refresh
          </Button>
          <Button small tone="primary" icon="plus" onClick={() => setCreateOpen(true)}>
            New page
          </Button>
          <Button
            small
            icon="sparkles"
            disabled={loading || pages.length === 0 || threads.length === 0}
            onClick={() => {
              setDraftScopeIds(overview ? [overview.id] : []);
              setDraftOpen(true);
            }}
          >
            Draft from chat
          </Button>
        </span>
      </div>

      {error ? <Notice tone="bad">{error}</Notice> : null}
      {notice ? <Notice tone="ok">{notice}</Notice> : null}

      {loading && pages.length === 0 ? (
        <div className="flex flex-col gap-2">
          <div className="aa-skel h-7" />
          <div className="aa-skel h-7" />
          <div className="aa-skel h-7" />
        </div>
      ) : null}

      {!loading && pages.length === 0 ? (
        <EmptyState
          title="No briefs yet"
          body="Create a feature or microservice page, or draft one from a saved chat thread."
          action={(
            <Button small tone="primary" icon="plus" onClick={() => setCreateOpen(true)}>
              Create first page
            </Button>
          )}
        />
      ) : null}

      {pages.length > 0 ? (
        <div className="aa-scroll max-h-[30rem] overflow-auto rounded-md border border-line bg-panel">
          <table className="w-full min-w-[40rem] border-collapse text-left">
            <thead className="bg-panel-alt border-b border-line">
              <tr className="sticky top-0 z-10 bg-panel-alt text-[10.5px] font-bold uppercase tracking-wider text-text-mute">
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2 text-center">Versions</th>
                <th className="px-3 py-2">Latest</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {pages.map((item) => (
                <tr
                  key={item.id}
                  className={cx(
                    'text-[12px] transition-colors hover:bg-hover',
                    item.id === openScopeId ? 'bg-accent-wash' : 'bg-transparent'
                  )}
                >
                  <td className="max-w-[18rem] px-3 py-2">
                    <button type="button" className="block max-w-full truncate text-left font-semibold text-text hover:text-accent" title={item.name} onClick={() => openPage(item)}>{item.name}</button>
                    {item.scope_type === 'project' ? <span className="block text-[9.5px] text-text-mute">Always included in generation</span> : null}
                  </td>
                  <td className="px-3 py-2">
                    <Badge tone={item.scope_type === 'project' ? 'accent' : item.scope_type === 'feature' ? 'info' : 'neutral'} dot={false}>
                      {SCOPE_LABEL[String(item.scope_type)] || item.scope_type}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-center font-mono text-[11px] text-text-dim">
                    {String(item.version_count || 0)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-[10.5px] text-text-dim">
                    {'v' + String(item.current_version_number || 1)}
                    {item.current_version_created_at ? ' · ' + formatTimestamp(item.current_version_created_at) : ''}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className="inline-flex gap-1">
                      <Button small tone="ghost" onClick={() => openPage(item)}>Open</Button>
                      <Button small tone="ghost" icon="sparkles" onClick={() => { setDraftScopeIds([item.id]); setDraftOpen(true); }}>Draft</Button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Modal
        open={createOpen}
        title="New brief page"
        description="Create a feature or microservice page in the Knowledge Hub."
        onClose={() => setCreateOpen(false)}
        footer={(
          <>
            <Button small onClick={() => setCreateOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              small
              tone="primary"
              icon="plus"
              onClick={() => void createPage()}
              disabled={busy || !createName.trim()}
            >
              {busy ? 'Creating' : 'Create page'}
            </Button>
          </>
        )}
      >
        <div className="flex flex-col gap-2.5">
          <Field label="Page kind">
            <div className="flex gap-1">
              {(['feature', 'microservice'] as const).map((kind) => (
                <Button
                  key={kind}
                  small
                  tone={createType === kind ? 'secondary' : 'ghost'}
                  aria-pressed={createType === kind}
                  onClick={() => setCreateType(kind)}
                >
                  {SCOPE_LABEL[kind]}
                </Button>
              ))}
            </div>
          </Field>
          <Field label="Page name">
            <Input
              value={createName}
              aria-label="Page name"
              placeholder={createType === 'feature' ? 'Checkout' : 'payments-service'}
              onChange={(event) => setCreateName(event.target.value)}
            />
          </Field>
        </div>
      </Modal>

      <Modal
        open={draftOpen}
        title="Draft brief update from chat"
        description="The model proposes page content. Nothing is saved until you review it and choose Save versions."
        wide
        onClose={() => {
          if (busy) return;
          setDraftOpen(false);
          setDraftResult(null);
        }}
        footer={(
          <>
            <Button
              small
              disabled={busy}
              onClick={() => {
                setDraftOpen(false);
                setDraftResult(null);
              }}
            >
              Cancel
            </Button>
            <Button
              small
              icon="sparkles"
              onClick={() => void prepareDraft()}
              disabled={busy || !draftThreadId || draftScopeIds.length === 0}
            >
              {busy && !draftResult ? 'Preparing' : 'Prepare draft'}
            </Button>
            {draftResult ? (
              <Button
                small
                tone="primary"
                icon="save"
                onClick={() => void saveDrafts()}
                disabled={busy}
              >
                {busy ? 'Saving' : 'Save versions'}
              </Button>
            ) : null}
          </>
        )}
      >
        <div className="flex flex-col gap-2.5">
          <Field label="Chat thread">
            <Select
              value={draftThreadId}
              aria-label="Chat thread"
              className="h-8"
              onChange={(event) => setDraftThreadId(event.target.value)}
            >
              <option value="">Choose a thread</option>
              {threads.filter((item) => !item.archived).map((item) => (
                <option key={item.id} value={item.id}>{item.title}</option>
              ))}
            </Select>
          </Field>

          <div>
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-text-mute">
              Pages to update
            </p>
            <div className="aa-scroll mt-1 max-h-[13rem] overflow-y-auto rounded-md border border-line bg-panel-alt p-1.5">
              {pages.length === 0 ? (
                <p className="px-1 py-1 text-[11px] text-text-mute">No pages yet.</p>
              ) : null}
              {pages.map((page) => (
                <label
                  key={page.id}
                  className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-1 hover:bg-hover"
                >
                  <Checkbox
                    checked={draftScopeIds.includes(page.id)}
                    aria-label={'Update ' + page.name}
                    onChange={() => setDraftScopeIds((previous) => (
                      previous.includes(page.id)
                        ? previous.filter((id) => id !== page.id)
                        : [...previous, page.id]
                    ))}
                  />
                  <span className="min-w-0 flex-1 truncate text-[11.5px] text-text">{page.name}</span>
                  <Badge tone="neutral" dot={false}>
                    {SCOPE_LABEL[String(page.scope_type)] || String(page.scope_type)}
                  </Badge>
                  <span className="font-mono text-[9px] text-text-mute">
                    {'v' + String(page.current_version_number || 1)}
                  </span>
                </label>
              ))}
            </div>
            <p className="mt-1 text-[10px] text-text-mute">
              {String(draftScopeIds.length) + ' page(s) selected'}
            </p>
          </div>

          {draftResult ? (
            <div className="flex flex-col gap-2">
              {(draftResult.pages || []).length === 0 ? (
                <Notice tone="warn">The model returned no page drafts.</Notice>
              ) : null}
              {(draftResult.pages || []).map((page) => (
                <section key={page.scope_id} className="rounded-md border border-line bg-panel-alt">
                  <div className="flex flex-wrap items-center gap-1.5 border-b border-line-soft px-2.5 py-1.5">
                    <Checkbox
                      checked={Boolean(draftInclude[page.scope_id])}
                      aria-label={'Include ' + (page.scope_name || page.scope_id)}
                      onChange={(event) => setDraftInclude((previous) => ({
                        ...previous,
                        [page.scope_id]: event.target.checked,
                      }))}
                    />
                    <span className="text-[12px] font-semibold text-text">
                      {page.scope_name || page.scope_id}
                    </span>
                    <Badge tone="neutral" dot={false}>{String(page.scope_type || '')}</Badge>
                    <span className="ml-auto text-[9.5px] text-text-mute">
                      {String((page.section_diffs || []).length) + ' section(s) changed'}
                    </span>
                  </div>
                  <div className="p-2">
                    <DiffView sections={page.section_diffs || []} />
                  </div>
                  {draftInclude[page.scope_id] ? (
                    <details className="border-t border-line-soft px-2.5 py-1.5">
                      <summary className="cursor-pointer text-[10.5px] font-semibold text-text-dim">
                        Review proposed body
                      </summary>
                      <Textarea
                        rows={8}
                        aria-label={'Draft for ' + (page.scope_name || page.scope_id)}
                        className="mt-1.5 font-mono text-[11px]"
                        value={draftBodies[page.scope_id] ?? page.draft}
                        onChange={(event) => setDraftBodies((previous) => ({
                          ...previous,
                          [page.scope_id]: event.target.value,
                        }))}
                      />
                      <div className="mt-1.5 rounded border border-line-soft bg-panel p-2">
                        <Markdown content={draftBodies[page.scope_id] ?? page.draft} />
                      </div>
                    </details>
                  ) : null}
                </section>
              ))}
            </div>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={Boolean(activePage)}
        title={activePage ? activePage.name : 'Brief'}
        description={activePage
          ? (SCOPE_LABEL[String(activePage.scope_type)] || 'Brief') + ' page'
          : undefined}
        wide
        onClose={() => {
          if (busy) return;
          setOpenScopeId(null);
          setEditText(null);
        }}
        footer={editText === null ? (
          <Button small onClick={() => setOpenScopeId(null)}>Close</Button>
        ) : (
          <>
            <Button small disabled={busy} onClick={() => { setEditText(null); setPreviewEdit(false); }}>
              Cancel
            </Button>
            <Button
              small
              tone="primary"
              icon="save"
              disabled={busy || !editText.trim()}
              onClick={() => void saveContent(editText)}
            >
              {busy ? 'Saving' : 'Save as v' + String(Number(activePage?.current_version_number || 0) + 1)}
            </Button>
          </>
        )}
      >
        {activePage ? (
          <div className="flex flex-col gap-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone="accent" dot={false}>
                {'v' + String(activePage.current_version_number || 1)}
              </Badge>
              <Badge tone="neutral" dot={false}>
                {String(activePage.version_count || versions.length) + ' version(s)'}
              </Badge>
              {activePage.updated_at ? (
                <span className="text-[9.5px] text-text-mute">
                  {'updated ' + relativeTime(activePage.updated_at)}
                </span>
              ) : null}
              {activePage.scope_type === 'project' ? (
                <Badge tone="info" dot={false}>always included</Badge>
              ) : null}
            </div>

            <Tabs
              value={tab}
              onChange={(next) => setTab(next === 'history' ? 'history' : 'current')}
              tabs={[
                { id: 'current', label: 'Content' },
                { id: 'history', label: 'History', badge: versions.length },
              ]}
            />

            {tab === 'current' ? (
              <div className="flex flex-col gap-2">
                {editText === null ? (
                  <>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Button
                        small
                        icon="edit"
                        onClick={() => setEditText(String(activePage.current_content || ''))}
                      >
                        Edit content
                      </Button>
                      <Button small icon="clock" onClick={() => setTab('history')}>
                        View history
                      </Button>
                      <Button
                        small
                        icon="sparkles"
                        disabled={threads.length === 0}
                        onClick={() => {
                          setDraftScopeIds([activePage.id]);
                          setDraftOpen(true);
                        }}
                      >
                        Draft from chat
                      </Button>
                    </div>

                    {activePage.current_content ? (
                      <div className="rounded-md border border-line bg-panel-alt p-2.5">
                        <Markdown content={String(activePage.current_content)} />
                      </div>
                    ) : (
                      <Notice tone="warn">
                        This page is empty. Add reviewed facts before generated tests rely on it.
                      </Notice>
                    )}

                    {activePage.scope_type === 'feature' && services.length > 0 ? (
                      <div className="rounded-md border border-line bg-panel-alt p-2.5">
                        <p className="text-[10.5px] font-bold uppercase tracking-[0.07em] text-text-mute">
                          Microservices used by this feature
                        </p>
                        <div className="mt-1.5 flex flex-col gap-1">
                          {services.map((service) => (
                            <label
                              key={service.id}
                              className="flex cursor-pointer items-center gap-1.5 text-[11.5px] text-text-dim"
                            >
                              <Checkbox
                                checked={linkIds.includes(service.id)}
                                aria-label={'Link ' + service.name}
                                onChange={() => setLinkIds((previous) => (
                                  previous.includes(service.id)
                                    ? previous.filter((id) => id !== service.id)
                                    : [...previous, service.id]
                                ))}
                              />
                              <span className="truncate">{service.name}</span>
                            </label>
                          ))}
                        </div>
                        <Button
                          small
                          className="mt-2"
                          icon="save"
                          disabled={busy}
                          onClick={() => void saveLinks()}
                        >
                          Save links
                        </Button>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Button
                        small
                        tone={previewEdit ? 'ghost' : 'secondary'}
                        aria-pressed={!previewEdit}
                        onClick={() => setPreviewEdit(false)}
                      >
                        Write
                      </Button>
                      <Button
                        small
                        tone={previewEdit ? 'secondary' : 'ghost'}
                        aria-pressed={previewEdit}
                        onClick={() => setPreviewEdit(true)}
                      >
                        Preview
                      </Button>
                      <span className="ml-auto font-mono text-[9.5px] text-text-mute">
                        {String(editText.length) + ' chars'}
                      </span>
                    </div>
                    {previewEdit ? (
                      <div className="aa-scroll max-h-[46vh] overflow-y-auto rounded-md border border-line bg-panel-alt p-2.5">
                        <Markdown content={editText} />
                      </div>
                    ) : (
                      <Textarea
                        rows={16}
                        value={editText}
                        aria-label="Brief content"
                        className="font-mono text-[11.5px]"
                        onChange={(event) => setEditText(event.target.value)}
                      />
                    )}
                    <p className="text-[10px] text-text-mute">
                      Saving appends an immutable version. Older versions stay restorable from History.
                    </p>
                  </div>
                )}
              </div>
            ) : null}

            {tab === 'history' ? (
              <div className="flex flex-col gap-2">
                {versionsLoading ? <Spinner label="Loading versions" /> : null}

                <div className="flex flex-wrap items-end gap-1.5 rounded-md border border-line bg-panel-alt p-2">
                  <Select
                    value={compareFrom}
                    aria-label="Compare from version"
                    className="h-8 min-w-[7rem]"
                    onChange={(event) => setCompareFrom(event.target.value)}
                  >
                    <option value="">From</option>
                    {versions.map((item) => (
                      <option key={item.id} value={item.id}>{'v' + String(item.version_number)}</option>
                    ))}
                  </Select>
                  <Select
                    value={compareTo}
                    aria-label="Compare to version"
                    className="h-8 min-w-[7rem]"
                    onChange={(event) => setCompareTo(event.target.value)}
                  >
                    <option value="">To</option>
                    {versions.map((item) => (
                      <option key={item.id} value={item.id}>{'v' + String(item.version_number)}</option>
                    ))}
                  </Select>
                  <Button
                    small
                    icon="layers"
                    disabled={busy || !compareFrom || !compareTo}
                    onClick={() => void compareSelected()}
                  >
                    Compare
                  </Button>
                  <Button
                    small
                    disabled={busy || versions.length < 2}
                    onClick={() => {
                      setCompareFrom(versions[1]?.id || '');
                      setCompareTo(versions[0]?.id || '');
                    }}
                  >
                    Latest vs previous
                  </Button>
                </div>

                {compareDiffs ? (
                  <div className="rounded-md border border-line bg-panel p-2">
                    <div className="mb-1 flex items-center justify-between gap-1.5">
                      <p className="text-[10.5px] font-bold uppercase tracking-[0.07em] text-text-mute">
                        Comparison
                      </p>
                      <Button small onClick={() => setCompareDiffs(null)}>Clear</Button>
                    </div>
                    <DiffView sections={compareDiffs} />
                  </div>
                ) : null}

                {versions.length === 0 && !versionsLoading ? (
                  <p className="text-[11px] text-text-mute">No saved versions yet.</p>
                ) : null}

                {versions.map((version) => (
                  <section key={version.id} className="rounded-md border border-line bg-panel-alt">
                    <div className="flex flex-wrap items-center gap-1.5 px-2.5 py-1.5">
                      <Badge tone="accent" dot={false}>{'v' + String(version.version_number)}</Badge>
                      {version.is_current ? <Badge tone="ok" dot={false}>current</Badge> : null}
                      <span className="font-mono text-[9.5px] text-text-mute">
                        {formatTimestamp(version.created_at)}
                      </span>
                      {version.source_thread_id ? (
                        <span className="truncate text-[9.5px] text-text-mute">
                          {'from thread ' + shortId(version.source_thread_id)}
                        </span>
                      ) : null}
                      <span className="ml-auto">
                        <Button
                          small
                          disabled={busy || version.is_current}
                          onClick={() => void restoreVersion(version)}
                        >
                          Restore
                        </Button>
                      </span>
                    </div>
                    <details className="border-t border-line-soft px-2.5 py-1.5">
                      <summary className="cursor-pointer text-[10.5px] font-semibold text-text-dim">
                        Preview
                      </summary>
                      <div className="aa-scroll mt-1.5 max-h-[30vh] overflow-y-auto rounded border border-line-soft bg-panel p-2">
                        <Markdown content={String(version.content || '')} />
                      </div>
                    </details>
                  </section>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

