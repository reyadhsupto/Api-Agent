'use client';

import React, { useCallback, useEffect, useState } from 'react';

import PageShell, { PageHeader } from '@/components/layout/PageShell';
import TestCaseCard from '@/components/test-cases/TestCaseCard';
import ManualCaseBuilder from '@/components/test-cases/ManualCaseBuilder';
import RevisionDialog from '@/components/test-cases/RevisionDialog';
import TestRunManager from '@/components/test-cases/TestRunManager';
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, Menu, MethodBadge, Notice, Select,
  Spinner, Textarea, cx,
} from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';
import { useAsync } from '@/lib/hooks';
import { api } from '@/lib/api';
import { answerClarifications, executeCase, exportCasesCsv, generateCases, saveCases } from '@/lib/testcases';
import type {
  BriefScope, ChatThread, ClarificationQuestion, CoverageSummary, GenerationResponse, TestCase,
} from '@/types/api';

const MODES = ['Single', 'General', 'Flow'] as const;

/** Download a blob without leaving the page. */
function downloadBlob(blob: Blob, filename: string): void {
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

/**
 * Render the Test Cases workspace.
 *
 * @returns Test cases page element.
 */
export default function TestCasesPage() {
  const { project, isLoadingProject, refreshProject } = useProject();
  const projectId = project?.id || '';

  const [mode, setMode] = useState<'Single' | 'General' | 'Flow'>('Single');
  const [endpointIds, setEndpointIds] = useState<string[]>([]);
  const [draggingEndpointId, setDraggingEndpointId] = useState<string | null>(null);
  const [dropEndpointId, setDropEndpointId] = useState<string | null>(null);
  const [exampleIds, setExampleIds] = useState<string[]>([]);
  const [briefIds, setBriefIds] = useState<string[]>([]);
  const [threadId, setThreadId] = useState('');
  const [requirements, setRequirements] = useState('');
  const [coverage, setCoverage] = useState<'changed' | 'full'>('changed');
  const [generalName, setGeneralName] = useState('General scenarios');

  const [phase, setPhase] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [note, setNote] = useState('');
  const [generated, setGenerated] = useState<TestCase[]>([]);
  const [questions, setQuestions] = useState<ClarificationQuestion[]>([]);
  const [summary, setSummary] = useState<CoverageSummary | null>(null);
  const [activityId, setActivityId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const [expanded, setExpanded] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [statusFilter, setStatusFilter] = useState('All');
  const [revisionFilter, setRevisionFilter] = useState('latest');
  const [collectionFilter, setCollectionFilter] = useState('All');
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [runErrors, setRunErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [loadedRunId, setLoadedRunId] = useState<string | null>(null);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [clearArmed, setClearArmed] = useState(false);

  const threads = useAsync<ChatThread[]>(
    () => (projectId
      ? api.get<ChatThread[]>('/api/v1/projects/' + projectId + '/chat/threads?include_archived=true')
      : Promise.resolve([])),
    [projectId],
  );

  const scopes = useAsync<BriefScope[]>(
    () => (projectId
      ? api.get<BriefScope[]>('/api/v1/projects/' + projectId + '/brief-scopes')
      : Promise.resolve([])),
    [projectId],
  );

  const savedCases = project?.test_cases;
  const endpoints = project?.endpoints || [];
  const eligibleEndpoints = endpoints.filter((item) => item.include_for_generation ?? item.include ?? false);
  const eligibleEndpointIds = eligibleEndpoints.map((item) => item.id);
  const collections = project?.collections || [];
  const revisions = project?.test_case_revisions || [];
  const order = project?.generation_order_ids || [];
  const runs = project?.test_runs || [];

  // Use API Workspace eligibility as the source of truth for generation scope.
  // A handoff may pass repeated `endpoint` query parameters to preselect a subset.
  useEffect(() => {
    if (!projectId) return;
    const params = new URLSearchParams(window.location.search);
    const requested = params.getAll('endpoint');
    const initial = params.has('endpoint')
      ? requested.filter((id) => eligibleEndpointIds.includes(id))
      : eligibleEndpointIds;
    setEndpointIds([...new Set(initial)]);
    // This initializes once per project; refreshing project data must not
    // overwrite the user's current selection or Flow order.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Seed the result filter from recorded executions. Without this a reload reports
  // every saved case as unrun, including cases that failed and are still failing.
  useEffect(() => {
    const records = (project?.executions as Array<Record<string, unknown>> | undefined) || [];
    const seeded: Record<string, string> = {};
    records.forEach((item) => {
      const caseId = typeof item.test_case_id === 'string' ? item.test_case_id : '';
      const status = typeof item.status === 'string' ? item.status : '';
      if (caseId && status) seeded[caseId] = status;
    });
    setStatuses(seeded);
  }, [project]);

  /** True when the view shows history, which is read only. */
  const isReadOnly = revisionFilter !== 'latest' && revisionFilter !== 'all';

  /**
   * Reload the project after a case is added.
   */
  const afterCreated = useCallback(async (): Promise<void> => {
    await refreshProject();
    setFlash('Added a manual case to the project.');
  }, [refreshProject]);

  /**
   * Reload the project after a revision is generated and show its cases.
   *
   * @param created - Cases produced by the revision.
   */
  const afterRevision = useCallback(async (created: TestCase[]): Promise<void> => {
    await refreshProject();
    setGenerated((prev) => [...prev, ...created.filter((item) => !prev.some((row) => row.id === item.id))]);
    setRevisionFilter('all');
    setFlash('Created a release revision with ' + String(created.length) + ' case(s).');
  }, [refreshProject]);


  /** Cases authored in this session that the project does not have yet. */
  const unsavedCount = generated.length;

  /**
   * Delete every case in the project after a two-step confirmation.
   */
  const clearAll = async (): Promise<void> => {
    if (!projectId || cases.length === 0) return;
    if (!clearArmed) {
      setClearArmed(true);
      return;
    }
    setBusy(true);
    setFlash(null);
    try {
      await api.delete('/api/v1/projects/' + projectId + '/test-cases');
      setGenerated([]);
      setSelected([]);
      setExpanded([]);
      setStatuses({});
      setQuestions([]);
      setSummary(null);
      setClearArmed(false);
      await refreshProject();
      setFlash('Cleared every case in the project.');
    } catch (caught) {
      setFlash(caught instanceof Error ? caught.message : 'Could not clear the cases');
    } finally {
      setBusy(false);
    }
  };

  // Saved cases keep the server order, then session-only cases follow.
  const knownCaseIds = new Set((savedCases || []).map((item) => item.id));
  const cases = [
    ...(savedCases || []),
    ...generated.filter((item) => !knownCaseIds.has(item.id)),
  ];

  const visibleCases = cases.filter((item) => {
    if (revisionFilter === 'latest' && item.superseded_by_activity_id) return false;
    if (revisionFilter !== 'latest' && revisionFilter !== 'all'
      && item.revision_id !== revisionFilter) return false;
    if (collectionFilter !== 'All'
      && (item.case_collection_id || '__general__') !== collectionFilter) return false;
    if (statusFilter !== 'All' && (statuses[item.id] || 'not_run') !== statusFilter) return false;
    return true;
  });

  /** Result counts across every case, for the toolbar summary. */
  const statusCounts: Record<'passed' | 'failed' | 'error' | 'not_run', number> = {
    passed: 0, failed: 0, error: 0, not_run: 0,
  };
  cases.forEach((item) => {
    const status = statuses[item.id] || 'not_run';
    if (status === 'passed' || status === 'failed' || status === 'error') statusCounts[status] += 1;
    else statusCounts.not_run += 1;
  });

  const eligibleById = new Map(eligibleEndpoints.map((item) => [item.id, item]));
  const selectedEndpoints = endpointIds
    .map((id) => eligibleById.get(id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const generationList = [
    ...endpointIds.map((id) => eligibleById.get(id)).filter((item): item is NonNullable<typeof item> => Boolean(item)),
    ...eligibleEndpoints
      .filter((item) => !endpointIds.includes(item.id))
      .sort((left, right) => {
        const li = order.indexOf(left.id);
        const ri = order.indexOf(right.id);
        return (li < 0 ? 1e9 : li) - (ri < 0 ? 1e9 : ri);
      }),
  ];

  const allExpanded = visibleCases.length > 0
    && visibleCases.every((item) => expanded.includes(item.id));

  /** Add or remove one identifier from a selection list. */
  const toggle = (list: string[], id: string) => (
    list.includes(id) ? list.filter((item) => item !== id) : [...list, id]
  );

  /** Move a selected request within a Flow and persist the project order. */
  const reorderFlowEndpoints = async (sourceId: string, targetId: string) => {
    if (!projectId || sourceId === targetId) return;
    const selectedOrder = endpointIds.filter((id) => eligibleById.has(id));
    const from = selectedOrder.indexOf(sourceId);
    const to = selectedOrder.indexOf(targetId);
    if (from < 0 || to < 0) return;
    const reorderedSelection = [...selectedOrder];
    const [moved] = reorderedSelection.splice(from, 1);
    reorderedSelection.splice(to, 0, moved);
    setEndpointIds((previous) => {
      const selection = previous.filter((id) => eligibleById.has(id));
      const untouched = previous.filter((id) => !eligibleById.has(id));
      return [...reorderedSelection, ...untouched, ...selection.filter((id) => !reorderedSelection.includes(id))];
    });

    const allIds = endpoints.map((item) => item.id);
    const oldOrder = [...new Set([...order.filter((id) => allIds.includes(id)), ...allIds])];
    const selectedSet = new Set(selectedOrder);
    let selectedIndex = 0;
    const nextOrder = oldOrder.map((id) => {
      if (!selectedSet.has(id)) return id;
      const nextId = reorderedSelection[selectedIndex];
      selectedIndex += 1;
      return nextId || id;
    });
    try {
      await api.put('/api/v1/projects/' + projectId + '/generation-order', { request_ids: nextOrder });
      await refreshProject();
    } catch (caught) {
      setFlash(caught instanceof Error ? caught.message : 'Could not save Flow order');
    }
  };

  /** Merge a generation envelope into the local case list. */
  const mergeResponse = (response: GenerationResponse) => {
    const incoming = response.test_cases || [];
    setGenerated((prev) => {
      const seen = new Set(prev.map((item) => item.id));
      return [...prev, ...incoming.filter((item) => !seen.has(item.id))];
    });
    setQuestions(response.clarification_questions || []);
    setSummary(response.coverage_summary || null);
    setActivityId(response.activity?.id || null);
    setAnswers({});
    return incoming.length;
  };

  /** Ask the configured providers for a new suite. */
  const generate = async () => {
    if (!projectId || (mode !== 'General' && selectedEndpoints.length === 0) || phase === 'running') return;
    setPhase('running');
    setNote('Generating with the configured providers.');
    setFlash(null);
    try {
      // The backend authors cases for one request per call, so single mode loops
      // over the selection instead of silently generating for the first request.
      const batches = mode === 'Single'
        ? selectedEndpoints.map((endpoint) => [endpoint])
        : [selectedEndpoints];
      let count = 0;
      for (const batch of batches) {
        const response = await generateCases({
          mode,
          endpoints: batch,
          exampleIds,
          requirements,
          projectId,
          threadId: threadId || null,
          briefScopeIds: briefIds,
          coverage,
          generalCollectionId: mode === 'General' ? '__general_scenarios__' : null,
          generalCollectionName: mode === 'General' ? generalName : null,
        });
        count += mergeResponse(response);
      }
      setPhase(count ? 'done' : 'error');
      setNote(count
        ? 'Generated ' + String(count) + ' case(s).'
        : 'The model returned no test cases.');
      await refreshProject();
    } catch (caught) {
      setPhase('error');
      setNote(caught instanceof Error ? caught.message : 'Generation failed');
    } finally {
      setCooldown(true);
      window.setTimeout(() => setCooldown(false), 3000);
    }
  };

  /** Send clarification answers and merge the refined suite. */
  const submitAnswers = async () => {
    if (!activityId) return;
    setPhase('running');
    setNote('Refining with your answers.');
    try {
      const response = await answerClarifications(projectId, activityId, answers);
      const count = mergeResponse(response);
      setPhase(count ? 'done' : 'error');
      setNote('Refined suite contains ' + String(count) + ' case(s).');
      await refreshProject();
    } catch (caught) {
      setPhase('error');
      setNote(caught instanceof Error ? caught.message : 'Could not refine the suite');
    }
  };

  /** Execute every selected, runnable case in order. */
  const runSelected = async () => {
    const targets = visibleCases.filter((item) => selected.includes(item.id));
    if (targets.length === 0) {
      setFlash('Select at least one case first.');
      return;
    }
    const runnable = targets.filter((item) => item.case_kind !== 'general');
    const skipped = targets.length - runnable.length;
    if (runnable.length === 0) {
      setFlash('Every selected case is a manual general scenario.');
      return;
    }
    setBusy(true);
    setRunErrors([]);
    setFlash(null);
    setProgress({ done: 0, total: runnable.length });
    const errors: string[] = [];
    for (let index = 0; index < runnable.length; index += 1) {
      const item = runnable[index];
      try {
        const result = await executeCase(projectId, item);
        setStatuses((prev) => ({ ...prev, [item.id]: result.status }));
      } catch (caught) {
        errors.push(item.name + ': ' + (caught instanceof Error ? caught.message : 'failed'));
        setStatuses((prev) => ({ ...prev, [item.id]: 'error' }));
      }
      setProgress({ done: index + 1, total: runnable.length });
    }
    setRunErrors(errors);
    setBusy(false);
    setFlash('Ran ' + String(runnable.length) + ' case(s).'
      + (skipped ? ' Skipped ' + String(skipped) + ' manual case(s).' : ''));
  };

  /** Download the CSV for selected cases, or every visible case. */
  const exportCsv = async () => {
    if (!projectId) return;
    setBusy(true);
    setFlash(null);
    try {
      const ids = visibleCases.filter((item) => selected.includes(item.id)).map((item) => item.id);
      const { blob, filename } = await exportCasesCsv(projectId, ids);
      downloadBlob(blob, filename);
      setFlash('Exported ' + String(ids.length || visibleCases.length) + ' case(s).');
    } catch (caught) {
      setFlash(caught instanceof Error ? caught.message : 'Export failed');
    } finally {
      setBusy(false);
    }
  };

  /** Persist selected and newly generated cases. */
  const saveAll = async () => {
    if (!projectId) return;
    const targets = visibleCases.filter((item) => (
      generated.some((candidate) => candidate.id === item.id)
      || selected.includes(item.id)
    ));
    if (targets.length === 0) {
      setFlash('Nothing to save yet.');
      return;
    }
    setBusy(true);
    try {
      const result = await saveCases(projectId, targets);
      setGenerated((prev) => prev.filter((item) => (
        !targets.some((saved) => saved.id === item.id)
      )));
      setFlash('Saved ' + String(result.count ?? targets.length) + ' case(s) to the project.');
      await refreshProject();
    } catch (caught) {
      setFlash(caught instanceof Error ? caught.message : 'Could not save the cases');
    } finally {
      setBusy(false);
    }
  };

  /** Drop a deleted case from every local selection. */
  const removeCase = async (id: string) => {
    setGenerated((prev) => prev.filter((item) => item.id !== id));
    setSelected((prev) => prev.filter((item) => item !== id));
    setExpanded((prev) => prev.filter((item) => item !== id));
    await refreshProject();
  };

  /** Toggle every visible card between expanded and collapsed. */
  const toggleAll = () => {
    setExpanded(allExpanded ? [] : visibleCases.map((item) => item.id));
  };

  return (
    <PageShell>
      <PageHeader
        title="Test Cases"
        description="Generate suites from saved requests, then review and execute them."
        actions={
          <>
            <Badge tone="neutral">{String(cases.length)} total</Badge>
            <Badge tone="ok">{String(statusCounts.passed) + ' passed'}</Badge>
            <Badge tone="bad">{String(statusCounts.failed) + ' failed'}</Badge>
            <Badge tone="warn">{String(statusCounts.error) + ' error'}</Badge>
            <Badge tone="neutral">{String(statusCounts.not_run) + ' not run'}</Badge>
            <Menu
              label="Batch actions"
              items={[
                { label: 'Run selected', icon: 'play', disabled: busy || selected.length === 0, onSelect: () => void runSelected() },
                { label: 'Export CSV', icon: 'download', disabled: busy || visibleCases.length === 0, onSelect: () => void exportCsv() },
                { label: 'Save to project', icon: 'save', disabled: busy, onSelect: () => void saveAll() },
              ]}
            />
          </>
        }
      />

      {flash ? (
        <div className="mb-3">
          <Notice tone="info">{flash}</Notice>
        </div>
      ) : null}

      {!project && !isLoadingProject ? (
        <EmptyState
          title="No project selected"
          body="Pick a project in the rail, then save a request in API Workspace."
        />
      ) : !project ? (
        <Spinner label="Loading project" />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
            <ManualCaseBuilder
              projectId={projectId}
              endpoints={endpoints}
              onCreated={afterCreated}
            />
            <TestRunManager
              projectId={projectId}
              runs={runs}
              selectedIds={selected.length > 0 ? selected : visibleCases.map((item) => item.id)}
              loadedRunId={loadedRunId}
              onLoad={(runId) => {
                setLoadedRunId(runId);
                const run = runs.find((item) => item.id === runId);
                setSelected(run ? run.case_ids || [] : []);
              }}
              onChanged={() => refreshProject()}
            />
          </div>

          <Card className="p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[12.5px] font-bold text-text">Generate cases</h2>
              <div className="flex flex-wrap items-center gap-1">
                {MODES.map((value) => (
                  <Button
                    key={value}
                    small
                    tone={mode === value ? 'secondary' : 'ghost'}
                    aria-pressed={mode === value}
                    onClick={() => setMode(value)}
                  >
                    {value === 'Single' ? 'Single endpoint' : value === 'General' ? 'General' : 'Flow'}
                  </Button>
                ))}
              </div>
            </div>

            <p className="mt-1.5 text-[10.5px] text-text-mute">
              {mode === 'Flow'
                ? 'Drag selected requests into the order they should run. Order is saved to this project.'
                : mode === 'General'
                  ? 'Requirements-only scenarios, recorded manually after a tester runs them.'
                  : 'Choose one or more saved requests to generate focused tests for.'}
            </p>

            <div className="aa-scroll mt-2 max-h-[8rem] overflow-y-auto rounded-md border border-line bg-panel-alt p-1.5">
              {eligibleEndpoints.length === 0 ? (
                <p className="px-1 py-1 text-[11px] text-text-mute">
                  No requests are enabled for generation. Enable requests in API Workspace first.
                </p>
              ) : null}
              {generationList.map((endpoint) => {
                const checked = endpointIds.includes(endpoint.id);
                const position = endpointIds.indexOf(endpoint.id);
                return (
                  <div
                    key={endpoint.id}
                    draggable={mode === 'Flow' && checked}
                    onDragStart={(event) => {
                      if (mode !== 'Flow' || !checked) return;
                      event.dataTransfer.effectAllowed = 'move';
                      event.dataTransfer.setData('text/plain', endpoint.id);
                      setDraggingEndpointId(endpoint.id);
                    }}
                    onDragOver={(event) => {
                      if (mode === 'Flow' && checked && draggingEndpointId) {
                        event.preventDefault();
                        event.dataTransfer.dropEffect = 'move';
                        setDropEndpointId(endpoint.id);
                      }
                    }}
                    onDrop={(event) => {
                      event.preventDefault();
                      const sourceId = event.dataTransfer.getData('text/plain') || draggingEndpointId;
                      if (sourceId) void reorderFlowEndpoints(sourceId, endpoint.id);
                      setDraggingEndpointId(null);
                      setDropEndpointId(null);
                    }}
                    onDragEnd={() => { setDraggingEndpointId(null); setDropEndpointId(null); }}
                    className={cx(
                      'flex items-center gap-1.5 rounded px-1 py-1 hover:bg-hover',
                      mode === 'Flow' && checked ? 'cursor-grab active:cursor-grabbing' : '',
                      draggingEndpointId === endpoint.id ? 'opacity-40' : '',
                      dropEndpointId === endpoint.id ? 'outline outline-1 outline-accent' : '',
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      aria-label={'Generate for ' + (endpoint.name || endpoint.url)}
                      onChange={() => setEndpointIds(toggle(endpointIds, endpoint.id))}
                    />
                    {mode === 'Flow' ? (
                      <span className="w-5 shrink-0 text-center font-mono text-[9.5px] text-text-mute" title="Selected Flow position">
                        {checked ? String(position + 1) : '–'}
                      </span>
                    ) : null}
                    <MethodBadge method={endpoint.method} />
                    <span className="min-w-0 flex-1 truncate text-[11.5px] text-text">
                      {endpoint.name || endpoint.url}
                    </span>
                    {mode === 'Flow' && checked ? (
                      <span className="flex shrink-0 items-center gap-1">
                        <Button
                          small
                          disabled={position <= 0}
                          aria-label="Move Flow endpoint earlier"
                          onClick={() => {
                            const previousId = endpointIds[position - 1];
                            if (previousId) void reorderFlowEndpoints(endpoint.id, previousId);
                          }}
                        >
                          Up
                        </Button>
                        <Button
                          small
                          disabled={position < 0 || position >= selectedEndpoints.length - 1}
                          aria-label="Move Flow endpoint later"
                          onClick={() => {
                            const nextId = endpointIds[position + 1];
                            if (nextId) void reorderFlowEndpoints(endpoint.id, nextId);
                          }}
                        >
                          Down
                        </Button>
                        <span aria-hidden="true" className="select-none px-0.5 text-text-mute">⠿</span>
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>

            {mode === 'General' ? (
              <Input
                value={generalName}
                aria-label="General case collection name"
                placeholder="General collection name"
                className="mt-2 h-8"
                onChange={(event) => setGeneralName(event.target.value)}
              />
            ) : null}

            {(savedCases || []).length > 0 ? (
              <details className="mt-2 rounded-md border border-line bg-panel-alt px-2 py-1.5">
                <summary className="cursor-pointer list-none text-[11px] font-semibold text-text-dim [&::-webkit-details-marker]:hidden">
                  {'Examples (' + String(exampleIds.length) + ')'}
                </summary>
                <div className="aa-scroll mt-1.5 flex max-h-[8rem] flex-col gap-1 overflow-y-auto">
                  {(savedCases || []).map((item) => (
                    <label
                      key={item.id}
                      className="flex cursor-pointer items-center gap-1.5 text-[11px] text-text-dim"
                    >
                      <Checkbox
                        checked={exampleIds.includes(item.id)}
                        aria-label={'Use ' + item.name + ' as an example'}
                        onChange={() => setExampleIds(toggle(exampleIds, item.id))}
                      />
                      <span className="truncate">{item.name}</span>
                    </label>
                  ))}
                </div>
              </details>
            ) : null}

            <details className="mt-2 rounded-md border border-line bg-panel-alt px-2 py-1.5">
              <summary className="cursor-pointer list-none text-[11px] font-semibold text-text-dim [&::-webkit-details-marker]:hidden">
                {'Project context (' + String(briefIds.length + (threadId ? 1 : 0)) + ')'}
              </summary>
                               <div className="aa-scroll mt-1.5 flex max-h-[13rem] flex-col gap-1.5 overflow-y-auto">
                <p className="text-[10px] text-text-mute">
                  The project overview page is always included.
                </p>
                {(scopes.data || []).map((scope) => (
                  <label
                    key={scope.id}
                    className="flex cursor-pointer items-center gap-1.5 text-[11px] text-text-dim"
                  >
                    <Checkbox
                      checked={briefIds.includes(scope.id)}
                      aria-label={'Include ' + (scope.name || scope.id) + ' brief'}
                      onChange={() => setBriefIds(toggle(briefIds, scope.id))}
                    />
                    <span className="truncate">{scope.name || scope.id}</span>
                    <span className="ml-auto shrink-0 text-[9.5px] uppercase tracking-[0.06em] text-text-mute">
                      {scope.scope_type || 'feature'}
                    </span>
                  </label>
                ))}
                <Select
                  value={threadId}
                  aria-label="Chat thread context"
                  className="h-8"
                  onChange={(event) => setThreadId(event.target.value)}
                >
                  <option value="">No chat thread</option>
                  {(threads.data || []).map((thread) => (
                    <option key={thread.id} value={thread.id}>
                      {thread.title + (thread.archived ? ' (archived)' : '')}
                    </option>
                  ))}
                </Select>
              </div>
            </details>

            <Textarea
              rows={3}
              className="mt-2 text-[11.5px]"
              value={requirements}
              aria-label="Business requirements"
              title="Requirements for this generation action only. Saved project and feature knowledge is included separately; this field does not update it."
              placeholder="Business rules, edge cases, or expected behavior..."
              onChange={(event) => setRequirements(event.target.value)}
            />

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Select
                value={coverage}
                aria-label="Knowledge coverage"
                title="Changed knowledge focuses on recent approved updates; full knowledge includes all relevant saved context."
                className="h-8 w-36"
                onChange={(event) => setCoverage(event.target.value as 'changed' | 'full')}
              >
                <option value="changed">Changed knowledge</option>
                <option value="full">Full knowledge</option>
              </Select>
              <Button
                tone="primary"
                icon="sparkles"
                loading={phase === 'running'}
                disabled={phase === 'running' || cooldown || (mode !== 'General' && selectedEndpoints.length === 0)}
                onClick={() => void generate()}
              >
                {phase === 'running' ? 'Generating…' : cooldown ? 'Wait a moment' : 'Generate cases'}
              </Button>
            </div>

            {phase === 'running' ? (
              <div className="mt-3 overflow-hidden rounded-md border border-accent/25 bg-accent/5 p-3" role="status" aria-live="polite">
                <div className="flex items-center gap-2 text-[11.5px] font-semibold text-text">
                  <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent border-r-transparent" aria-hidden="true" />
                  Generating test cases with the configured model. This may take a few minutes.
                  <span aria-hidden="true" className="inline-flex gap-0.5 text-accent">
                    {[0, 1, 2].map((dot) => (
                      <span key={dot} className="animate-bounce font-bold" style={{ animationDelay: `${dot * 120}ms` }}>·</span>
                    ))}
                  </span>
                </div>
                <div className="mt-2 h-1 overflow-hidden rounded-full bg-line">
                  <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
                </div>
              </div>
            ) : null}

            {note ? (
              <p
                className={cx(
                  'mt-1.5 aa-wrap-anywhere text-[10.5px]',
                  phase === 'error' ? 'text-bad' : phase === 'done' ? 'text-ok' : 'text-text-mute',
                )}
              >
                {note}
              </p>
            ) : null}
          </Card>

          {summary ? (
            <Card className="p-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-[12.5px] font-bold text-text">Coverage</h2>
                <Badge tone="neutral">
                  {String((summary.requirements || []).length)} requirement(s)
                </Badge>
              </div>
              <div className="mt-2 flex flex-col gap-1">
                {(summary.requirements || []).map((item, index) => (
                  <div key={String(index)} className="flex items-start gap-1.5 text-[11px]">
                    <Badge tone={item.covered ? 'ok' : 'warn'}>
                      {item.covered ? 'covered' : 'gap'}
                    </Badge>
                    <span className="min-w-0 text-text-dim">
                      {item.requirement || item.requirement_id || 'Requirement'}
                    </span>
                  </div>
                ))}
                {(summary.unsupported_claims || []).map((claim, index) => (
                  <p key={String(index)} className="aa-wrap-anywhere text-[10.5px] text-warn">
                    Unsupported claim: {claim}
                  </p>
                ))}
                {summary.note ? (
                  <p className="aa-wrap-anywhere text-[10.5px] text-text-mute">{summary.note}</p>
                ) : null}
              </div>
            </Card>
          ) : null}

          {questions.length > 0 ? (
            <Card className="p-3">
              <h2 className="text-[12.5px] font-bold text-text">Clarifications</h2>
              <p className="mt-1 text-[10.5px] text-text-mute">
                Answer what you know, then refine the suite with the same providers.
              </p>
              <div className="mt-2 flex flex-col gap-2">
                {questions.map((item, index) => {
                  const key = item.id || 'question_' + String(index);
                  return (
                    <div key={key} className="flex flex-col gap-1">
                      <span className="text-[11.5px] text-text">
                        {item.question || item.text || 'Question'}
                      </span>
                      {item.why ? (
                        <span className="text-[10px] text-text-mute">{item.why}</span>
                      ) : null}
                      <Input
                        value={answers[key] || ''}
                        aria-label={'Answer to ' + key}
                        placeholder="Your answer"
                        className="h-8"
                        onChange={(event) => setAnswers({ ...answers, [key]: event.target.value })}
                      />
                    </div>
                  );
                })}
              </div>
              <Button
                small
                tone="primary"
                icon="send"
                loading={phase === 'running'}
                className="mt-2 self-start"
                disabled={phase === 'running'}
                onClick={() => void submitAnswers()}
              >
                {phase === 'running' ? 'Refining…' : 'Refine suite'}
              </Button>
            </Card>
          ) : null}

          <Card className="p-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <Button small icon="layers" onClick={toggleAll}>
                {allExpanded ? 'Collapse all' : 'Expand all'}
              </Button>
              <Button
                small
                onClick={() => setSelected(
                  selected.length === visibleCases.length
                    ? []
                    : visibleCases.map((item) => item.id),
                )}
              >
                {selected.length === visibleCases.length && visibleCases.length > 0
                  ? 'Deselect all'
                  : 'Select all'}
              </Button>
              <Button small icon="download" disabled={busy} onClick={() => void exportCsv()}>
                Export CSV
              </Button>
              <Button
                small
                icon="play"
                disabled={busy || selected.length === 0}
                onClick={() => void runSelected()}
              >
                Run selected
              </Button>
              <Button small icon="save" disabled={busy || isReadOnly} onClick={() => void saveAll()}>
                Save to project
              </Button>
              <Button
                small
                icon="sparkles"
                disabled={busy || unsavedCount > 0}
                onClick={() => setRevisionOpen(true)}
              >
                Create revision
              </Button>
              <Button
                small
                tone="danger"
                icon="trash"
                disabled={busy || cases.length === 0}
                onClick={() => void clearAll()}
              >
                {clearArmed ? 'Confirm clear' : 'Clear all'}
              </Button>
              <span className="ml-auto text-[10.5px] font-semibold text-text-mute">
                {progress
                  ? String(progress.done) + ' / ' + String(progress.total)
                  : String(visibleCases.length) + ' case(s)'}
              </span>
            </div>

            <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-3">
              <Select
                value={revisionFilter}
                aria-label="Revision filter"
                className="h-8"
                onChange={(event) => setRevisionFilter(event.target.value)}
              >
                <option value="latest">Latest revision</option>
                <option value="all">All revisions</option>
                {revisions.map((revision) => (
                  <option key={revision.id} value={revision.id}>{revision.label}</option>
                ))}
              </Select>
              <Select
                value={collectionFilter}
                aria-label="Collection filter"
                className="h-8"
                onChange={(event) => setCollectionFilter(event.target.value)}
              >
                <option value="All">All collections</option>
                <option value="__general__">General scenarios</option>
                {collections.map((collection) => (
                  <option key={collection.id} value={collection.id}>{collection.name}</option>
                ))}
              </Select>
              <Select
                value={statusFilter}
                aria-label="Result filter"
                className="h-8"
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                <option value="All">All results</option>
                <option value="passed">Passed</option>
                <option value="failed">Failed</option>
                <option value="error">Error</option>
                <option value="not_run">Not run</option>
              </Select>
            </div>

            {progress ? (
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-pill bg-chip-fill">
                <div
                  className="h-full bg-accent"
                  style={{
                    width: (progress.total
                      ? Math.round((progress.done / progress.total) * 100)
                      : 0) + '%',
                  }}
                />
              </div>
            ) : null}

            {runErrors.length > 0 ? (
              <div className="mt-2 flex flex-col gap-1">
                {runErrors.map((item, index) => (
                  <p key={String(index)} className="aa-wrap-anywhere text-[10.5px] text-bad">
                    {item}
                  </p>
                ))}
              </div>
            ) : null}
          </Card>

          <div className="flex flex-col gap-2">
            {visibleCases.length === 0 ? (
              <EmptyState
                title="No cases match the filters"
                body="Clear a filter, or generate a new suite from the panel above."
              />
            ) : null}

            {visibleCases.map((item) => (
              <TestCaseCard
                key={item.id}
                testCase={item}
                projectId={projectId}
                latestStatus={statuses[item.id]}
                selected={selected.includes(item.id)}
                expanded={expanded.includes(item.id)}
                onSelect={(next) => setSelected((prev) => (
                  next
                    ? [...new Set([...prev, item.id])]
                    : prev.filter((id) => id !== item.id)
                ))}
                onToggle={() => setExpanded((prev) => (
                  prev.includes(item.id)
                    ? prev.filter((id) => id !== item.id)
                    : [...prev, item.id]
                ))}
                onDeleted={(id) => void removeCase(id)}
                onSaved={() => void refreshProject()}
                onStatus={(id, status) => setStatuses((prev) => ({ ...prev, [id]: status }))}
              />
            ))}
          </div>
        </div>
      )}

      <RevisionDialog
        open={revisionOpen}
        onClose={() => setRevisionOpen(false)}
        projectId={projectId}
        testCases={cases}
        endpoints={endpoints}
        collections={collections}
        briefs={scopes.data || []}
        threads={threads.data || []}
        unsavedCount={unsavedCount}
        onCreated={afterRevision}
      />
    </PageShell>
  );
}
