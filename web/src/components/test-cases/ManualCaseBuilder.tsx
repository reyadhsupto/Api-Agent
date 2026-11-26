'use client';

import React, { useState } from 'react';

import Icon from '@/components/ui/Icon';
import {
  Button, Card, Input, MethodBadge, Notice, Select,
} from '@/components/ui/primitives';
import { buildManualCase } from '@/lib/manualcase';
import { saveCases } from '@/lib/testcases';
import type { SavedRequest } from '@/types/api';

/**
 * Render the manual case builder.
 *
 * Two shapes are supported: a single case copied from one saved request, and an
 * ordered flow copied from several. A manual case is authored by hand rather
 * than generated, so it can be tuned without spending a model call.
 *
 * @param props - Project, saved requests, and the created hook.
 * @returns Manual builder card.
 */
export default function ManualCaseBuilder({
  projectId,
  endpoints,
  onCreated,
}: {
  projectId: string;
  endpoints: SavedRequest[];
  onCreated: () => Promise<void> | void;
}) {
  const [mode, setMode] = useState<'single' | 'flow'>('single');
  const [requestId, setRequestId] = useState('');
  const [flowOrder, setFlowOrder] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const byId = new Map(endpoints.map((item) => [item.id, item]));
  const remaining = endpoints.filter((item) => !flowOrder.includes(item.id));

  /**
   * Move one entry inside the flow order.
   *
   * @param index - Current position.
   * @param step - Negative for earlier, positive for later.
   */
  function move(index: number, step: number): void {
    const next = [...flowOrder];
    const target = index + step;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setFlowOrder(next);
  }

  /**
   * Persist the composed case and report success upward.
   */
  async function create(): Promise<void> {
    const chosen = mode === 'single'
      ? endpoints.filter((item) => item.id === requestId)
      : flowOrder.map((id) => byId.get(id)).filter((item): item is SavedRequest => Boolean(item));
    if (chosen.length === 0) {
      setError('Choose at least one saved request.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await saveCases(projectId, [buildManualCase(chosen, name, mode === 'flow')]);
      setName('');
      setFlowOrder([]);
      if (mode === 'single') setRequestId('');
      await onCreated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create the case');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <Icon name="plus" size={13} className="text-accent" />
        <h3 className="text-[12px] font-bold text-text">Add manual test</h3>
        <span className="ml-auto flex gap-1">
          <Button
            small
            tone={mode === 'single' ? 'secondary' : 'ghost'}
            aria-pressed={mode === 'single'}
            onClick={() => setMode('single')}
          >
            Single test
          </Button>
          <Button
            small
            tone={mode === 'flow' ? 'secondary' : 'ghost'}
            aria-pressed={mode === 'flow'}
            onClick={() => setMode('flow')}
          >
            Flow
          </Button>
        </span>
      </div>

      {error ? <div className="mt-1.5"><Notice tone="bad">{error}</Notice></div> : null}

      {endpoints.length === 0 ? (
        <p className="mt-1.5 text-[11px] text-text-mute">
          Save a request in API Workspace first.
        </p>
      ) : null}

      {mode === 'single' && endpoints.length > 0 ? (
        <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-[1.4fr_1.4fr_auto]">
          <Select
            value={requestId}
            aria-label="Saved request"
            className="h-8"
            onChange={(event) => setRequestId(event.target.value)}
          >
            <option value="">Choose a request</option>
            {endpoints.map((item) => (
              <option key={item.id} value={item.id}>
                {(item.method || 'GET') + ' - ' + (item.name || item.url)}
              </option>
            ))}
          </Select>
          <Input
            value={name}
            aria-label="Case name"
            className="h-8"
            placeholder="Defaults to the request name"
            onChange={(event) => setName(event.target.value)}
          />
          <Button small icon="plus" disabled={busy || !requestId} onClick={() => void create()}>
            {busy ? 'Adding' : 'Add case'}
          </Button>
        </div>
      ) : null}

      {mode === 'flow' && endpoints.length > 0 ? (
        <div className="mt-2 flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Select
              value=""
              aria-label="Add step"
              className="h-8 min-w-[9rem]"
              onChange={(event) => {
                const id = event.target.value;
                if (id) setFlowOrder((previous) => [...previous, id]);
              }}
            >
              <option value="">Add a step</option>
              {remaining.map((item) => (
                <option key={item.id} value={item.id}>
                  {(item.method || 'GET') + ' - ' + (item.name || item.url)}
                </option>
              ))}
            </Select>
            <Input
              value={name}
              aria-label="Flow name"
              className="h-8"
              placeholder="Defaults to Manual flow"
              onChange={(event) => setName(event.target.value)}
            />
            <Button
              small
              icon="plus"
              disabled={busy || flowOrder.length === 0}
              onClick={() => void create()}
            >
              {busy ? 'Adding' : 'Add flow'}
            </Button>
          </div>

          <div className="flex flex-col gap-1">
            {flowOrder.length === 0 ? (
              <p className="text-[10.5px] text-text-mute">
                No steps yet. Add saved requests in the order they should run.
              </p>
            ) : null}
            {flowOrder.map((id, index) => {
              const item = byId.get(id);
              return (
                <div
                  key={id}
                  className="flex flex-wrap items-center gap-1.5 rounded border border-line bg-panel-alt px-1.5 py-1"
                >
                  <span className="w-4 shrink-0 text-center font-mono text-[9.5px] text-text-mute">
                    {String(index + 1)}
                  </span>
                  <MethodBadge method={item?.method} />
                  <span className="min-w-0 flex-1 truncate text-[11px] text-text">
                    {item?.name || item?.url || id}
                  </span>
                  <Button
                    small
                    onClick={() => move(index, -1)}
                    disabled={index === 0}
                    aria-label="Move step earlier"
                  >
                    Up
                  </Button>
                  <Button
                    small
                    onClick={() => move(index, 1)}
                    disabled={index === flowOrder.length - 1}
                    aria-label="Move step later"
                  >
                    Down
                  </Button>
                  <Button
                    small
                    tone="danger"
                    onClick={() => setFlowOrder((previous) => previous.filter((entry) => entry !== id))}
                  >
                    Remove
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
