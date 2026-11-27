'use client';

import React, { useState } from 'react';

import AssertionsEditor, { countEnabled, emptyAssertions } from '@/components/ui/AssertionsEditor';
import Icon from '@/components/ui/Icon';
import {
  Badge, Button, Card, Checkbox, Input, Menu, MethodBadge, Modal, Notice, Spinner, StatusPill,
  Tabs, Textarea, cx,
} from '@/components/ui/primitives';
import { formatLatency, prettyPayload, truncate } from '@/lib/format';
import { api } from '@/lib/api';
import { deleteCase, executeCase, recordManualOutcome, saveCases } from '@/lib/testcases';
import type { Assertions, ExecutionResult, TestCase } from '@/types/api';

/** Presentation tone for a generated case type. */
function typeTone(type: string): 'ok' | 'bad' | 'warn' | 'info' | 'accent' {
  const value = type.toLowerCase();
  if (value === 'positive') return 'ok';
  if (value === 'negative') return 'bad';
  if (value === 'edge') return 'warn';
  if (value === 'race') return 'accent';
  return 'info';
}

/**
 * Derive a flaky signal from recent executions.
 *
 * Three or more failures in the last ten runs is the threshold the Streamlit
 * card used, kept here so both surfaces agree.
 */
function isFlaky(executions: ExecutionResult[] | undefined): boolean {
  if (!executions?.length) return false;
  const recent = executions.slice(-10);
  return recent.filter((item) => item.status !== 'passed').length >= 3;
}

export interface TestCaseCardProps {
  /** Case being rendered. */
  testCase: TestCase;
  /** Owning project, used for the routes below. */
  projectId: string;
  /** Batch-run selection. */
  selected: boolean;
  /** Whether the detail tabs are visible. */
  expanded: boolean;
  /** Toggle batch-run selection. */
  onSelect: (next: boolean) => void;
  /** Report a new execution status to the parent. */
  onStatus?: (id: string, status: string) => void;
  /** Latest persisted outcome, used for the left-edge result accent. */
  latestStatus?: string;
  /** Toggle the detail tabs. */
  onToggle: () => void;
  /** Remove the case from the workspace after a successful delete. */
  onDeleted: (id: string) => void;
  /** Called after a save so the parent can reload the project. */
  onSaved: () => void;
}

/**
 * Render one test case with assertions, request, result, and history tabs.
 */
export default function TestCaseCard({
  testCase, projectId, selected, expanded, onSelect, onToggle, onDeleted, onSaved, onStatus,
  latestStatus,
}: TestCaseCardProps) {
  const [tab, setTab] = useState('assertions');
  const [name, setName] = useState(testCase.name);
  const [description, setDescription] = useState(testCase.description || '');
  const [assertions, setAssertions] = useState<Assertions>(
    testCase.assertions || emptyAssertions(),
  );
  const [requestText, setRequestText] = useState(
    JSON.stringify(testCase.request || {}, null, 2),
  );
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [history, setHistory] = useState<ExecutionResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [manualBusy, setManualBusy] = useState(false);
  const [manualDialogOpen, setManualDialogOpen] = useState(false);
  const [manualOutcome, setManualOutcome] = useState<'passed' | 'failed' | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saved' | 'dirty'>('idle');

  const flag = isFlaky(history || undefined);
  const isGeneral = testCase.case_kind === 'general';
  const isFlow = Boolean(testCase.is_flow || testCase.steps);
  const visibleLatestStatus = latestStatus || (isGeneral ? testCase.manual_status : undefined);
  const orderedFlowSteps = [...(testCase.steps || [])]
    .map((step, sourceIndex) => ({ step, sourceIndex }))
    .sort((left, right) => {
      const leftOrder = Number(left.step.step_order);
      const rightOrder = Number(right.step.step_order);
      const safeLeft = Number.isFinite(leftOrder) ? leftOrder : left.sourceIndex;
      const safeRight = Number.isFinite(rightOrder) ? rightOrder : right.sourceIndex;
      return safeLeft - safeRight || left.sourceIndex - right.sourceIndex;
    })
    .map(({ step }) => step);
  const manualSteps = (testCase.manual_steps || []).map((step) => String(step).trim()).filter(Boolean);
  const processStepCount = isGeneral ? manualSteps.length : isFlow ? orderedFlowSteps.length : 0;

  /** Mark the card dirty after any local edit. */
  const touch = () => setSaveState('dirty');

  /** Run the saved case through the backend executor. */
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await executeCase(projectId, testCase);
      setResult(response);
      onStatus?.(testCase.id, response.status);
      setTab('result');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Execution failed');
    } finally {
      setBusy(false);
    }
  };

  /** Persist name, description, assertions, and request edits. */
  const save = async () => {
    setBusy(true);
    setError(null);
    let request = testCase.request;
    if (!isFlow && !isGeneral) {
      try {
        request = JSON.parse(requestText);
      } catch {
        setError('Request must be valid JSON before saving.');
        setBusy(false);
        return;
      }
    }
    try {
      await saveCases(projectId, [{
        ...testCase,
        name: name.trim() || 'Untitled case',
        description,
        assertions,
        request,
      }]);
      setSaveState('saved');
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the case');
    } finally {
      setBusy(false);
    }
  };

  /** Load execution history the first time the tab is opened. */
  const loadHistory = async () => {
    setTab('history');
    if (history) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.get<{ executions: ExecutionResult[] }>(
        '/api/v1/projects/' + projectId + '/test-cases/' + testCase.id + '/history?limit=50',
      );
      setHistory(data.executions || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load history');
    } finally {
      setBusy(false);
    }
  };

  /** Record a manual outcome for a requirements-only general case. */
  const recordManual = async (status: 'passed' | 'failed') => {
    setManualBusy(true);
    setError(null);
    try {
      const response = await recordManualOutcome(projectId, testCase.id, status, reason.trim());
      setResult(response);
      onStatus?.(testCase.id, response.status);
      setReason('');
      setManualOutcome(null);
      setManualDialogOpen(false);
      setHistory(null);
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not record the outcome');
    } finally {
      setManualBusy(false);
    }
  };

  /** Delete the case and let the parent drop it from view. */
  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteCase(projectId, testCase.id);
      onDeleted(testCase.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the case');
      setBusy(false);
    }
  };

  return (
    <>
    <Card className={cx(
      'relative overflow-hidden',
    )}>
      <span
        aria-label={visibleLatestStatus ? 'Latest execution: ' + visibleLatestStatus : undefined}
        title={visibleLatestStatus ? 'Latest execution: ' + visibleLatestStatus : undefined}
        className={cx(
          'absolute inset-y-0 left-0 z-10 w-1',
          visibleLatestStatus === 'passed' ? 'bg-ok' :
            visibleLatestStatus === 'failed' ? 'bg-bad' :
              visibleLatestStatus === 'error' ? 'bg-warn' : 'bg-transparent',
        )}
      />
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <Checkbox
          checked={selected}
          aria-label={'Select ' + testCase.name + ' for a batch run'}
          onChange={(event) => onSelect(event.target.checked)}
        />
        <button
          type="button"
          onClick={onToggle}
          className="inline-flex min-w-0 items-center gap-1.5 text-[12.5px] font-bold text-text"
        >
          <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={13} />
          <span className="truncate">{name || 'Untitled case'}</span>
        </button>
        <Badge tone={typeTone(testCase.type)}>{testCase.type}</Badge>
        {isFlow ? <Badge tone="info">flow</Badge> : null}
        {isGeneral ? <Badge tone="warn">general</Badge> : null}
        {flag ? <Badge tone="warn">flaky</Badge> : null}
        {saveState === 'dirty' ? <Badge tone="neutral">unsaved</Badge> : null}
        <span className="ml-auto flex items-center gap-1.5">
          {visibleLatestStatus ? (
            <span className="sr-only">Latest execution: {visibleLatestStatus}</span>
          ) : null}
          {result ? <StatusPill status={result.response_status ?? null} /> : null}
          {result?.latency_ms ? <Badge tone="neutral">{formatLatency(result.latency_ms)}</Badge> : null}
          {isGeneral ? (
            <>
              <Button
                small
                tone="success"
                icon="check"
                disabled={busy || manualBusy}
                onClick={() => {
                  setError(null);
                  setManualOutcome('passed');
                  setManualDialogOpen(true);
                }}
              >
                Pass
              </Button>
              <Button
                small
                tone="dangerSolid"
                icon="close"
                disabled={busy || manualBusy}
                onClick={() => {
                  setError(null);
                  setManualOutcome('failed');
                  setManualDialogOpen(true);
                }}
              >
                Fail
              </Button>
            </>
          ) : (
            <Button small tone="primary" icon="play" disabled={busy} onClick={() => void run()}>
              Run
            </Button>
          )}
          <Menu
            label={'Actions for ' + testCase.name}
            items={[
              { label: 'Save changes', icon: 'save', onSelect: () => void save() },
              { label: 'Delete case', icon: 'trash', danger: true, onSelect: () => void remove() },
            ]}
          />
        </span>
      </div>

      {testCase.description ? (
        <div className="mx-3 mb-2 rounded-md border border-line-soft bg-panel-alt px-2.5 py-2">
          <p className="mb-0.5 text-[9px] font-bold uppercase tracking-[0.08em] text-text-mute">Overview</p>
          <p className="text-[11px] leading-relaxed text-text-dim">{testCase.description}</p>
        </div>
      ) : null}

      {error ? (
        <div className="px-3 pb-2">
          <Notice tone="bad">{error}</Notice>
        </div>
      ) : null}

      {expanded && processStepCount > 0 ? (
        <section className="mx-3 mb-2 overflow-hidden rounded-lg border border-line-strong bg-panel-alt">
          <header className="flex items-center justify-between gap-2 border-b border-line-soft px-3 py-2">
            <div className="min-w-0">
              <h3 className="text-[10.5px] font-bold uppercase tracking-[0.08em] text-text">Test process</h3>
              <p className="mt-0.5 text-[9.5px] text-text-mute">
                {'Follow these steps in order: 1 through ' + String(processStepCount)}
              </p>
            </div>
            <Badge tone="neutral" dot={false}>
              {String(processStepCount) + (processStepCount === 1 ? ' step' : ' steps')}
            </Badge>
          </header>
          <ol className="divide-y divide-line-soft">
            {isGeneral ? manualSteps.map((step, index) => (
              <li key={String(index)} className="grid grid-cols-[1.6rem_minmax(0,1fr)] gap-2 px-3 py-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-line-strong bg-panel text-[10px] font-bold text-accent">
                  {index + 1}
                </span>
                <p className="min-w-0 self-center whitespace-pre-wrap text-[11.5px] leading-relaxed text-text">
                  {step}
                </p>
              </li>
            )) : orderedFlowSteps.map((step, index) => {
              const endpoint = step.endpoint || {};
              const endpointName = String(endpoint.name || '').trim();
              const method = String(endpoint.method || '').trim().toUpperCase();
              const url = String(endpoint.url || '').trim();
              const endpointLabel = [method, url].filter(Boolean).join(' ');
              const instruction = String(
                step.description || endpointName || endpointLabel || 'Follow the request configured for this step.',
              );
              return (
                <li key={String(step.step_id || step.step_order || index)} className="grid grid-cols-[1.6rem_minmax(0,1fr)] gap-2 px-3 py-2.5">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full border border-line-strong bg-panel text-[10px] font-bold text-accent">
                    {index + 1}
                  </span>
                  <div className="min-w-0 self-center">
                    <p className="whitespace-pre-wrap text-[11.5px] font-medium leading-relaxed text-text">
                      {instruction}
                    </p>
                    {endpointLabel ? (
                      <p className="mt-0.5 aa-wrap-anywhere font-mono text-[9.5px] text-text-mute">
                        {endpointLabel}
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      {expanded ? (
        <div className="border-t border-line px-3 py-2">
          <Tabs
            value={tab}
            onChange={(next) => {
              if (next === 'history') void loadHistory();
              else setTab(next);
            }}
            tabs={[
              { id: 'details', label: 'Details' },
              { id: 'assertions', label: 'Assertions', badge: countEnabled(assertions) },
              { id: 'request', label: 'Request' },
              { id: 'result', label: 'Result', badge: result?.status },
              { id: 'history', label: 'History', badge: history?.length },
            ]}
          />

          <div className="pt-2.5">
            {tab === 'details' ? (
              <div className="grid gap-2.5 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-text-mute">
                  Case title
                  <Input
                    value={name}
                    aria-label="Case title"
                    placeholder="Case title"
                    onChange={(event) => { setName(event.target.value); touch(); }}
                  />
                </label>
                <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wide text-text-mute sm:col-span-2">
                  Overview
                  <Textarea
                    rows={3}
                    value={description}
                    aria-label="Case overview"
                    placeholder="Describe the purpose of this case"
                    onChange={(event) => { setDescription(event.target.value); touch(); }}
                  />
                </label>
              </div>
            ) : null}

            {tab === 'assertions' ? (
              <div className="flex flex-col gap-2.5">
                {isGeneral ? (
                  <div className="flex flex-col gap-2 rounded-md border border-line bg-panel-alt p-2.5">
                    <p className="text-[11px] text-text-dim">
                      Run opens a prompt to record this scenario as passed or failed.
                    </p>
                  </div>
                ) : null}

                <AssertionsEditor
                  value={assertions}
                  onChange={(next) => { setAssertions(next); touch(); }}
                  hint={isGeneral ? 'not run for general scenarios' : 'run with this case'}
                />
              </div>
            ) : null}

            {tab === 'request' ? (
              <div className="flex flex-col gap-1.5">
                <p className="text-[10.5px] text-text-mute">
                  {isFlow
                    ? 'Flows run their stored steps in order. Steps are read-only here.'
                    : 'Edit the request JSON, then save the case to keep the change.'}
                </p>
                {isFlow ? (
                  <pre className="aa-scroll aa-wrap-anywhere max-h-[22rem] overflow-auto rounded-md border border-code-border bg-code-bg p-3 font-mono text-[11px] text-text">
                    {prettyPayload(testCase.steps)}
                  </pre>
                ) : (
                  <Textarea
                    rows={10}
                    spellCheck={false}
                    aria-label="Request JSON"
                    className="font-mono text-[11px]"
                    value={requestText}
                    onChange={(event) => { setRequestText(event.target.value); touch(); }}
                  />
                )}
              </div>
            ) : null}

            {tab === 'result' ? (
              !result ? (
                <p className="text-[11px] text-text-mute">Run this case to see its response.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={result.status === 'passed' ? 'ok' : result.status === 'failed' ? 'bad' : 'warn'}>
                      {result.status}
                    </Badge>
                    <MethodBadge method={result.request_method} />
                    <StatusPill status={result.response_status ?? null} />
                    {result.latency_ms ? <Badge tone="neutral">{formatLatency(result.latency_ms)}</Badge> : null}
                  </div>

                  <p className="aa-wrap-anywhere font-mono text-[10.5px] text-text-dim">
                    {result.request_url || '(no request URL recorded)'}
                  </p>

                  {result.assertion_detail ? (
                    <p className="aa-wrap-anywhere text-[11px] text-text-dim">{result.assertion_detail}</p>
                  ) : null}

                  {result.request_body ? (
                    <details className="rounded-md border border-line bg-panel-alt px-2 py-1.5">
                      <summary className="cursor-pointer text-[11px] font-semibold text-text-dim">Request body</summary>
                      <pre className="aa-scroll aa-wrap-anywhere mt-1 max-h-[16rem] overflow-auto font-mono text-[10.5px] text-text">
                        {prettyPayload(result.request_body)}
                      </pre>
                    </details>
                  ) : null}

                  {result.response_body ? (
                    <details className="rounded-md border border-line bg-panel-alt px-2 py-1.5" open>
                      <summary className="cursor-pointer text-[11px] font-semibold text-text-dim">Response body</summary>
                      <pre className="aa-scroll aa-wrap-anywhere mt-1 max-h-[20rem] overflow-auto font-mono text-[10.5px] text-text">
                        {prettyPayload(result.response_body)}
                      </pre>
                    </details>
                  ) : null}
                </div>
              )
            ) : null}

            {tab === 'history' ? (
              <div className="flex flex-col gap-2">
                {busy && history === null ? <Spinner label="Loading execution history" /> : null}
                {history !== null && history.length === 0 ? (
                  <p className="text-[11px] text-text-mute">This case has not been executed yet.</p>
                ) : null}
                {flag ? (
                  <Notice tone="warn">
                    Flaky signal: three or more of the last ten executions did not pass.
                  </Notice>
                ) : null}
                {history?.map((item, index) => (
                  <details
                    key={String(item.id || index)}
                    className="rounded-md border border-line bg-panel-alt px-2 py-1.5"
                  >
                    <summary className="flex cursor-pointer flex-wrap items-center gap-1.5 text-[11px] text-text-dim">
                      <span className="font-mono text-[10px] text-text-mute">#{String(history.length - index)}</span>
                      <Badge tone={item.status === 'passed' ? 'ok' : item.status === 'failed' ? 'bad' : 'warn'}>
                        {item.status}
                      </Badge>
                      <span>{formatLatency(item.latency_ms)}</span>
                      <span className="ml-auto text-text-mute">
                        {truncate(String(item.created_at || item.executed_at || ''), 22)}
                      </span>
                    </summary>
                    <p className="aa-wrap-anywhere mt-1 text-[11px] text-text-dim">
                      {item.assertion_detail || 'No assertion detail recorded.'}
                    </p>
                    <pre className="aa-scroll aa-wrap-anywhere mt-1 max-h-[14rem] overflow-auto font-mono text-[10px] text-text-mute">
                      {prettyPayload(item)}
                    </pre>
                  </details>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </Card>
    <Modal
      open={manualDialogOpen}
      title="Record manual outcome"
      description={testCase.name}
      onClose={() => {
        if (manualBusy) return;
        setManualDialogOpen(false);
        setManualOutcome(null);
      }}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <Button
            small
            onClick={() => {
              setManualDialogOpen(false);
              setManualOutcome(null);
            }}
            disabled={manualBusy}
          >
            Cancel
          </Button>
          <Button
            small
            tone={manualOutcome === 'failed' ? 'dangerSolid' : 'success'}
            disabled={!manualOutcome || manualBusy}
            onClick={() => { if (manualOutcome) void recordManual(manualOutcome); }}
          >
            {manualBusy ? 'Recording…' : manualOutcome === 'passed' ? 'Confirm pass' : 'Confirm failure'}
          </Button>
        </div>
      )}
    >
      <div className="flex flex-col gap-3">
        <p className="text-[11px] text-text-dim">
          {'Confirm marking this case as ' + (manualOutcome === 'passed' ? 'passed.' : 'failed.')}
        </p>
        {manualOutcome === 'failed' ? (
          <Textarea
            rows={3}
            value={reason}
            aria-label="Optional failure reason"
            placeholder="Failure reason (optional)"
            onChange={(event) => setReason(event.target.value)}
            disabled={manualBusy}
          />
        ) : null}
        {error ? <Notice tone="bad">{error}</Notice> : null}
      </div>
    </Modal>
    </>
  );
}
