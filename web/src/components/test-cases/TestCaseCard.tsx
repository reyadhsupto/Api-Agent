'use client';

import React, { useState } from 'react';

import AssertionsEditor, { countEnabled, emptyAssertions } from '@/components/ui/AssertionsEditor';
import Icon from '@/components/ui/Icon';
import {
  Badge, Button, Card, Checkbox, Input, Menu, MethodBadge, Notice, Spinner, StatusPill,
  Tabs, Textarea,
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
  const [saveState, setSaveState] = useState<'idle' | 'saved' | 'dirty'>('idle');

  const flag = isFlaky(history || undefined);
  const isGeneral = testCase.case_kind === 'general';
  const isFlow = Boolean(testCase.is_flow || testCase.steps);

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
    if (status === 'failed' && !reason.trim()) {
      setError('Add a failure reason before recording a failed outcome.');
      return;
    }
    setManualBusy(true);
    setError(null);
    try {
      const response = await recordManualOutcome(projectId, testCase.id, status, reason.trim());
      setResult(response);
      onStatus?.(testCase.id, response.status);
      setReason('');
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
    <Card className="overflow-hidden">
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
          {result ? <StatusPill status={result.response_status ?? null} /> : null}
          {result?.latency_ms ? <Badge tone="neutral">{formatLatency(result.latency_ms)}</Badge> : null}
          <Button small tone="primary" icon="play" disabled={busy} onClick={() => void run()}>
            Run
          </Button>
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
        <p className="px-3 pb-2 text-[11px] text-text-dim">{testCase.description}</p>
      ) : null}

      {error ? (
        <div className="px-3 pb-2">
          <Notice tone="bad">{error}</Notice>
        </div>
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
              { id: 'assertions', label: 'Assertions', badge: countEnabled(assertions) },
              { id: 'request', label: 'Request' },
              { id: 'result', label: 'Result', badge: result?.status },
              { id: 'history', label: 'History', badge: history?.length },
            ]}
          />

          <div className="pt-2.5">
            {tab === 'assertions' ? (
              <div className="flex flex-col gap-2.5">
                <div className="flex flex-col gap-1.5">
                  <Input
                    value={name}
                    aria-label="Case name"
                    placeholder="Case name"
                    onChange={(event) => { setName(event.target.value); touch(); }}
                  />
                  <Input
                    value={description}
                    aria-label="Case description"
                    placeholder="Description"
                    onChange={(event) => { setDescription(event.target.value); touch(); }}
                  />
                </div>

                {isGeneral ? (
                  <div className="flex flex-col gap-2 rounded-md border border-line bg-panel-alt p-2.5">
                    <p className="text-[11px] text-text-dim">
                      General scenarios are executed by a tester and recorded here.
                    </p>
                    <Input
                      value={reason}
                      aria-label="Failure reason"
                      placeholder="Failure reason, required only when recording a failure"
                      onChange={(event) => setReason(event.target.value)}
                    />
                    <div className="flex items-center gap-1.5">
                      <Button
                        small
                        icon="check"
                        disabled={manualBusy}
                        onClick={() => void recordManual('passed')}
                      >
                        Passed
                      </Button>
                      <Button
                        small
                        tone="danger"
                        icon="close"
                        disabled={manualBusy}
                        onClick={() => void recordManual('failed')}
                      >
                        Failed
                      </Button>
                    </div>
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
  );
}
