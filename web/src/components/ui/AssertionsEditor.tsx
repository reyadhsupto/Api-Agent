'use client';

import React from 'react';

import Icon from './Icon';
import { Button, Checkbox, IconButton, Input, Textarea, cx } from './primitives';
import type { AssertionConfig, Assertions } from '@/types/api';

type AssertionType = keyof Assertions;

const ORDER: AssertionType[] = ['status', 'body_contains', 'jsonpath', 'response_schema'];

const LABELS: Record<AssertionType, string> = {
  status: 'Status code',
  body_contains: 'Body contains',
  jsonpath: 'Field value',
  response_schema: 'Response schema',
};

/** Return a unique identifier for a new assertion instance. */
function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return Math.random().toString(36).slice(2);
}

/**
 * Create one assertion with the defaults for its type.
 *
 * @param type - Assertion group to create into.
 * @returns A fresh assertion configuration.
 */
export function makeAssertion(type: AssertionType): AssertionConfig {
  if (type === 'status') return { id: newId(), enabled: true, expected_status: 200 };
  if (type === 'body_contains') return { id: newId(), enabled: true, value: '' };
  if (type === 'jsonpath') return { id: newId(), enabled: true, path: '', expected_value: '' };
  return { id: newId(), enabled: true, schema: '{}' };
}

/**
 * Build the empty assertion set used by a new case.
 *
 * @returns Every group present with no instances.
 */
export function emptyAssertions(): Assertions {
  return { status: [], body_contains: [], jsonpath: [], response_schema: [] };
}

/**
 * Count enabled instances across every group.
 *
 * @param assertions - Assertion groups to inspect.
 * @returns Number of assertions that will run.
 */
export function countEnabled(assertions: Assertions): number {
  return ORDER.reduce(
    (total, type) => total + (assertions[type] || []).filter((item) => item.enabled).length,
    0,
  );
}

/**
 * Flatten enabled assertions into the payload the playground route accepts.
 *
 * @param assertions - Assertion groups to flatten.
 * @returns One record per enabled assertion, each tagged with its type.
 */
export function flattenAssertions(assertions: Assertions): Array<Record<string, unknown>> {
  return ORDER.flatMap((type) => (assertions[type] || [])
    .filter((item) => item.enabled)
    .map((item) => ({ ...item, type })));
}

export interface AssertionsEditorProps {
  /** Current assertion groups. */
  value: Assertions;
  /** Replace the groups when any instance changes. */
  onChange: (next: Assertions) => void;
  /** Where these assertions run, shown after the count. */
  hint?: string;
}

/**
 * Render repeatable assertion groups.
 *
 * A group can hold several instances because one response often needs more than
 * one check of the same kind: two acceptable status codes, or several fields
 * that must carry specific values.
 */
export default function AssertionsEditor({ value, onChange, hint }: AssertionsEditorProps) {
  const update = (type: AssertionType, instance: number, patch: Partial<AssertionConfig>) => {
    const next = (value[type] || []).map((item, index) => (
      index === instance ? { ...item, ...patch } : item
    ));
    onChange({ ...value, [type]: next });
  };

  const remove = (type: AssertionType, instance: number) => {
    const next = (value[type] || []).filter((_, index) => index !== instance);
    onChange({ ...value, [type]: next });
  };

  const add = (type: AssertionType) => {
    onChange({ ...value, [type]: [...(value[type] || []), makeAssertion(type)] });
  };

  const enabled = countEnabled(value);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-[11px] text-text-mute">
        {enabled} enabled{hint ? ' - ' + hint : ''}
      </p>

      {ORDER.map((type) => {
        const group = value[type] || [];
        const active = group.some((item) => item.enabled);
        return (
          <details key={type} className="rounded-md border border-line bg-panel-alt">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-[12px] font-semibold text-text [&::-webkit-details-marker]:hidden">
              <span className="inline-flex items-center gap-2">
                <Icon name="chevronRight" size={12} className="text-text-mute" />
                {LABELS[type]}
              </span>
              <span
                className={cx(
                  'rounded-pill border px-1.5 py-0.5 text-[10px]',
                  active
                    ? 'border-line-accent bg-accent-soft text-text'
                    : 'border-chip-line bg-chip-fill text-text-mute',
                )}
              >
                {group.length}
              </span>
            </summary>

            <div className="flex flex-col gap-2 border-t border-line px-3 py-2">
              {group.length === 0 ? (
                <p className="text-[11px] text-text-mute">No checks in this group.</p>
              ) : null}

              {group.map((config, instance) => (
                <div
                  key={config.id || String(instance)}
                  className="rounded-md border border-line-soft bg-panel px-2 py-1.5"
                >
                  <div className="flex items-start gap-2">
                    <span className="pt-1">
                      <Checkbox
                        checked={config.enabled}
                        onChange={(event) => update(type, instance, { enabled: event.target.checked })}
                        aria-label={'Enable ' + LABELS[type] + ' ' + String(instance + 1)}
                      />
                    </span>

                    {type === 'status' ? (
                      <Input
                        type="number"
                        min={100}
                        max={599}
                        value={config.expected_status ?? 200}
                        disabled={!config.enabled}
                        aria-label="Expected status code"
                        onChange={(event) => update(type, instance, {
                          expected_status: Number(event.target.value) || 200,
                        })}
                        className="h-8 w-28"
                      />
                    ) : null}

                    {type === 'body_contains' ? (
                      <Input
                        value={config.value || ''}
                        disabled={!config.enabled}
                        placeholder="Text expected in the body"
                        aria-label="Expected body text"
                        onChange={(event) => update(type, instance, { value: event.target.value })}
                        className="h-8"
                      />
                    ) : null}

                    {type === 'jsonpath' ? (
                      <div className="flex min-w-0 flex-1 flex-col gap-1.5 sm:flex-row">
                        <Input
                          value={config.path || ''}
                          disabled={!config.enabled}
                          placeholder="$.token"
                          aria-label="JSONPath"
                          onChange={(event) => update(type, instance, { path: event.target.value })}
                          className="h-8 font-mono"
                        />
                        <Input
                          value={config.expected_value || ''}
                          disabled={!config.enabled}
                          placeholder="Expected value"
                          aria-label="Expected field value"
                          onChange={(event) => update(type, instance, {
                            expected_value: event.target.value,
                          })}
                          className="h-8"
                        />
                      </div>
                    ) : null}

                    {type === 'response_schema' ? (
                      <Textarea
                        value={config.schema || '{}'}
                        disabled={!config.enabled}
                        rows={4}
                        spellCheck={false}
                        aria-label="JSON Schema"
                        placeholder='{"type":"object","required":["id"]}'
                        onChange={(event) => update(type, instance, { schema: event.target.value })}
                        className="min-h-[5rem] font-mono text-[11.5px]"
                      />
                    ) : null}

                    <IconButton
                      icon="trash"
                      label={'Remove ' + LABELS[type] + ' check'}
                      onClick={() => remove(type, instance)}
                    />
                  </div>
                </div>
              ))}

              <Button small icon="plus" onClick={() => add(type)} className="self-start">
                Add {LABELS[type].toLowerCase()}
              </Button>
            </div>
          </details>
        );
      })}
    </div>
  );
}
