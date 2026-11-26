'use client';

import React, { useEffect, useState } from 'react';

import PageShell, { PageHeader } from '@/components/layout/PageShell';
import ActivityDetail from '@/components/activity/ActivityDetail';
import {
  Badge, Button, Card, EmptyState, Modal, Notice, Select, Spinner, cx,
} from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';
import { api } from '@/lib/api';
import { formatTimestamp, prettyPayload } from '@/lib/format';

/** The two history streams the backend records. */
type Stream = 'generation' | 'knowledge';

/** One paged list response, normalized across both routes. */
interface Page {
  rows: Array<Record<string, unknown>>;
  total: number;
}

/**
 * Normalize a paged list body from either activity route.
 *
 * @param payload - Decoded response body.
 * @param stream - Which route produced the body.
 * @returns Rows and the true total, or empty values when the body is unusable.
 */
function toPage(payload: unknown, stream: Stream): Page {
  if (!payload || typeof payload !== 'object') return { rows: [], total: 0 };
  const record = payload as Record<string, unknown>;
  const key = stream === 'generation' ? 'activities' : 'events';
  const rows = Array.isArray(record[key]) ? (record[key] as Array<Record<string, unknown>>) : [];
  return { rows, total: Number(record.total ?? rows.length) };
}

/**
 * Render the Activity surface: paged generation and knowledge history.
 *
 * @returns Activity page element.
 */
export default function ActivityPage() {
  const { project } = useProject();
  const projectId = project?.id || '';

  const [stream, setStream] = useState<Stream>('generation');
  const [pageSize, setPageSize] = useState(25);
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);

  // Load one page. Offset is clamped when the history shrinks under us.
  useEffect(() => {
    if (!projectId) {
      setRows([]);
      setTotal(0);
      return undefined;
    }
    let live = true;
    setLoading(true);
    setError(null);
    const path = stream === 'generation'
      ? '/api/v1/projects/' + projectId + '/generation-activity'
      : '/api/v1/projects/' + projectId + '/knowledge/activity';
    const query = '?limit=' + String(pageSize) + '&offset=' + String(offset);
    api.get<unknown>(path + query).then(
      (payload) => {
        if (!live) return;
        const page = toPage(payload, stream);
        if (offset > 0 && offset >= page.total) {
          setOffset(Math.max(0, Math.floor((page.total - 1) / pageSize) * pageSize));
          return;
        }
        setRows(page.rows);
        setTotal(page.total);
      },
      (caught: unknown) => {
        if (live) {
          setError(caught instanceof Error ? caught.message : 'Could not load activity');
        }
      },
    ).finally(() => {
      if (live) setLoading(false);
    });
    return () => {
      live = false;
    };
  }, [projectId, stream, pageSize, offset]);

  const page = Math.floor(offset / pageSize) + 1;
  const pages = Math.max(1, Math.ceil(total / pageSize));

  /**
   * Open one record, loading the fuller payload for knowledge events.
   *
   * @param row - Selected activity row.
   */
  async function openDetail(row: Record<string, unknown>): Promise<void> {
    if (stream === 'generation') {
      setDetail(row);
      return;
    }
    try {
      const payload = await api.get<Record<string, unknown>>(
        '/api/v1/projects/' + projectId + '/knowledge/activity/' + String(row.id),
      );
      setDetail(payload);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load the detail');
    }
  }

  /** Human labels for the Hub events the backend records. */
  const KNOWLEDGE_EVENT_LABEL: Record<string, string> = {
    extracted: 'Knowledge extracted',
    extraction_failed: 'Extraction failed',
    hub_page_created: 'Hub page created',
    hub_feature_services_updated: 'Feature services updated',
    hub_draft_prepared: 'Hub draft prepared',
    hub_draft_failed: 'Hub draft failed',
    hub_update_saved: 'Hub versions saved',
    hub_version_restored: 'Hub version restored',
  };

  /**
   * Derive a knowledge outcome from the recorded payload.
   *
   * A draft event is written before the model call finishes, so failure has to
   * be read from the payload error or the failed event type rather than assumed.
   *
   * @param row - Knowledge activity row.
   * @returns failed, recorded, or completed.
   */
  function knowledgeStatus(row: Record<string, unknown>): string {
    const summary = (row.summary || {}) as Record<string, unknown>;
    const eventType = String(row.event_type || '');
    if (summary.error || eventType.endsWith('_failed')) return 'failed';
    if (eventType === 'extracted' || eventType === 'hub_draft_prepared') return 'recorded';
    return 'completed';
  }

  /**
   * Reduce one knowledge event to a table label.
   *
   * @param row - Knowledge activity row.
   * @returns Event label with page or proposal counts.
   */
  function knowledgeLabel(row: Record<string, unknown>): string {
    const summary = (row.summary || {}) as Record<string, unknown>;
    const eventType = String(row.event_type || 'event');
    const base = KNOWLEDGE_EVENT_LABEL[eventType] || eventType.replace(/_/g, ' ');
    const pages = Number(summary.page_count || 0);
    const proposals = Number(summary.proposal_count || 0);
    const rawNames = Array.isArray(summary.page_names) ? (summary.page_names as unknown[]) : [];
    const names = rawNames.map(String).slice(0, 3);
    const parts: string[] = [];
    if (names.length > 0) {
      parts.push(names.join(', ') + (rawNames.length > 3 ? ' +' + String(rawNames.length - 3) : ''));
    } else if (pages > 0) {
      parts.push(String(pages) + ' page' + (pages === 1 ? '' : 's'));
    }
    if (proposals > 0) parts.push(String(proposals) + ' proposal' + (proposals === 1 ? '' : 's'));
    const suffix = parts.length > 0 ? ' - ' + parts.join(', ') : '';
    const source = row.source_type ? ' [' + String(row.source_type) + ']' : '';
    return base + suffix + source;
  }

  /**
   * Describe a generation row.
   *
   * @param row - Generation activity row.
   * @returns Action label and status.
   */
  function generationLabel(row: Record<string, unknown>): { label: string; status: string } {
    const label = String(row.mode || row.activity_type || 'generation');
    const status = String(row.status || (row.superseded_by_activity_id ? 'superseded' : 'recorded'));
    return { label, status };
  }

  if (!project) {
    return (
      <PageShell>
        <PageHeader title="Activity" description="Generation and knowledge extraction history." />
        <EmptyState title="No project selected" body="Pick a project in the rail to inspect its history." />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title="Activity"
        description="Every generation and knowledge extraction, with the payload behind it."
        actions={
          <Badge tone="neutral">
            {String(total) + (total === 1 ? ' record' : ' records')}
          </Badge>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded border border-line">
          {(['generation', 'knowledge'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => { setStream(option); setOffset(0); }}
              className={cx(
                'px-2.5 py-1 text-[10.5px] font-semibold',
                stream === option
                  ? 'bg-accent-soft text-accent'
                  : 'bg-panel text-text-dim hover:bg-hover',
              )}
            >
              {option === 'generation' ? 'Generation' : 'Knowledge extraction'}
            </button>
          ))}
        </div>

        <Select
          value={String(pageSize)}
          aria-label="Page size"
          className="h-7 w-20 text-[10.5px]"
          onChange={(event) => {
            setPageSize(Number(event.target.value));
            setOffset(0);
          }}
        >
          {[10, 25, 50, 100].map((size) => (
            <option key={size} value={size}>{String(size)}</option>
          ))}
        </Select>

        <span className="ml-auto flex items-center gap-1">
          <Button small disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - pageSize))}>
            Previous
          </Button>
          <span className="px-1 font-mono text-[10px] text-text-mute">
            {'Page ' + String(page) + ' of ' + String(pages)}
          </span>
          <Button small disabled={offset + pageSize >= total || loading} onClick={() => setOffset(offset + pageSize)}>
            Next
          </Button>
        </span>
      </div>

      {error ? <div className="mb-3"><Notice tone="bad">{error}</Notice></div> : null}

      <Card className="divide-y divide-line-soft p-0">
        {loading ? <div className="p-3"><Spinner label="Loading activity" /></div> : null}

        {!loading && rows.length === 0 ? (
          <div className="p-3">
            <p className="text-[11.5px] text-text-mute">No records yet.</p>
          </div>
        ) : null}

        {!loading && rows.map((row) => {
          const created = String(row.created_at || '');
          const status = stream === 'generation' ? generationLabel(row).status : knowledgeStatus(row);
          const label = stream === 'generation' ? generationLabel(row).label : knowledgeLabel(row);
          const source = stream === 'generation'
            ? String(row.project_name || row.project_id || '')
            : String(row.source_name || '');

          return (
            <button
              key={String(row.id)}
              type="button"
              onClick={() => void openDetail(row)}
              className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-hover"
            >
              <span className="font-mono text-[9.5px] text-text-mute">
                {formatTimestamp(created)}
              </span>
              <Badge tone={status === 'failed' ? 'bad' : status === 'superseded' ? 'warn' : 'ok'}>
                {status}
              </Badge>
              <span className="min-w-0 flex-1 truncate text-[11px] text-text">{label}</span>
              {source ? (
                <span className="hidden shrink-0 truncate text-[9.5px] text-text-mute sm:block">
                  {source}
                </span>
              ) : null}
              <span className="shrink-0 text-[9.5px] font-semibold text-accent">View</span>
            </button>
          );
        })}
      </Card>

      <Modal open={Boolean(detail)} title="Activity detail" onClose={() => setDetail(null)} wide>
        {detail ? <ActivityDetail stream={stream} row={detail} /> : null}
      </Modal>
    </PageShell>
  );
}
