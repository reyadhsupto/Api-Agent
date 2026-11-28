'use client';

import React, { useState } from 'react';

import Icon from '@/components/ui/Icon';
import { Badge, Button, Card, Checkbox, Input, Notice, Select } from '@/components/ui/primitives';
import { createRun, deleteRun, updateRun } from '@/lib/runs';
import type { TestRun } from '@/types/api';

/**
 * Render the named-run manager for the project.
 *
 * A run stores an ordered selection of saved case IDs. Loading one restores the
 * batch selection, and running it later resolves each ID to the case as saved
 * at that moment, so edits to a case carry into future runs.
 *
 * @param props - Project, runs, current selection, and change hooks.
 * @returns Run manager card.
 */
export default function TestRunManager({
  projectId,
  runs,
  selectedIds,
  loadedRunId,
  onLoad,
  onChanged,
}: {
  projectId: string;
  runs: TestRun[];
  selectedIds: string[];
  loadedRunId: string | null;
  onLoad: (runId: string | null) => void;
  onChanged: () => Promise<void> | void;
}) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const chosen = runs.find((item) => item.id === loadedRunId) || null;

  /**
   * Create a run, or replace the loaded run's name and membership.
   */
  async function save(): Promise<void> {
    const title = (name.trim() || chosen?.name || '').trim();
    if (!title) {
      setError('Give the run a name first.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = chosen
        ? await updateRun(projectId, chosen.id, title, selectedIds)
        : await createRun(projectId, title, selectedIds);
      setName('');
      setConfirmDelete(false);
      onLoad(saved.id);
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the run');
    } finally {
      setBusy(false);
    }
  }

  /**
   * Delete the loaded run. Case records are left untouched.
   */
  async function remove(): Promise<void> {
    if (!chosen) return;
    setBusy(true);
    setError(null);
    try {
      await deleteRun(projectId, chosen.id);
      onLoad(null);
      setConfirmDelete(false);
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the run');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <Icon name="layers" size={13} className="text-accent" />
        <h3 className="text-[12px] font-bold text-text">Suites and reusable runs</h3>
        <Badge tone="neutral" dot={false}>{String(runs.length)}</Badge>
        <span className="ml-auto text-[9.5px] text-text-mute">
          {String(selectedIds.length) + ' case(s) selected'}
        </span>
      </div>

      {error ? <div className="mt-1.5"><Notice tone="bad">{error}</Notice></div> : null}

      <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-[1.4fr_1.4fr_auto]">
        <Select
          value={loadedRunId || ''}
          aria-label="Load a saved run"
          className="h-8"
          onChange={(event) => {
            onLoad(event.target.value || null);
            setConfirmDelete(false);
          }}
        >
          <option value="">No saved run loaded</option>
          {runs.map((run) => (
            <option key={run.id} value={run.id}>
              {run.name + ' (' + String((run.case_ids || []).length) + ')'}
            </option>
          ))}
        </Select>

        <Input
          value={name}
          aria-label="Run name"
          placeholder={chosen ? 'New name for the loaded run' : 'Name this run'}
          className="h-8"
          onChange={(event) => setName(event.target.value)}
        />

        <Button
          small
          tone="primary"
          icon="save"
          className="h-8"
          disabled={busy || selectedIds.length === 0 || (!name.trim() && !chosen)}
          onClick={() => void save()}
        >
          {chosen ? 'Update run' : 'Save run'}
        </Button>
      </div>

      {chosen ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded border border-line-soft bg-panel-alt px-2 py-1.5">
          <span className="text-[10.5px] text-text-dim">
            {'Loaded: ' + chosen.name + ' - ' + String((chosen.case_ids || []).length) + ' case(s)'}
          </span>
          <label className="ml-auto flex cursor-pointer items-center gap-1 text-[10px] text-text-mute">
            <Checkbox
              checked={confirmDelete}
              aria-label="Confirm run delete"
              onChange={() => setConfirmDelete(!confirmDelete)}
            />
            Confirm delete
          </label>
          <Button small tone="danger" disabled={busy || !confirmDelete} onClick={() => void remove()}>
            Delete run
          </Button>
        </div>
      ) : (
        <p className="mt-1.5 text-[10px] text-text-mute">
          Load a run to see its cases selected.
        </p>
      )}
    </Card>
  );
}
