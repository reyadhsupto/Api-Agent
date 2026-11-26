'use client';

import React, { useEffect, useMemo, useState } from 'react';

import PageShell, { PageHeader } from '@/components/layout/PageShell';
import AssertionsEditor, { countEnabled, emptyAssertions, flattenAssertions } from '@/components/ui/AssertionsEditor';
import {
  Badge, Button, Card, Checkbox, EmptyState, IconButton, Input, Menu, MethodBadge, Modal,
  Notice, Select, Spinner, StatusPill, Tabs, Textarea, cx,
} from '@/components/ui/primitives';
import { useProject } from '@/context/ProjectContext';
import { ApiError, LLM_TIMEOUT_MS, api, apiDownload } from '@/lib/api';
import { formatBytes, formatLatency, isJsonPayload, prettyPayload, truncate } from '@/lib/format';
import type { ApiRequest, Assertions, Collection, HttpMethod, HttpResult, ParsedCurl, SavedRequest, ValueRow } from '@/types/api';

const METHODS: HttpMethod[] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];
const BODY_TYPES = ['json', 'text', 'xml'] as const;

/** One editable key/value row. */
interface Row {
  key: string;
  value: string;
  description: string;
  enabled: boolean;
}

/** One request editor tab. */
interface Draft {
  tabId: string;
  savedId?: string;
  collectionId?: string;
  name: string;
  method: HttpMethod;
  url: string;
  headers: Row[];
  query: Row[];
  body: string;
  includeBody: boolean;
  bodyType: 'json' | 'text' | 'xml';
  authType: 'none' | 'bearer' | 'basic' | 'apiKey';
  token: string;
  username: string;
  password: string;
  apiKeyHeader: string;
  apiKey: string;
  assertions: Assertions;
  response?: HttpResult;
  baseline: string;
  dirty: boolean;
  busy: boolean;
}

/** Create a unique identifier for drafts, rows, and assertions. */
function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return Math.random().toString(36).slice(2);
}

/** Build a blank key/value row. */
function blankRow(): Row {
  return { key: '', value: '', description: '', enabled: true };
}

/** Convert saved header or query rows into editor rows. */
function toRows(source: ValueRow[] | Record<string, unknown> | undefined): Row[] {
  if (!source) return [blankRow()];
  if (Array.isArray(source)) {
    const rows = source.map((item) => ({
      key: String(item.key ?? ''),
      value: String(item.value ?? ''),
      description: String(item.description ?? ''),
      enabled: item.enabled !== false,
    }));
    return rows.length ? rows : [blankRow()];
  }
  const rows = Object.entries(source).map(([key, value]) => ({
    key: key,
    value: String(value ?? ''),
    description: '',
    enabled: true,
  }));
  return rows.length ? rows : [blankRow()];
}

/** Render a stored body as editable text without losing its formatting. */
function bodyText(body: unknown): string {
  if (body === null || body === undefined) return '';
  if (typeof body === 'string') return body;
  try {
    return JSON.stringify(body, null, 2);
  } catch {
    return String(body);
  }
}

/** Normalise assertions read from storage into the repeatable editor shape. */
function normalizeAssertions(source: Assertions | undefined): Assertions {
  const base = emptyAssertions();
  if (!source) return base;
  (Object.keys(base) as Array<keyof Assertions>).forEach((type) => {
    const group = source[type];
    if (!Array.isArray(group)) return;
    base[type] = group.map((item) => ({
      ...item,
      id: item.id || newId(),
      enabled: item.enabled !== false,
    }));
  });
  return base;
}

/**
 * Reduce the editable draft to the values that define the request.
 *
 * Comparing meaning rather than representation is what lets a saved request
 * reopen as clean while a real edit marks the tab as unsaved.
 */
function signatureOf(draft: Draft): string {
  return JSON.stringify({
    method: draft.method,
    url: draft.url.trim(),
    headers: draft.headers.map((row) => [row.key.trim(), row.key ? row.value : '', row.enabled]),
    query: draft.query.map((row) => [row.key.trim(), row.key ? row.value : '', row.enabled]),
    body: draft.includeBody ? draft.body.trim() : '',
    bodyType: draft.bodyType,
    authType: draft.authType,
    token: draft.token,
    username: draft.username,
    password: draft.password,
    apiKeyHeader: draft.apiKeyHeader,
    apiKey: draft.apiKey,
    assertions: draft.assertions,
  });
}

/** Return enabled rows as a plain mapping. */
function rowsToObject(rows: Row[]): Record<string, string> {
  const result: Record<string, string> = {};
  rows.forEach((row) => {
    const key = row.key.trim();
    if (key && row.enabled && !(key in result)) result[key] = row.value;
  });
  return result;
}

/** Return the authorization header implied by the auth fields, if any. */
function authHeader(draft: Draft): [string, string] | null {
  if (draft.authType === 'bearer' && draft.token.trim()) {
    return ['Authorization', 'Bearer ' + draft.token.trim()];
  }
  if (draft.authType === 'basic' && (draft.username || draft.password)) {
    try {
      return ['Authorization', 'Basic ' + btoa(draft.username + ':' + draft.password)];
    } catch {
      return null;
    }
  }
  if (draft.authType === 'apiKey' && draft.apiKey) {
    return [draft.apiKeyHeader.trim() || 'X-API-Key', draft.apiKey];
  }
  return null;
}

/** Build the JSON payload the backend proxy should send. */
function buildRequest(draft: Draft): ApiRequest {
  const headers = rowsToObject(draft.headers);
  const auth = authHeader(draft);
  if (auth) {
    const existing = Object.keys(headers).find((name) => name.toLowerCase() === auth[0].toLowerCase());
    if (!existing) headers[auth[0]] = auth[1];
  }
  let body: unknown;
  if (draft.includeBody && draft.body.trim()) {
    body = draft.body;
    if (draft.bodyType === 'json') {
      try {
        body = JSON.parse(draft.body);
      } catch {
        body = draft.body;
      }
    }
  }
  return {
    method: draft.method,
    url: draft.url.trim(),
    headers,
    query_params: rowsToObject(draft.query),
    body: (body ?? null) as ApiRequest['body'],
    timeout_seconds: 120,
  };
}

/** Create a draft from a saved request, or a blank one for a new request. */
function newDraft(saved?: SavedRequest, collectionId?: string): Draft {
  const draft: Draft = {
    tabId: newId(),
    savedId: saved?.id,
    collectionId: saved?.collection_id || collectionId,
    name: saved?.name || 'New request',
    method: (saved?.method || 'GET') as HttpMethod,
    url: saved?.url || '',
    headers: toRows(saved?.headers),
    query: toRows(saved?.query_params),
    body: bodyText(saved?.body),
    includeBody: saved ? saved.include_body !== false && saved?.body != null : false,
    bodyType: 'json',
    authType: 'none',
    token: '',
    username: '',
    password: '',
    apiKeyHeader: 'X-API-Key',
    apiKey: '',
    assertions: normalizeAssertions(saved?.assertions),
    response: undefined,
    baseline: '',
    dirty: false,
    busy: false,
  };
  return { ...draft, baseline: signatureOf(draft), dirty: false };
}

/** Render editable key/value rows with per-row enable toggles. */
function RowEditor({
  rows,
  onChange,
  keyPlaceholder,
  valuePlaceholder,
}: {
  rows: Row[];
  onChange: (next: Row[]) => void;
  keyPlaceholder: string;
  valuePlaceholder: string;
}) {
  const patch = (index: number, next: Partial<Row>) => {
    onChange(rows.map((row, position) => (position === index ? { ...row, ...next } : row)));
  };

  return (
    <div className="flex flex-col gap-1.5">
      {rows.map((row, index) => (
        <div
          key={String(index)}
          className="grid grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-1.5"
        >
          <Checkbox
            checked={row.enabled}
            aria-label={'Enable row ' + String(index + 1)}
            onChange={(event) => patch(index, { enabled: event.target.checked })}
          />
          <Input
            value={row.key}
            placeholder={keyPlaceholder}
            aria-label={'Key ' + String(index + 1)}
            className="h-8 font-mono"
            onChange={(event) => patch(index, { key: event.target.value })}
          />
          <Input
            value={row.value}
            placeholder={valuePlaceholder}
            aria-label={'Value ' + String(index + 1)}
            className="h-8 font-mono"
            onChange={(event) => patch(index, { value: event.target.value })}
          />
          <IconButton
            icon="trash"
            label={'Remove row ' + String(index + 1)}
            onClick={() => onChange(rows.filter((_, position) => position !== index))}
          />
        </div>
      ))}
      <Button small icon="plus" className="self-start" onClick={() => onChange([...rows, blankRow()])}>
        Add row
      </Button>
    </div>
  );
}

/** Render one tab in the request tab strip. */
function DraftTab({
  draft,
  active,
  onSelect,
  onClose,
}: {
  draft: Draft;
  active: boolean;
  onSelect: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className={cx(
        'flex shrink-0 items-center gap-1 border-b-2 px-1',
        active ? 'border-accent bg-panel' : 'border-transparent hover:bg-hover',
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? 'page' : undefined}
        className="inline-flex h-9 max-w-[13rem] items-center gap-1.5 px-1.5"
        title={draft.name || 'Untitled request'}
      >
        <MethodBadge method={draft.method} />
        <span className="truncate text-[11.5px] font-semibold text-text">{draft.name || 'Untitled'}</span>
        {draft.dirty ? <span className="text-accent" title="Unsaved changes">*</span> : null}
      </button>
      <IconButton icon="close" label={'Close ' + (draft.name || 'request')} onClick={onClose} />
    </div>
  );
}

/** Render the response inspector for one request. */
function ResponsePanel({ result }: { result?: HttpResult }) {
  const [tab, setTab] = useState('body');
  const [view, setView] = useState<'pretty' | 'raw'>('pretty');

  if (!result) {
    return (
      <Card tone="quiet" className="flex min-h-[11rem] items-center justify-center p-4">
        <p className="text-[11.5px] text-text-mute">Send the request to inspect the response.</p>
      </Card>
    );
  }

  const text = typeof result.body === 'string' ? result.body : prettyPayload(result.body);
  const json = isJsonPayload(text);
  const shown = view === 'pretty' && json ? prettyPayload(text) : text;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusPill status={result.status} />
        <Badge tone="neutral">{formatLatency(result.elapsed_ms)}</Badge>
        <Badge tone="neutral">{formatBytes(text)}</Badge>
        {result.assertion_results ? (
          <Badge tone={result.assertions_passed ? 'ok' : 'bad'}>
            {String(result.assertion_results.filter((item) => item.passed).length)}
            {' / '}
            {String(result.assertion_results.length)} checks
          </Badge>
        ) : null}
      </div>

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'body', label: 'Body' },
          { id: 'headers', label: 'Headers', badge: Object.keys(result.headers || {}).length },
        ]}
      />

      {tab === 'body' ? (
        <div className="flex flex-col gap-2">
          {json ? (
            <div className="flex items-center gap-1">
              <Button small tone={view === 'pretty' ? 'secondary' : 'ghost'} onClick={() => setView('pretty')}>
                Pretty
              </Button>
              <Button small tone={view === 'raw' ? 'secondary' : 'ghost'} onClick={() => setView('raw')}>
                Raw
              </Button>
            </div>
          ) : null}
          <pre className="aa-scroll aa-wrap-anywhere max-h-[24rem] overflow-auto rounded-md border border-code-border bg-code-bg p-3 font-mono text-[11.5px] leading-relaxed text-text">
            {shown || '(empty response body)'}
          </pre>
        </div>
      ) : null}

      {tab === 'headers' ? (
        <div className="aa-scroll max-h-[24rem] overflow-auto rounded-md border border-line">
          <table className="w-full border-collapse text-[11.5px]">
            <tbody>
              {Object.entries(result.headers || {}).map(([key, value]) => (
                <tr key={key} className="border-b border-line-soft last:border-0">
                  <td className="w-1/3 px-2 py-1 align-top font-mono font-semibold text-text-dim">{key}</td>
                  <td className="aa-wrap-anywhere px-2 py-1 align-top font-mono text-text">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {result.assertion_results?.length ? (
        <div className="flex flex-col gap-1 rounded-md border border-line bg-panel-alt p-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-mute">Checks</p>
          {result.assertion_results.map((item, index) => (
            <div key={index} className="flex items-start gap-2 text-[11.5px]">
              <Badge tone={item.passed ? 'ok' : 'bad'}>{item.passed ? 'Pass' : 'Fail'}</Badge>
              <span className="min-w-0 text-text-dim">{item.detail}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Trigger a browser download for a blob fetched from the API. */
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
 * Render the API workspace: collections on the right, request editor in the
 * centre, and the live response underneath.
 *
 * @returns API workspace page element.
 */
export default function ApiWorkspacePage() {
  const { project, isLoadingProject, refreshProject, refreshProjects } = useProject();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [methodFilter, setMethodFilter] = useState('All');
  const [tab, setTab] = useState('params');
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<{ tone: 'ok' | 'bad' | 'info'; text: string } | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null);
  const [confirmCollection, setConfirmCollection] = useState<{ id: string; name: string } | null>(null);
  const [confirmProject, setConfirmProject] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');

  const active = drafts.find((item) => item.tabId === activeId) || drafts[0] || null;

  // Seed one editor tab once a project is available, so the surface is usable
  // without an extra click on first load.
  useEffect(() => {
    if (!project || drafts.length > 0) return;
    const draft = newDraft(undefined, project.collections?.[0]?.id);
    setDrafts([draft]);
    setActiveId(draft.tabId);
  }, [project, drafts.length]);

  /** Report an error without throwing away the editor state. */
  const fail = (reason: unknown) => {
    const message = reason instanceof ApiError
      ? reason.message
      : reason instanceof Error ? reason.message : 'Request failed';
    setFlash({ tone: 'bad', text: message });
  };

  /** Apply a patch to the active draft and recompute its dirty flag. */
  const update = (patch: Partial<Draft>) => {
    if (!active) return;
    setDrafts((prev) => prev.map((item) => {
      if (item.tabId !== active.tabId) return item;
      const next = { ...item, ...patch };
      return { ...next, dirty: signatureOf(next) !== next.baseline };
    }));
  };

  // Parse a pasted cURL command after a quiet period. The backend owns parsing.
  useEffect(() => {
    const text = active?.url ?? '';
    const tabId = active?.tabId;
    if (!tabId || !/^\s*curl(\.exe)?\s/i.test(text)) return undefined;

    const handle = window.setTimeout(() => {
      api.post<ParsedCurl>('/api/v1/curl/parse', { curl: text }).then(
        (parsed) => {
          setDrafts((prev) => prev.map((item) => {
            if (item.tabId !== tabId) return item;
            const next: Draft = {
              ...item,
              method: (parsed.method || 'GET').toUpperCase() as HttpMethod,
              url: parsed.url || item.url,
              headers: toRows(parsed.headers),
              query: toRows(parsed.query_params),
              body: bodyText(parsed.body),
              includeBody: parsed.body != null,
              bodyType: 'json',
            };
            return { ...next, baseline: signatureOf(next), dirty: false };
          }));
          setFlash({ tone: 'ok', text: 'cURL parsed into the editor.' });
        },
        (reason: unknown) => fail(reason),
      );
    }, 3000);

    return () => window.clearTimeout(handle);
  }, [active?.tabId, active?.url]);

  const createDraft = (collectionId?: string) => {
    const draft = newDraft(undefined, collectionId ?? project?.collections?.[0]?.id);
    setDrafts((prev) => [...prev, draft]);
    setActiveId(draft.tabId);
  };

  const openSaved = (saved: SavedRequest) => {
    const existing = drafts.find((item) => item.savedId === saved.id);
    if (existing) {
      setActiveId(existing.tabId);
      return;
    }
    const draft = newDraft(saved);
    setDrafts((prev) => [...prev, draft]);
    setActiveId(draft.tabId);
  };

  const closeDraft = (tabId: string) => {
    setDrafts((prev) => {
      const remaining = prev.filter((item) => item.tabId !== tabId);
      if (tabId === activeId) setActiveId(remaining[0]?.tabId ?? null);
      return remaining;
    });
  };

  /** Send the active draft through the backend proxy. */
  const send = async () => {
    if (!active) return;
    update({ busy: true });
    try {
      const result = await api.post<HttpResult>(
        '/api/v1/http/send',
        buildRequest(active),
        { timeoutMs: LLM_TIMEOUT_MS },
      );
      update({ response: result, busy: false });
      setFlash({ tone: result.status < 400 ? 'ok' : 'bad', text: 'Response ' + String(result.status) + ' in ' + formatLatency(result.elapsed_ms) });
    } catch (reason) {
      update({ busy: false });
      fail(reason);
    }
  };

  /** Send the request and evaluate the enabled assertions on the fresh response. */
  const runAssertions = async () => {
    if (!active) return;
    const checks = flattenAssertions(active.assertions);
    if (checks.length === 0) {
      setFlash({ tone: 'info', text: 'Nothing to evaluate; enable at least one assertion.' });
      return;
    }
    update({ busy: true });
    try {
      const result = await api.post<HttpResult>(
        '/api/v1/http/execute-assertions',
        { request: buildRequest(active), assertions: checks },
        { timeoutMs: LLM_TIMEOUT_MS },
      );
      update({ response: result, busy: false });
      const passed = result.assertion_results?.filter((item) => item.passed).length ?? 0;
      setFlash({ tone: result.assertions_passed ? 'ok' : 'bad', text: String(passed) + ' of ' + String(checks.length) + ' checks passed.' });
    } catch (reason) {
      update({ busy: false });
      fail(reason);
    }
  };

  /** Persist the active draft to its collection and rebase the dirty flag. */
  const saveDraft = async () => {
    if (!active || !project) return;
    if (!active.collectionId) {
      setFlash({ tone: 'bad', text: 'Choose a collection header before saving.' });
      return;
    }
    let body: unknown = null;
    if (active.includeBody && active.body.trim()) {
      body = active.body;
      if (active.bodyType === 'json') {
        try {
          body = JSON.parse(active.body);
        } catch {
          body = active.body;
        }
      }
    }
    const payload = {
      id: active.savedId,
      name: active.name.trim() || 'Untitled request',
      method: active.method,
      url: active.url.trim(),
      headers: active.headers.filter((row) => row.key.trim()),
      query_params: active.query.filter((row) => row.key.trim()),
      body,
      include_body: active.includeBody,
      assertions: active.assertions,
    };
    setBusy(true);
    try {
      const base = '/api/v1/projects/' + project.id + '/collections/' + active.collectionId + '/requests';
      const saved = active.savedId
        ? await api.put<SavedRequest>(base + '/' + active.savedId, payload)
        : await api.post<SavedRequest>(base, payload);
      setDrafts((prev) => prev.map((item) => (
        item.tabId === active.tabId ? newDraft(saved) : item
      )));
      await refreshProject();
      setFlash({ tone: 'ok', text: 'Saved "' + saved.name + '".' });
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Create a collection and open an editor tab that saves into it. */
  const createCollection = async (name: string) => {
    if (!project || !name.trim()) return;
    setBusy(true);
    try {
      const created = await api.post<{ id: string; name: string }>(
        '/api/v1/projects/' + project.id + '/collections',
        { name: name.trim() },
      );
      await refreshProject();
      const draft = newDraft(undefined, created.id);
      setDrafts((prev) => [...prev, draft]);
      setActiveId(draft.tabId);
      setFlash({ tone: 'ok', text: 'Collection "' + created.name + '" created.' });
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Rename the collection currently held in the rename dialog. */
  const renameCollection = async () => {
    if (!project || !renaming || !renaming.name.trim()) return;
    setBusy(true);
    try {
      await api.put(
        '/api/v1/projects/' + project.id + '/collections/' + renaming.id,
        { name: renaming.name.trim() },
      );
      await refreshProject();
      setFlash({ tone: 'ok', text: 'Collection renamed.' });
      setRenaming(null);
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Delete the collection held in the confirmation dialog. */
  const deleteCollection = async () => {
    if (!project || !confirmCollection) return;
    setBusy(true);
    try {
      await api.delete(
        '/api/v1/projects/' + project.id + '/collections/' + confirmCollection.id,
      );
      setDrafts((prev) => prev.filter((item) => item.collectionId !== confirmCollection.id));
      await refreshProject();
      setFlash({ tone: 'ok', text: 'Collection deleted.' });
      setConfirmCollection(null);
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Download one collection as a Postman v2.1 document. */
  const exportCollection = async (collectionId: string, name: string) => {
    try {
      const { blob, filename } = await apiDownload(
        '/api/v1/projects/' + project?.id + '/collections/' + collectionId + '/export',
        (name || 'collection') + '.postman_collection.json',
      );
      downloadBlob(blob, filename);
      setFlash({ tone: 'ok', text: 'Exported "' + name + '".' });
    } catch (reason) {
      fail(reason);
    }
  };

  /** Delete a saved request and close any editor tab that pointed at it. */
  const deleteSaved = async (saved: SavedRequest) => {
    if (!project || !saved.collection_id) return;
    setBusy(true);
    try {
      await api.delete(
        '/api/v1/projects/' + project.id + '/collections/' + saved.collection_id
        + '/requests/' + saved.id,
      );
      setDrafts((prev) => prev.filter((item) => item.savedId !== saved.id));
      await refreshProject();
      setFlash({ tone: 'ok', text: 'Request deleted.' });
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Copy a saved request into the same collection as an excluded draft. */
  const duplicateSaved = async (saved: SavedRequest) => {
    if (!project || !saved.collection_id) return;
    setBusy(true);
    try {
      const copy: Record<string, unknown> = {
        ...saved,
        name: (saved.name || 'Request') + ' Copy',
        include_for_generation: false,
        include: false,
      };
      delete copy.id;
      await api.post('/api/v1/projects/' + project.id + '/collections/'
        + saved.collection_id + '/requests', copy);
      await refreshProject();
      setFlash({ tone: 'ok', text: 'Request duplicated.' });
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Persist whether one request may be used for generation. */
  const toggleEligible = async (saved: SavedRequest, next: boolean) => {
    if (!project || !saved.collection_id) return;
    try {
      await api.put(
        '/api/v1/projects/' + project.id + '/collections/' + saved.collection_id
        + '/requests/' + saved.id,
        { include_for_generation: next, include: next },
      );
      await refreshProject();
      setFlash({
        tone: 'ok',
        text: next ? 'Request enabled for generation.' : 'Request excluded from generation.',
      });
    } catch (reason) {
      fail(reason);
    }
  };

  /** Enable or exclude every request in one collection, then sync its order. */
  const toggleCollection = async (collection: Collection, next: boolean) => {
    if (!project) return;
    setBusy(true);
    try {
      for (const request of collection.requests || []) {
        await api.put(
          '/api/v1/projects/' + project.id + '/collections/' + collection.id
          + '/requests/' + request.id,
          { include_for_generation: next, include: next },
        );
      }
      const order = next && collection.requests
        ? collection.requests.map((request) => request.id)
        : [];
      if (order.length) {
        await api.put('/api/v1/projects/' + project.id + '/generation-order', { request_ids: order });
      }
      await refreshProject();
      await refreshProjects();
      setFlash({ tone: 'ok', text: next ? 'Collection enabled for generation.' : 'Collection excluded from generation.' });
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  /** Delete the project and reset the workspace. */
  const deleteProject = async () => {
    if (!project) return;
    setBusy(true);
    try {
      await api.delete('/api/v1/projects/' + project.id);
      setDrafts([]);
      setActiveId(null);
      setConfirmProject(false);
      await refreshProjects();
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  };

  const collections = project?.collections || [];
  const requests = project?.endpoints || [];
  const totalSaved = requests.length;
  const eligibleCount = requests.filter((item) => item.include_for_generation ?? item.include).length;

  const filtered = collections.map((collection) => ({
    collection,
    requests: (collection.requests || []).filter((request) => {
      const text = (String(request.name) + ' ' + String(request.url) + ' ' + String(request.method)).toLowerCase();
      const matchesText = !search || text.includes(search.toLowerCase());
      const matchesMethod = methodFilter === 'All'
        || String(request.method || '').toUpperCase() === methodFilter;
      return matchesText && matchesMethod;
    }),
  }));

  const bodyJsonValid = useMemo(() => {
    if (!active || !active.includeBody || active.bodyType !== 'json') return true;
    if (!active.body.trim()) return true;
    try {
      JSON.parse(active.body);
      return true;
    } catch {
      return false;
    }
  }, [active]);

  const auth = active ? authHeader(active) : null;

  /** Reformat a JSON body in place, leaving invalid JSON untouched. */
  const beautify = () => {
    if (!active) return;
    try {
      update({ body: JSON.stringify(JSON.parse(active.body), null, 2) });
    } catch {
      setFlash({ tone: 'info', text: 'Body is not valid JSON, so it was left unchanged.' });
    }
  };

  return (
    <PageShell>
      <PageHeader
        title="API Workspace"
        description="Compose a request, send it, and keep it in a collection for generation."
        actions={
          <>
            <Badge tone="neutral">{String(totalSaved)} saved</Badge>
            <Badge tone={eligibleCount > 0 ? 'accent' : 'neutral'}>{String(eligibleCount)} eligible</Badge>
            {project ? (
              <Button small icon="trash" disabled={busy} onClick={() => setConfirmProject(true)}>
                Delete project
              </Button>
            ) : null}
          </>
        }
      />

      {flash ? (
        <div className="mb-3">
          <Notice tone={flash.tone === 'ok' ? 'ok' : flash.tone === 'bad' ? 'bad' : 'info'}>
            {flash.text}
          </Notice>
        </div>
      ) : null}

      {!project && !isLoadingProject ? (
        <EmptyState title="No project selected" body="Pick a project in the rail, or create one there." />
      ) : !project ? (
        <Spinner label="Loading project" />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_21rem]">
          <div className="flex min-w-0 flex-col gap-3">
            <Card className="overflow-hidden">
              <div className="aa-scroll flex items-stretch gap-1 overflow-x-auto border-b border-line px-2 py-1">
                {drafts.map((draft) => (
                  <DraftTab
                    key={draft.tabId}
                    draft={draft}
                    active={draft.tabId === active?.tabId}
                    onSelect={() => setActiveId(draft.tabId)}
                    onClose={() => closeDraft(draft.tabId)}
                  />
                ))}
                <Button small icon="plus" className="my-auto ml-1" onClick={() => createDraft()}>
                  New
                </Button>
              </div>

              {!active ? (
                <div className="p-4">
                  <EmptyState title="No request open" body="Create a request tab to start composing." />
                </div>
              ) : (
                <div className="flex flex-col gap-2.5 p-3">
                  <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-[6.5rem_minmax(0,1fr)_auto] sm:items-center">
                    <Select
                      value={active.method}
                      aria-label="Method"
                      onChange={(event) => update({ method: event.target.value as HttpMethod })}
                    >
                      {METHODS.map((method) => (
                        <option key={method} value={method}>{method}</option>
                      ))}
                    </Select>
                    <Input
                      value={active.url}
                      aria-label="Request URL"
                      placeholder="https://api.example.com/resource or paste a cURL command"
                      className="font-mono"
                      onChange={(event) => update({ url: event.target.value })}
                    />
                    <Button
                      tone="primary"
                      icon="send"
                      disabled={active.busy || busy || !active.url.trim()}
                      onClick={() => void send()}
                    >
                      {active.busy ? 'Sending' : 'Send'}
                    </Button>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5">
                    <Input
                      value={active.name}
                      aria-label="Request name"
                      placeholder="Request name"
                      className="h-8 w-[13rem]"
                      onChange={(event) => update({ name: event.target.value })}
                    />
                    <Select
                      value={active.collectionId || ''}
                      aria-label="Collection"
                      className="h-8 w-[12rem]"
                      onChange={(event) => update({ collectionId: event.target.value || undefined })}
                    >
                      <option value="">No collection</option>
                      {collections.map((collection) => (
                        <option key={collection.id} value={collection.id}>{collection.name}</option>
                      ))}
                    </Select>
                    <Button
                      small
                      icon="save"
                      disabled={busy || !active.collectionId || !active.url.trim()}
                      onClick={() => void saveDraft()}
                    >
                      Save
                    </Button>
                    <Button small icon="check" disabled={active.busy} onClick={() => void runAssertions()}>
                      Run checks
                    </Button>
                    <span className="ml-auto text-[10.5px] font-semibold text-text-mute">
                      {active.busy ? 'Working' : active.dirty ? 'Unsaved changes' : 'Saved'}
                    </span>
                  </div>

                  <p className="text-[10.5px] text-text-mute">
                    {/^\s*curl(\.exe)?\s/i.test(active.url)
                      ? 'cURL detected: parsing into these fields after 3 seconds of quiet.'
                      : 'Paste a cURL command into the URL field to fill this tab from it.'}
                  </p>

                  <Tabs
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { id: 'params', label: 'Params', badge: active.query.filter((row) => row.key).length },
                      { id: 'headers', label: 'Headers', badge: active.headers.filter((row) => row.key).length },
                      { id: 'body', label: 'Body', badge: active.includeBody ? 'on' : undefined },
                      { id: 'auth', label: 'Auth', badge: active.authType === 'none' ? undefined : active.authType },
                      { id: 'checks', label: 'Checks', badge: countEnabled(active.assertions) },
                    ]}
                  />

                  <div className="pt-1">
                    {tab === 'params' ? (
                      <div className="flex flex-col gap-2">
                        <p className="text-[10.5px] text-text-mute">
                          Query values are merged into the URL when the request is sent.
                        </p>
                        <RowEditor
                          rows={active.query}
                          onChange={(query) => update({ query })}
                          keyPlaceholder="Query key"
                          valuePlaceholder="Value"
                        />
                      </div>
                    ) : null}

                    {tab === 'headers' ? (
                      <div className="flex flex-col gap-2">
                        <p className="text-[10.5px] text-text-mute">
                          An explicit Authorization row wins over the Auth tab.
                        </p>
                        <RowEditor
                          rows={active.headers}
                          onChange={(headers) => update({ headers })}
                          keyPlaceholder="Header"
                          valuePlaceholder="Value"
                        />
                      </div>
                    ) : null}

                    {tab === 'body' ? (
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <label className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-text-dim">
                            <Checkbox
                              checked={active.includeBody}
                              onChange={(event) => update({ includeBody: event.target.checked })}
                            />
                            Send a body
                          </label>
                          <Select
                            value={active.bodyType}
                            aria-label="Body language"
                            className="h-8 w-28"
                            disabled={!active.includeBody}
                            onChange={(event) => update({
                              bodyType: event.target.value as Draft['bodyType'],
                            })}
                          >
                            {BODY_TYPES.map((type) => (
                              <option key={type} value={type}>{type.toUpperCase()}</option>
                            ))}
                          </Select>
                          <Button
                            small
                            icon="code"
                            disabled={!active.includeBody}
                            onClick={beautify}
                          >
                            Beautify
                          </Button>
                          <span
                            className={
                              'text-[10.5px] font-semibold '
                              + (bodyJsonValid ? 'text-text-mute' : 'text-bad')
                            }
                          >
                            {active.bodyType === 'json' && active.includeBody
                              ? (bodyJsonValid ? 'valid JSON' : 'invalid JSON: sent as raw text')
                              : ''}
                          </span>
                        </div>
                        <Textarea
                          rows={9}
                          spellCheck={false}
                          aria-label="Request body"
                          placeholder='{"key": "value"}'
                          className="font-mono text-[11.5px]"
                          value={active.body}
                          disabled={!active.includeBody}
                          onChange={(event) => update({ body: event.target.value })}
                        />
                      </div>
                    ) : null}

                    {tab === 'auth' ? (
                      <div className="flex flex-col gap-2">
                        <Select
                          value={active.authType}
                          aria-label="Auth type"
                          className="h-8 w-48"
                          onChange={(event) => update({
                            authType: event.target.value as Draft['authType'],
                          })}
                        >
                          <option value="none">No auth</option>
                          <option value="bearer">Bearer token</option>
                          <option value="basic">Basic auth</option>
                          <option value="apiKey">API key</option>
                        </Select>

                        {active.authType === 'bearer' ? (
                          <Input
                            value={active.token}
                            aria-label="Bearer token"
                            placeholder="Token"
                            className="font-mono"
                            onChange={(event) => update({ token: event.target.value })}
                          />
                        ) : null}

                        {active.authType === 'basic' ? (
                          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                            <Input
                              value={active.username}
                              aria-label="Basic username"
                              placeholder="Username"
                              className="font-mono"
                              onChange={(event) => update({ username: event.target.value })}
                            />
                            <Input
                              type="password"
                              value={active.password}
                              aria-label="Basic password"
                              placeholder="Password"
                              className="font-mono"
                              onChange={(event) => update({ password: event.target.value })}
                            />
                          </div>
                        ) : null}

                        {active.authType === 'apiKey' ? (
                          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                            <Input
                              value={active.apiKeyHeader}
                              aria-label="API key header"
                              placeholder="X-API-Key"
                              className="font-mono"
                              onChange={(event) => update({ apiKeyHeader: event.target.value })}
                            />
                            <Input
                              value={active.apiKey}
                              aria-label="API key"
                              placeholder="Key"
                              className="font-mono"
                              onChange={(event) => update({ apiKey: event.target.value })}
                            />
                          </div>
                        ) : null}

                        <p className="aa-wrap-anywhere font-mono text-[10.5px] text-text-mute">
                          {auth
                            ? auth[0] + ': ' + (auth[0].toLowerCase() === 'authorization'
                              ? auth[1].slice(0, 12) + '...'
                              : '***')
                            : 'No auth header will be added.'}
                        </p>
                        <p className="text-[10.5px] text-text-mute">
                          Credentials stay in this browser session; only the resulting header is sent.
                        </p>
                      </div>
                    ) : null}

                    {tab === 'checks' ? (
                      <AssertionsEditor
                        value={active.assertions}
                        onChange={(assertions) => update({ assertions })}
                        hint="run against a fresh response"
                      />
                    ) : null}
                  </div>
                </div>
              )}
            </Card>

            <Card className="p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h2 className="text-[12.5px] font-bold text-text">Response</h2>
                {active?.response ? <Badge tone="neutral">{truncate(active.url, 46)}</Badge> : null}
              </div>
              <ResponsePanel result={active?.response} />
            </Card>
          </div>

          <aside className="flex min-w-0 flex-col gap-3">
            <Card className="p-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-[12.5px] font-bold text-text">Collections</h2>
                <Button small icon="plus" onClick={() => setCreating(true)}>New</Button>
              </div>

              <div className="mt-2 flex flex-col gap-1.5">
                <Input
                  value={search}
                  aria-label="Search collections and requests"
                  placeholder="Search collections and requests"
                  className="h-8"
                  onChange={(event) => setSearch(event.target.value)}
                />
                <Select
                  value={methodFilter}
                  aria-label="Method filter"
                  className="h-8"
                  onChange={(event) => setMethodFilter(event.target.value)}
                >
                  <option value="All">All methods</option>
                  {METHODS.map((method) => (
                    <option key={method} value={method}>{method}</option>
                  ))}
                </Select>
              </div>

              <div className="aa-scroll mt-3 flex max-h-[62vh] flex-col gap-2 overflow-y-auto">
                {filtered.map(({ collection, requests: visible }) => {
                  const total = (collection.requests || []).length;
                  const on = (collection.requests || []).filter(
                    (request) => request.include_for_generation ?? request.include,
                  ).length;
                  return (
                    <div key={collection.id} className="rounded-md border border-line bg-panel-alt">
                      <div className="flex items-center gap-1.5 border-b border-line px-2 py-1.5">
                        <Checkbox
                          checked={total > 0 && on === total}
                          aria-label={'Include all ' + collection.name + ' requests'}
                          onChange={(event) => void toggleCollection(collection, event.target.checked)}
                        />
                        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-text">
                          {collection.name}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-text-mute">
                          {String(on) + '/' + String(total)}
                        </span>
                        <Menu
                          label={'Actions for ' + collection.name}
                          items={[
                            { label: 'New request', icon: 'plus', onSelect: () => createDraft(collection.id) },
                            { label: 'Rename', icon: 'edit', onSelect: () => setRenaming({ id: collection.id, name: collection.name }) },
                            { label: 'Export Postman', icon: 'download', onSelect: () => void exportCollection(collection.id, collection.name) },
                            { label: 'Delete', icon: 'trash', danger: true, onSelect: () => setConfirmCollection({ id: collection.id, name: collection.name }) },
                          ]}
                        />
                      </div>

                      <ul className="flex flex-col">
                        {visible.length === 0 ? (
                          <li className="px-2 py-1.5 text-[10.5px] text-text-mute">No matching requests.</li>
                        ) : null}
                        {visible.map((request) => {
                          const eligible = request.include_for_generation ?? request.include ?? false;
                          return (
                            <li
                              key={request.id}
                              className="flex items-center gap-1.5 border-b border-line-soft px-1.5 py-1 last:border-0 hover:bg-hover"
                            >
                              <Checkbox
                                checked={Boolean(eligible)}
                                aria-label={'Include ' + request.name + ' in generation'}
                                onChange={(event) => void toggleEligible(request, event.target.checked)}
                              />
                              <MethodBadge method={request.method} />
                              <button
                                type="button"
                                className="min-w-0 flex-1 truncate text-left text-[11.5px] text-text hover:text-accent"
                                title={request.url}
                                onClick={() => openSaved(request)}
                              >
                                {request.name || 'Untitled request'}
                              </button>
                              <Menu
                                label={'Actions for ' + request.name}
                                items={[
                                  { label: 'Open', icon: 'external', onSelect: () => openSaved(request) },
                                  { label: 'Duplicate', icon: 'copy', onSelect: () => void duplicateSaved(request) },
                                  { label: 'Delete', icon: 'trash', danger: true, onSelect: () => void deleteSaved(request) },
                                ]}
                              />
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </Card>
          </aside>
        </div>
      )}

      <Modal
        open={creating}
        title="New collection"
        description="Collections group saved requests and are used to build flows."
        onClose={() => setCreating(false)}
        footer={
          <>
            <Button onClick={() => setCreating(false)}>Cancel</Button>
            <Button
              tone="primary"
              icon="plus"
              disabled={!newName.trim() || busy}
              onClick={() => {
                const name = newName.trim();
                setCreating(false);
                setNewName('');
                void createCollection(name);
              }}
            >
            Create
            </Button>
          </>
        }
      >
        <Input
          value={newName}
          aria-label="Collection name"
          placeholder="e.g. Authentication"
          onChange={(event) => setNewName(event.target.value)}
        />
      </Modal>

      <Modal
        open={Boolean(renaming)}
        title="Rename collection"
        onClose={() => setRenaming(null)}
        footer={
          <>
            <Button onClick={() => setRenaming(null)}>Cancel</Button>
            <Button
              tone="primary"
              icon="save"
              disabled={busy || !renaming?.name.trim()}
              onClick={() => void renameCollection()}
            >
              Rename
            </Button>
          </>
        }
      >
        <Input
          value={renaming?.name || ''}
          aria-label="Collection name"
          placeholder="Collection name"
          onChange={(event) => setRenaming((prev) => (
            prev ? { ...prev, name: event.target.value } : prev
          ))}
        />
      </Modal>

      <Modal
        open={Boolean(confirmCollection)}
        title="Delete collection"
        description={'This removes "' + (confirmCollection?.name || '') + '" and its saved requests.'}
        onClose={() => setConfirmCollection(null)}
        footer={
          <>
            <Button onClick={() => setConfirmCollection(null)}>Cancel</Button>
            <Button tone="danger" icon="trash" disabled={busy} onClick={() => void deleteCollection()}>
              Delete collection
            </Button>
          </>
        }
      >
        <p className="text-[12px] text-text-dim">Deleted requests cannot be restored.</p>
      </Modal>

      <Modal
        open={confirmProject}
        title="Delete project"
        description={'This removes "' + (project?.name || '') + '" with every collection, request, case, and run.'}
        onClose={() => setConfirmProject(false)}
        footer={
          <>
            <Button onClick={() => setConfirmProject(false)}>Cancel</Button>
            <Button tone="danger" icon="trash" disabled={busy} onClick={() => void deleteProject()}>
              Delete project
            </Button>
          </>
        }
      >
        <p className="text-[12px] text-text-dim">This action cannot be undone.</p>
      </Modal>
    </PageShell>
  );
}
