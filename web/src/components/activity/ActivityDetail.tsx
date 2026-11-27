'use client';

import React, { useState } from 'react';

import DiffView from '@/components/ui/DiffView';
import Markdown from '@/components/ui/Markdown';
import { Badge, Card, Notice, Tabs, cx } from '@/components/ui/primitives';
import { formatTimestamp, prettyPayload } from '@/lib/format';
import type { SectionDiff } from '@/types/api';

/** Where a record came from, which decides its detail layout. */
export type ActivityStream = 'generation' | 'knowledge';

/**
 * Read a nested object without a cast.
 *
 * @param value - Candidate object.
 * @returns The object, or an empty object.
 */
function recordOf(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

/**
 * Read true only for a populated array.
 *
 * @param value - Candidate list.
 * @returns The list, or an empty list.
 */
function listOf(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

/** Render a stored scalar or payload, making missing values explicit. */
function valueOrNA(value: unknown): string {
  if (value === null || value === undefined) return 'N/A';
  const text = typeof value === 'string' ? value.trim() : prettyPayload(value);
  return text || 'N/A';
}

/**
 * Render one read-only key/value line when a value exists.
 *
 * @param props - Label and value.
 * @returns Label line, or null when the value is empty.
 */
/**
 * Render a structured evidence section with a title and content.
 *
 * @param props - Title and content.
 * @returns Section element.
 */
function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <h4 className="text-[10px] font-bold uppercase tracking-[0.08em] text-text-mute">
        {title}
      </h4>
      <div className="rounded-lg border border-line bg-panel p-2.5 shadow-sm">
        {children}
      </div>
    </section>
  );
}

function Line({ label, value }: { label: string; value: unknown }) {
  const text = valueOrNA(value);
  return (
    <div className="flex flex-wrap items-baseline gap-1.5 text-[11px]">
      <span className="font-semibold uppercase tracking-[0.05em] text-text-mute">{label}</span>
      <span className="aa-wrap-anywhere min-w-0 text-text-dim">{text}</span>
    </div>
  );
}

/**
 * Render one activity record with the payload behind it.
 *
 * Both streams share the meta and raw sections but differ in the middle, so the
 * decision to show generation evidence or extraction evidence is made here.
 *
 * @param props - Stream and selected record.
 * @returns Detail body for the modal.
 */
export default function ActivityDetail({
  stream,
  row,
}: {
  stream: ActivityStream;
  row: Record<string, unknown>;
}) {
  const [tab, setTab] = useState<'summary' | 'evidence' | 'prompt' | 'response' | 'raw'>('summary');
  const summary = recordOf(row.summary);
  const payload = recordOf(row.payload);
  const submission = recordOf(row.submission);
  const merged = Object.keys(payload).length > 0 ? payload : row;

  const pages = listOf(summary.pages).length > 0 ? listOf(summary.pages) : listOf(merged.pages);
  const proposals = listOf(summary.proposals).length > 0 ? listOf(summary.proposals) : listOf(merged.proposals);
  const questions = listOf(merged.clarification_questions);
  const answers = recordOf(merged.clarification_answers);
  const endpoints = listOf(merged.endpoints);
  const coverage = recordOf(merged.coverage_summary);
  const requirements = listOf(coverage.requirements);
  const promptContent = valueOrNA(merged.prompt_messages ?? merged.prompt ?? merged.request_prompt);
  const responseContent = valueOrNA(
    merged.raw_response ?? merged.response_text ?? merged.llm_response ?? merged.response,
  );

  const tabs = [
    { id: 'summary', label: 'Summary' },
    { id: 'evidence', label: 'Evidence' },
    { id: 'prompt', label: 'LLM prompt' },
    { id: 'response', label: 'Raw LLM response' },
    { id: 'raw', label: 'Raw JSON' },
  ] as const;

  const status = String(merged.status || (summary.error ? 'failed' : 'recorded'));

  return (
    <div className="flex flex-col gap-2.5">
      <Tabs
        value={tab}
        onChange={(next) => setTab(
          next === 'evidence' || next === 'prompt' || next === 'response' || next === 'raw' ? next : 'summary',
        )}
        className="mb-1"
        tabs={tabs.map((item) => ({ id: item.id, label: item.label }))}
      />

      {tab === 'summary' ? (
        <div className="flex flex-col gap-3">
          <Card className="p-3">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              {stream === 'generation' ? (
                <>
                  <Badge tone={status === 'failed' ? 'bad' : merged.superseded_by_activity_id ? 'warn' : 'ok'}>
                    {merged.superseded_by_activity_id ? 'superseded' : status}
                  </Badge>
                  <Badge tone="neutral" dot={false}>
                    {String(merged.mode || merged.action || 'generation')}
                  </Badge>
                </>
              ) : (
                <>
                  <Badge tone={summary.error ? 'bad' : summary.status === 'succeeded' ? 'ok' : 'neutral'}>
                    {String(summary.status || (summary.error ? 'failed' : 'recorded'))}
                  </Badge>
                  <Badge tone="neutral" dot={false}>
                    {String(row.event_type || 'event').replace(/_/g, ' ')}
                  </Badge>
                  {row.source_type ? (
                    <Badge tone="info" dot={false}>{String(row.source_type)}</Badge>
                  ) : null}
                </>
              )}
              <span className="ml-auto font-mono text-[9.5px] text-text-mute">
                {formatTimestamp(String(row.created_at || row.timestamp || ''))}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              <Line label="Project" value={merged.project_name || merged.project_id} />
              <Line label="Provider" value={merged.provider} />
              <Line label="Model" value={merged.model} />
              <Line label="Finish" value={merged.finish_reason} />
              <Line label="Source" value={row.source_name} />
              <Line label="Revision" value={merged.revision_id} />
            </div>

            <div className="mt-3 pt-3 border-t border-line-soft flex flex-wrap gap-x-4 gap-y-2">
              {stream === 'generation' ? (
                <>
                  <Line label="Generated ids" value={listOf(merged.generated_case_ids).length} />
                  <Line label="Archived ids" value={listOf(merged.archived_case_ids).length} />
                </>
              ) : (
                <>
                  <Line label="Pages" value={summary.page_count} />
                  <Line label="Proposals" value={summary.proposal_count} />
                </>
              )}
            </div>
          </Card>

          {merged.finish_reason === 'length' && (
            <Notice tone="warn">
              The model stopped at its token limit, so this response is truncated.
            </Notice>
          )}
          {summary.error ? <Notice tone="bad">{String(summary.error)}</Notice> : null}
          {merged.error ? <Notice tone="bad">{String(merged.error)}</Notice> : null}
        </div>
      ) : null}

      {tab === 'evidence' ? (
        <div className="flex flex-col gap-2.5">
          {stream === 'generation' ? (
            <>
              <SectionCard title="Run requirements">
                <Markdown content={valueOrNA(merged.run_business_requirements)} />
              </SectionCard>
              <SectionCard title="Business requirements">
                <Markdown content={valueOrNA(merged.business_requirements)} />
              </SectionCard>
              <SectionCard title="Generation requirements">
                <Markdown content={valueOrNA(merged.generation_requirements)} />
              </SectionCard>

              {endpoints.length > 0 ? (
                <SectionCard title="Endpoints used">
                  <Card className="divide-y divide-line-soft p-0 border-0 bg-transparent">
                    {endpoints.map((entry, index) => {
                      const endpoint = recordOf(entry);
                      return (
                        <div key={String(index)} className="flex flex-wrap items-center gap-1.5 px-2 py-1.5">
                          <Badge tone="accent" dot={false}>
                            {String(endpoint.method || 'GET')}
                          </Badge>
                          <span className="min-w-0 flex-1 truncate text-[11px] text-text">
                            {String(endpoint.name || endpoint.url || 'request')}
                          </span>
                          <span className="text-[9px] text-text-mute">
                            {valueOrNA(endpoint.collection_name)}
                          </span>
                        </div>
                      );
                    })}
                  </Card>
                </SectionCard>
              ) : null}

              {requirements.length > 0 ? (
                <SectionCard title="Requirement coverage">
                  <Card className="divide-y divide-line-soft p-0 border-0 bg-transparent">
                    {requirements.map((entry, index) => {
                      const item = recordOf(entry);
                      const detail = item.note;
                      return (
                        <div key={String(index)} className="border-b border-line-soft px-3 py-2.5 last:border-b-0">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge tone={item.covered ? 'ok' : 'warn'} dot={false}>
                              {item.covered ? 'Covered' : 'Gap'}
                            </Badge>
                            {item.requirement_id ? (
                              <span className="font-mono text-[9.5px] text-text-mute">
                                {valueOrNA(item.requirement_id)}
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1.5 text-[11px] font-medium leading-relaxed text-text">
                            {valueOrNA(item.requirement || item.description)}
                          </p>
                          <div className="mt-1 grid grid-cols-[4.25rem_minmax(0,1fr)] gap-2 text-[10px] leading-relaxed">
                            <span className="font-semibold uppercase tracking-wide text-text-mute">
                              {item.covered ? 'Evidence' : 'Gap detail'}
                            </span>
                            <span className="aa-wrap-anywhere text-text-dim">{valueOrNA(detail)}</span>
                          </div>
                        </div>
                      );
                    })}
                  </Card>
                </SectionCard>
              ) : null}

              {questions.length > 0 ? (
                <SectionCard title="Clarifications">
                  <Card className="divide-y divide-line-soft p-0 border-0 bg-transparent">
                    {questions.map((entry, index) => {
                      const question = recordOf(entry);
                      const id = String(question.id || 'question_' + String(index));
                      const answer = typeof answers[id] === 'string' ? String(answers[id]) : '';
                      return (
                        <div key={id} className="border-b border-line-soft px-3 py-2.5 last:border-b-0">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="font-mono text-[9.5px] font-semibold uppercase tracking-wide text-text-mute">
                              {'Question ' + String(index + 1)}
                            </span>
                            <Badge tone={answer.trim() ? 'info' : 'warn'} dot={false}>
                              {answer.trim() ? 'Answered' : 'Open'}
                            </Badge>
                          </div>
                          <p className="mt-1.5 text-[11px] font-semibold leading-relaxed text-text">
                            {valueOrNA(question.question || question.text)}
                          </p>
                          <div className="mt-1 grid grid-cols-[4.25rem_minmax(0,1fr)] gap-2 text-[10px] leading-relaxed">
                            <span className="font-semibold uppercase tracking-wide text-text-mute">Context</span>
                            <span className="aa-wrap-anywhere text-text-dim">{valueOrNA(question.why)}</span>
                            <span className="font-semibold uppercase tracking-wide text-text-mute">Answer</span>
                            <span className={cx('aa-wrap-anywhere', answer.trim() ? 'text-ok' : 'text-text-mute')}>
                              {valueOrNA(answer)}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </Card>
                </SectionCard>
              ) : null}

            </>
          ) : (
            <>
              <SectionCard title="Source">
                <Markdown content={valueOrNA(merged.source_excerpt || merged.source_text || merged.original_source)} />
              </SectionCard>

              {pages.length > 0 ? (
                <SectionCard title="Page drafts">
                  {pages.map((entry, index) => {
                    const page = recordOf(entry);
                    const diffs = listOf(page.section_diffs) as SectionDiff[];
                    return (
                      <div key={String(index)} className="rounded border border-line bg-panel-alt p-2 mb-2 last:mb-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Badge tone="neutral" dot={false}>{String(page.scope_type || 'page')}</Badge>
                          <span className="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-text">
                            {String(page.scope_name || page.name || 'Untitled page')}
                          </span>
                          {page.error ? <Badge tone="bad" dot={false}>failed</Badge> : null}
                        </div>
                        {page.error ? (
                          <p className="aa-wrap-anywhere mt-1 text-[10.5px] text-bad">{String(page.error)}</p>
                        ) : null}
                        {diffs.length > 0 ? (
                          <div className="mt-1.5"><DiffView sections={diffs} /></div>
                        ) : null}
                        {page.draft ? (
                          <div className="mt-1.5"><Markdown content={String(page.draft)} /></div>
                        ) : null}
                      </div>
                    );
                  })}
                </SectionCard>
              ) : null}

              {proposals.length > 0 ? (
                <SectionCard title="Fact proposals">
                  {proposals.map((entry, index) => {
                    const proposal = recordOf(entry);
                    const evidence = listOf(proposal.evidence).length;
                    return (
                      <div key={String(index)} className="rounded border border-line-soft bg-panel-alt px-2 py-1.5 mb-2 last:mb-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {proposal.category ? (
                            <Badge tone="info" dot={false}>{String(proposal.category)}</Badge>
                          ) : null}
                          {proposal.scope_name ? (
                            <span className="text-[9.5px] text-text-mute">{String(proposal.scope_name)}</span>
                          ) : null}
                          {evidence > 0 ? (
                            <span className="ml-auto text-[9px] text-text-mute">
                              {String(evidence) + ' evidence'}{evidence === 1 ? '' : 's'}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-[11.5px] text-text">
                          {String(proposal.statement || proposal.title || proposal.content || '')}
                        </p>
                        {proposal.source_quote ? (
                          <p className="aa-wrap-anywhere mt-1 border-l-2 border-line-accent pl-2 text-[10.5px] text-text-mute">
                            {String(proposal.source_quote)}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                </SectionCard>
              ) : null}

              {Object.keys(submission).length > 0 ? (
                <SectionCard title="Retained submission">
                  <Markdown content={prettyPayload(submission)} />
                </SectionCard>
              ) : null}
            </>
          )}
        </div>
      ) : null}

      {tab === 'prompt' ? (
        <pre className="aa-scroll aa-wrap-anywhere max-h-[60vh] overflow-auto rounded border border-line-soft bg-code-bg p-3 font-mono text-[10px] leading-relaxed text-text">
          {promptContent}
        </pre>
      ) : null}

      {tab === 'response' ? (
        <pre className="aa-scroll aa-wrap-anywhere max-h-[60vh] overflow-auto rounded border border-line-soft bg-code-bg p-3 font-mono text-[10px] leading-relaxed text-text">
          {responseContent}
        </pre>
      ) : null}

      {tab === 'raw' ? (
        <pre className="aa-scroll aa-wrap-anywhere max-h-[60vh] overflow-auto rounded border border-line-soft bg-code-bg p-2.5 font-mono text-[10px] text-text">
          {prettyPayload(row)}
        </pre>
      ) : null}
    </div>
  );
}
