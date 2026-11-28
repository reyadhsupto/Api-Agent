'use client';

import React, { useState } from 'react';

import Icon from '@/components/ui/Icon';
import Markdown from '@/components/ui/Markdown';
import { Badge, cx } from '@/components/ui/primitives';
import type { ChatMessage, ChatSource } from '@/types/api';

const LONG_MESSAGE = 900;

/**
 * Format an ISO timestamp as local clock time.
 *
 * @param iso - Timestamp from the API.
 * @returns Time label, or empty text when the stamp is unusable.
 */
export function formatTime(iso?: string): string {
  if (!iso) return '';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString();
}

/**
 * Format an ISO timestamp as a local day label.
 *
 * @param iso - Timestamp from the API.
 * @returns Day label, or an empty string when the stamp is unusable.
 */
export function formatDay(iso?: string): string {
  if (!iso) return '';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString();
}

/**
 * Read the knowledge records a message cited.
 *
 * @param message - Transcript message.
 * @returns Cited Hub pages and reviewed facts.
 */
function knowledgeSourcesOf(message: ChatMessage): ChatSource[] {
  return Array.isArray(message.knowledge_sources) ? message.knowledge_sources : [];
}


/**
 * Render the method and title of one cited endpoint.
 *
 * @param source - Endpoint citation record.
 * @returns Readable endpoint label.
 */
function endpointLabel(source: ChatSource): string {
  const method = String(source.method || '').toUpperCase();
  const name = String(source.name || source.url || source.id || 'request');
  return method ? method + ' ' + name : name;
}

/**
 * Render one cited knowledge record.
 *
 * @param source - Knowledge citation record.
 * @returns Readable knowledge label with its kind.
 */
function knowledgeLabel(source: ChatSource): string {
  const title = String(source.title || source.name || source.id || 'record');
  const kind = String(source.kind || '').replace(/_/g, ' ');
  return kind ? kind + ' - ' + title : title;
}

/**
 * Render one transcript message.
 *
 * Assistant replies are Markdown, so they go through the Markdown renderer;
 * user text stays literal because it is exactly what the tester typed.
 *
 * @param props - Message to render.
 * @returns Message row with role, time, ordinal, citations, and a copy control.
 */
export default function MessageBubble({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const body = String(message.content || '');
  const clipped = body.length > LONG_MESSAGE;
  const knowledge = knowledgeSourcesOf(message);
  const endpoints = endpointSourcesOf(message);
  const totalSources = knowledge.length + endpoints.length;
  const created = typeof message.created_at === 'string' ? message.created_at : '';
  const metadata = (message.provider_metadata || {}) as Record<string, unknown>;
  const model = typeof metadata.model === 'string' ? metadata.model : '';

  /**
   * Copy the full message, not the clipped view.
   */
  async function copyMessage(): Promise<void> {
    try {
      await navigator.clipboard.writeText(body);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  const shown = clipped && !expanded ? body.slice(0, LONG_MESSAGE) + '\n\n...' : body;

  return (
    <div className={cx('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cx(
          'max-w-[min(56rem,88%)] rounded-lg border px-3 py-2',
          isUser ? 'border-line-accent bg-accent-soft' : 'border-line bg-panel',
        )}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-[9.5px] font-bold uppercase tracking-[0.07em] text-text-dim">
            {isUser ? 'You' : 'Assistant'}
          </span>
          <span className="text-[9.5px] text-text-mute">{formatTime(created)}</span>
          <span className="font-mono text-[9px] text-text-mute">
            {'#' + String(message.ordinal)}
          </span>
          {model ? (
            <span
              className="ml-1 max-w-[14rem] truncate rounded-pill border border-chip-line bg-chip-fill px-1.5 py-0.5 font-mono text-[9px] text-text-mute"
              title={model}
            >
              {model}
            </span>
          ) : null}
          {!isUser ? (
            <button
              type="button"
              onClick={() => void copyMessage()}
              title={copied ? 'Copied' : 'Copy reply'}
              aria-label={copied ? 'Copied' : 'Copy reply'}
              className="ml-auto inline-flex h-6 w-6 items-center justify-center rounded text-text-mute transition-colors hover:bg-hover hover:text-text"
            >
              <Icon name={copied ? 'check' : 'copy'} size={12} />
            </button>
          ) : null}
        </div>

        {isUser ? (
          <p className="aa-wrap-anywhere mt-1 whitespace-pre-wrap text-[12.5px] leading-relaxed text-text">
            {shown}
          </p>
        ) : (
          <div className="mt-1">
            <Markdown content={shown} />
          </div>
        )}

        {clipped ? (
          <button
            type="button"
            className="mt-1 text-[10.5px] font-semibold text-accent"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        ) : null}

        {totalSources > 0 ? (
          <details className="mt-1.5 border-t border-line-soft pt-1.5">
            <summary className="cursor-pointer text-[9.5px] font-semibold uppercase tracking-[0.07em] text-text-mute">
              {'Sources (' + String(totalSources) + ')'}
            </summary>

            {knowledge.length > 0 ? (
              <div className="mt-1.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-text-mute">
                  {'Knowledge ' + String(knowledge.length)}
                </p>
                <div className="mt-1 flex flex-col gap-1">
                  {knowledge.map((source, index) => (
                    <div key={String(source.id || index)} className="flex items-start gap-1.5">
                      <Badge tone="info" dot={false}>
                        {String(source.kind || 'record').replace(/_/g, ' ')}
                      </Badge>
                      <span className="aa-wrap-anywhere min-w-0 text-[10px] text-text-dim">
                        {knowledgeLabel(source)}
                      </span>
                      {source.status ? (
                        <span className="ml-auto shrink-0 font-mono text-[9px] text-text-mute">
                          {String(source.status)}
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {endpoints.length > 0 ? (
              <div className="mt-1.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-text-mute">
                  {'Endpoints ' + String(endpoints.length)}
                </p>
                <div className="mt-1 flex flex-col gap-1">
                  {endpoints.map((source, index) => (
                    <div key={String(source.id || index)} className="flex items-start gap-1.5">
                      <Badge tone="accent" dot={false}>
                        {String(source.method || 'GET').toUpperCase()}
                      </Badge>
                      <span className="min-w-0">
                        <span className="block text-[10px] font-semibold text-text-dim">
                          {endpointLabel(source)}
                        </span>
                        {source.collection_name ? (
                          <span className="block text-[9px] text-text-mute">
                            {String(source.collection_name)}
                          </span>
                        ) : null}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </details>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Read the endpoints a message cited.
 *
 * Kept separate from knowledge sources on purpose: both lists can be populated
 * at once, so returning whichever exists first hides half of the evidence.
 *
 * @param message - Transcript message.
 * @returns Cited saved requests.
 */
function endpointSourcesOf(message: ChatMessage): ChatSource[] {
  return Array.isArray(message.endpoint_sources) ? message.endpoint_sources : [];
}
