'use client';

import React, { useEffect, useMemo, useState } from 'react';

import {
  Badge, Button, Checkbox, Field, Input, Modal, Notice, Select, Textarea,
} from '@/components/ui/primitives';
import { formatTimestamp, truncate } from '@/lib/format';
import { createRevision, listActivities } from '@/lib/revisions';
import type {
  BriefScope, ChatThread, GenerationActivity, SavedRequest, TestCase,
} from '@/types/api';

/** One baseline group in the dialog. */
interface CaseGroup {
  label: string;
  cases: TestCase[];
}

/**
 * Group cases by the collection they were generated for.
 *
 * @param cases - Candidate baseline cases.
 * @returns Groups in first-seen order.
 */
function groupCases(cases: TestCase[]): CaseGroup[] {
  const groups = new Map<string, TestCase[]>();
  cases.forEach((item) => {
    const label = String(item.case_collection_name || item.case_kind || 'Endpoint cases');
    const rows = groups.get(label) || [];
    rows.push(item);
    groups.set(label, rows);
  });
  return Array.from(groups.entries()).map(([label, rows]) => ({ label, cases: rows }));
}

/**
 * Render the release revision dialog.
 *
 * @param props - Project data, source choices, and the created hook.
 * @returns Revision dialog element.
 */
export default function RevisionDialog({
  open,
  onClose,
  projectId,
  testCases,
  endpoints,
  collections,
  briefs,
  threads,
  unsavedCount,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  testCases: TestCase[];
  endpoints: SavedRequest[];
  collections: Array<{ id: string; name: string }>;
  briefs: BriefScope[];
  threads: ChatThread[];
  unsavedCount: number;
  onCreated: (cases: TestCase[]) => Promise<void> | void;
}) {
  const [activities, setActivities] = useState<GenerationActivity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [sourceId, setSourceId] = useState('');
  const [baselineIds, setBaselineIds] = useState<string[]>([]);
  const [keepIds, setKeepIds] = useState<string[]>([]);
  const [endpointIds, setEndpointIds] = useState<string[]>([]);
  const [label, setLabel] = useState('');
  const [notes, setNotes] = useState('');
  const [threadId, setThreadId] = useState('');
  const [briefIds, setBriefIds] = useState<string[]>([]);
  const [coverage, setCoverage] = useState<'changed' | 'full'>('changed');

  // Load candidate source actions whenever the dialog opens.
  useEffect(() => {
    if (!open || !projectId) return undefined;
    let live = true;
    setLoading(true);
    setError(null);
    listActivities(projectId).then(
      (result) => {
        if (live) setActivities(result.activities);
      },
      (caught: unknown) => {
        if (live) setError(caught instanceof Error ? caught.message : 'Could not load history');
      },
    ).finally(() => {
      if (live) setLoading(false);
    });
    return () => {
      live = false;
    };
  }, [open, projectId]);

  const sources = useMemo(
    () => activities.filter((item) => (
      item.status === 'succeeded'
      && Boolean(item.business_requirements)
      && !item.superseded_by_activity_id
    )),
    [activities],
  );

  const source = sources.find((item) => item.id === sourceId) || null;
  const generated = Array.isArray(source?.generated_case_ids)
    ? (source?.generated_case_ids as string[]).map(String)
    : [];
  const allowed = new Set(generated);
  const liveCases = testCases.filter((item) => !item.superseded_by_activity_id);
  const candidates = allowed.size === 0
    ? liveCases
    : liveCases.filter((item) => allowed.has(String(item.id)));
  const groups = groupCases(candidates);

  // Order the scope list by collection, so related requests stay adjacent.
  const scopeEndpoints = useMemo(() => {
    const positions = new Map(collections.map((item, index) => [item.id, index]));
    return [...endpoints].sort((left, right) => (
      (positions.get(String(left.collection_id)) ?? 1e6)
      - (positions.get(String(right.collection_id)) ?? 1e6)
    ));
  }, [collections, endpoints]);

  /**
   * Add or remove one identifier from a list.
   *
   * @param list - Current identifiers.
   * @param id - Identifier to toggle.
   * @returns New identifier list.
   */
  function toggle(list: string[], id: string): string[] {
    return list.includes(id) ? list.filter((entry) => entry !== id) : [...list, id];
  }

  /**
   * Select or clear every case in one baseline group.
   *
   * @param cases - Cases in the group.
   * @param select - True to select, false to clear.
   */
  function toggleGroup(cases: TestCase[], select: boolean): void {
    const ids = cases.map((item) => item.id);
    setBaselineIds((previous) => (
      select
        ? Array.from(new Set([...previous, ...ids]))
        : previous.filter((id) => !ids.includes(id))
    ));
    if (!select) setKeepIds((previous) => previous.filter((id) => !ids.includes(id)));
  }

  const reasons: string[] = [];
  if (unsavedCount > 0) {
    reasons.push(String(unsavedCount) + ' generated case(s) are not saved yet. Save them first.');
  }
  if (!sourceId) reasons.push('Choose one successful generation action as the source.');
  else if (!source) reasons.push('The chosen source action is not available.');
  if (sourceId && baselineIds.length === 0) reasons.push('Select at least one baseline case.');
  if (!label.trim()) reasons.push('Add a release label.');

  /**
   * Submit the revision request.
   */
  async function submit(): Promise<void> {
    if (reasons.length > 0) {
      setError(reasons[0]);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createRevision(projectId, {
        sourceActivityId: sourceId,
        baselineCaseIds: baselineIds.filter((id) => candidates.some((item) => item.id === id)),
        releaseLabel: label,
        releaseNotes: notes,
        endpointIds: endpointIds,
        keepUnchangedCaseIds: keepIds.filter((id) => baselineIds.includes(id)),
        projectChatThreadId: threadId || null,
        briefScopeIds: briefIds,
        coverage,
      });
      await onCreated(created);
      setSourceId('');
      setBaselineIds([]);
      setKeepIds([]);
      setEndpointIds([]);
      setLabel('');
      setNotes('');
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create the revision');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Create release revision"
      description="Re-author the suite from a prior generation action, carrying chosen cases forward."
      wide
      onClose={() => {
        if (!busy) onClose();
      }}
      footer={(
        <>
          <Button small disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button
            small
            tone="primary"
            icon="sparkles"
            disabled={busy || reasons.length > 0}
            onClick={() => void submit()}
          >
            {busy ? 'Generating' : 'Generate revision'}
          </Button>
        </>
      )}
    >
      <div className="flex flex-col gap-3">
        {error ? <Notice tone="bad">{error}</Notice> : null}
        {reasons.length > 0 ? (
          <Notice tone="warn">
            <span className="block font-semibold">Cannot generate yet</span>
            <ul className="mt-1 list-disc pl-4">
              {reasons.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </Notice>
        ) : null}

        <section className="flex flex-col gap-1.5">
          <h4 className="text-[11px] font-bold uppercase tracking-[0.07em] text-text-dim">
            1 - Source action
          </h4>
          <Select
            value={sourceId}
            aria-label="Source generation action"
            className="h-8"
            onChange={(event) => {
              const next = event.target.value;
              setSourceId(next);
              setKeepIds([]);
              const chosen = sources.find((item) => item.id === next);
              const ids = Array.isArray(chosen?.generated_case_ids)
                ? (chosen?.generated_case_ids as string[]).map(String)
                : [];
              setBaselineIds(ids.length > 0 ? ids : liveCases.map((item) => item.id));
            }}
          >
            <option value="">{loading ? 'Loading history' : 'Choose a successful action'}</option>
            {sources.map((item) => (
              <option key={item.id} value={item.id}>
                {formatTimestamp(item.timestamp || item.created_at)
                  + ' - ' + String(item.mode || item.action || 'generation')
                  + ' - ' + String((item.generated_case_ids || []).length) + ' case(s)'}
              </option>
            ))}
          </Select>
          {source ? (
            <p className="text-[10px] text-text-mute">
              {truncate(String(source.business_requirements || ''), 220)}
            </p>
          ) : null}
        </section>

        <section className="flex flex-col gap-1.5">
          <h4 className="text-[11px] font-bold uppercase tracking-[0.07em] text-text-dim">
            {'2 - Baseline (' + String(baselineIds.length) + ')'}
          </h4>
          <p className="text-[10px] text-text-mute">
            Baseline cases are carried into the revision and may be refined by the model.
          </p>
          <div className="aa-scroll max-h-[16rem] overflow-y-auto rounded border border-line bg-panel-alt p-1.5">
            {groups.length === 0 ? (
              <p className="px-1 py-1 text-[11px] text-text-mute">
                Choose a source action that produced cases.
              </p>
            ) : null}
            {groups.map((group) => {
              const all = group.cases.every((item) => baselineIds.includes(item.id));
              return (
                <div key={group.label} className="mb-1.5">
                  <div className="flex items-center gap-1.5 border-b border-line-soft pb-1">
                    <Checkbox
                      checked={all}
                      aria-label={'Select group ' + group.label}
                      onChange={() => toggleGroup(group.cases, !all)}
                    />
                    <span className="text-[10.5px] font-bold uppercase tracking-[0.06em] text-text-dim">
                      {group.label}
                    </span>
                    <Badge tone="neutral" dot={false}>{String(group.cases.length)}</Badge>
                  </div>
                  {group.cases.map((item) => (
                    <label
                      key={item.id}
                      className="flex cursor-pointer items-center gap-1.5 px-1 py-0.5 text-[11px] text-text-dim"
                    >
                      <Checkbox
                        checked={baselineIds.includes(item.id)}
                        aria-label={'Baseline ' + item.name}
                        onChange={() => setBaselineIds((previous) => toggle(previous, item.id))}
                      />
                      <span className="min-w-0 flex-1 truncate">{item.name}</span>
                      <Badge tone="neutral" dot={false}>{String(item.type || 'case')}</Badge>
                    </label>
                  ))}
                </div>
              );
            })}
          </div>
        </section>

        <section className="flex flex-col gap-1.5">
          <h4 className="text-[11px] font-bold uppercase tracking-[0.07em] text-text-dim">
            {'3 - Keep unchanged (' + String(keepIds.length) + ')'}
          </h4>
          <p className="text-[10px] text-text-mute">
            Chosen baseline cases are copied verbatim; everything else is re-authored.
          </p>
          {baselineIds.length === 0 ? (
            <p className="text-[11px] text-text-mute">Select baseline cases first.</p>
          ) : null}
          <div className="flex flex-col gap-0.5">
            {candidates.filter((item) => baselineIds.includes(item.id)).map((item) => (
              <label
                key={item.id}
                className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 text-[11px] text-text-dim hover:bg-hover"
              >
                <Checkbox
                  checked={keepIds.includes(item.id)}
                  aria-label={'Keep ' + item.name + ' unchanged'}
                  onChange={() => setKeepIds((previous) => toggle(previous, item.id))}
                />
                <span className="min-w-0 flex-1 truncate">{item.name}</span>
              </label>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-1.5">
          <h4 className="text-[11px] font-bold uppercase tracking-[0.07em] text-text-dim">
            {'4 - Endpoint scope (optional, ' + String(endpointIds.length) + ' chosen)'}
          </h4>
          <p className="text-[10px] text-text-mute">
            Leave empty to regenerate from every saved request.
          </p>
          <div className="flex gap-1">
            <Button small onClick={() => setEndpointIds(endpoints.map((item) => item.id))}>
              All
            </Button>
            <Button small onClick={() => setEndpointIds([])}>
              None
            </Button>
          </div>
          <div className="aa-scroll max-h-[13rem] overflow-y-auto rounded border border-line bg-panel p-1.5">
            {scopeEndpoints.length === 0 ? (
              <p className="px-1 py-1 text-[11px] text-text-mute">No saved requests.</p>
            ) : null}
            {scopeEndpoints.map((item) => (
              <label
                key={item.id}
                className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 text-[11px] text-text-dim hover:bg-hover"
              >
                <Checkbox
                  checked={endpointIds.includes(item.id)}
                  aria-label={'Scope ' + (item.name || item.url)}
                  onChange={() => setEndpointIds((previous) => (
                    previous.includes(item.id)
                      ? previous.filter((id) => id !== item.id)
                      : [...previous, item.id]
                  ))}
                />
                <span className="min-w-0 flex-1 truncate">{item.name || item.url}</span>
                <Badge tone="neutral" dot={false}>{String(item.method || 'GET')}</Badge>
              </label>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-1.5">
          <h4 className="text-[11px] font-bold uppercase tracking-[0.07em] text-text-dim">
            5 - Release
          </h4>
          <Field label="Release label">
            <Input
              value={label}
              aria-label="Release label"
              className="h-8"
              placeholder="Revision 2"
              onChange={(event) => setLabel(event.target.value)}
            />
          </Field>
          <Field
            label="New requirement changes"
            tooltip="Describe changed behavior, new rules, and release context. Previous generation requirements are carried forward separately and remain read-only."
          >
            <Textarea
              rows={3}
              value={notes}
              aria-label="New requirement changes"
              placeholder="What changed in this release?"
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>
          <Field label="Chat thread context" tooltip="Optionally include the selected project conversation as additional context for this revision.">
            <Select
              value={threadId}
              aria-label="Chat thread context"
              className="h-8"
              onChange={(event) => setThreadId(event.target.value)}
            >
              <option value="">No chat thread</option>
              {threads.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title + (item.archived ? ' (archived)' : '')}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Knowledge coverage" tooltip="Changed knowledge emphasizes recent approved updates; full knowledge includes all relevant saved context.">
            <Select
              value={coverage}
              aria-label="Knowledge coverage"
              className="h-8"
              onChange={(event) => setCoverage(event.target.value === 'full' ? 'full' : 'changed')}
            >
              <option value="changed">Changed knowledge</option>
              <option value="full">Full knowledge</option>
            </Select>
          </Field>

          {briefs.length > 0 ? (
            <div>
              <p className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-text-mute">
                {'Briefs (' + String(briefIds.length) + ')'}
              </p>
              <div className="mt-1 flex flex-col gap-0.5">
                {briefs.map((brief) => (
                  <label
                    key={brief.id}
                    className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 text-[11px] text-text-dim hover:bg-hover"
                  >
                    <Checkbox
                      checked={briefIds.includes(brief.id)}
                      aria-label={'Include ' + brief.name}
                      onChange={() => setBriefIds((previous) => toggle(previous, brief.id))}
                    />
                    <span className="min-w-0 flex-1 truncate">{brief.name}</span>
                    <Badge tone="neutral" dot={false}>{String(brief.scope_type || '')}</Badge>
                  </label>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </Modal>
  );
}
