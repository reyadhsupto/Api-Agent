'use client';

import React from 'react';

import { Button, Textarea } from '@/components/ui/primitives';

/**
 * Render the composer pinned to the bottom of the conversation column.
 *
 * The composer is a flex sibling of the transcript, not a child of it, so it
 * never enters the scroll area. That is what keeps it reachable however long the
 * conversation grows.
 *
 * @param props - Current draft, send and draft handlers, and busy flags.
 * @returns Composer element.
 */
export default function ChatComposer({
  value,
  onChange,
  onSend,
  disabled = false,
  busy = false,
  archived = false,
  disabledReason,
}: {
  value: string;
  onChange: (next: string) => void;
  onSend: () => void;
  disabled?: boolean;
  busy?: boolean;
  archived?: boolean;
  disabledReason?: string;
}) {
  /**
   * Send on Enter, keep the newline on Shift+Enter, and never send while busy.
   *
   * @param event - Textarea key event.
   */
  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (busy || event.shiftKey) return;
    if (event.key !== 'Enter') return;
    event.preventDefault();
    if (!disabled && value.trim()) onSend();
  }

  return (
    <div className="shrink-0 border-t border-line bg-rail p-2.5">
      {archived ? (
        <p className="mb-1.5 text-[10.5px] text-warn">This thread is archived and read only.</p>
      ) : null}
      {disabledReason ? (
        <p className="mb-1.5 text-[10.5px] text-text-mute">{disabledReason}</p>
      ) : null}
      <div className="flex items-end gap-2">
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Message the project assistant"
          aria-label="Message"
          title="Ask about product behavior, share requirements, or clarify an earlier answer in this project thread."
          disabled={disabled || archived}
          className="min-h-9"
        />
        <Button
          tone="primary"
          small
          icon="send"
          loading={busy}
          onClick={onSend}
          disabled={disabled || archived || busy || !value.trim()}
        >
          {busy ? 'Thinking…' : 'Send'}
        </Button>
      </div>
      {busy ? (
        <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-text-mute" role="status" aria-live="polite">
          <span>Assistant is thinking</span>
          <span aria-hidden="true" className="inline-flex gap-0.5">
            {[0, 1, 2].map((dot) => (
              <span key={dot} className="animate-bounce font-bold" style={{ animationDelay: `${dot * 120}ms` }}>·</span>
            ))}
          </span>
        </div>
      ) : (
        <p className="mt-1 text-[9.5px] text-text-mute">
          Enter sends. Shift and Enter starts a new line.
        </p>
      )}
    </div>
  );
}
