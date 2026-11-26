'use client';

import React from 'react';

import { cx } from '@/components/ui/primitives';
import type { SectionDiff } from '@/types/api';

/** How one unified-diff line is rendered. */
type LineKind = 'add' | 'remove' | 'hunk' | 'meta' | 'context';

/**
 * Classify one line of a unified diff.
 *
 * Order matters: a removed file header is `---`, which must not be mistaken for
 * a removed content line, so metadata is checked before the add/remove prefixes.
 *
 * @param line - Single diff line, including its prefix.
 * @returns Rendering kind for the line.
 */
function lineKind(line: string): LineKind {
  if (line.startsWith('+++') || line.startsWith('---')) return 'meta';
  if (line.startsWith('@@')) return 'hunk';
  if (line.startsWith('+')) return 'add';
  if (line.startsWith('-')) return 'remove';
  return 'context';
}

const LINE_CLASS: Record<LineKind, string> = {
  add: 'aa-diff-add',
  remove: 'aa-diff-del',
  hunk: 'aa-diff-hunk',
  meta: 'aa-diff-meta',
  context: '',
};

/**
 * Render one unified-diff block with add and remove gutters.
 *
 * @param props - Raw unified diff text.
 * @returns Diff block element.
 */
export function DiffBlock({ text }: { text: string }) {
  const lines = String(text || '').split('\n');

  return (
    <pre className="aa-diff aa-scroll max-h-[22rem] overflow-auto">
      {lines.map((line, index) => {
        const kind = lineKind(line);
        const sign = kind === 'add' ? '+' : kind === 'remove' ? '-' : ' ';
        return (
          <div key={String(index)} className={cx('aa-diff-line', LINE_CLASS[kind])}>
            <span className="aa-diff-gutter" aria-hidden="true">{sign}</span>
            <span className="aa-diff-text">{line.replace(/^[+-]/, '') || ' '}</span>
          </div>
        );
      })}
    </pre>
  );
}

/**
 * Render section-level diffs produced by the Knowledge Hub draft route.
 *
 * @param props - Section diffs, plus an optional empty message.
 * @returns One block per changed section.
 */
export default function DiffView({
  sections,
  emptyLabel = 'No section changes.',
}: {
  sections: SectionDiff[];
  emptyLabel?: string;
}) {
  const changed = (sections || []).filter((item) => String(item.diff || '').trim());

  if (changed.length === 0) {
    return <p className="text-[11px] text-text-mute">{emptyLabel}</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {changed.map((section, index) => (
        <section
          key={String(section.section || index)}
          className="overflow-hidden rounded-md border border-line bg-panel-alt"
        >
          <h4 className="border-b border-line-soft px-2.5 py-1.5 text-[10.5px] font-bold uppercase tracking-[0.06em] text-text-dim">
            {String(section.section || 'Section ' + String(index + 1))}
          </h4>
          <DiffBlock text={String(section.diff || '')} />
        </section>
      ))}
    </div>
  );
}
