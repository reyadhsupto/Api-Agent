'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { cx } from '@/components/ui/primitives';

/**
 * Render assistant-authored Markdown with workbench typography.
 *
 * The assistant is instructed to answer in Markdown, so transcripts have to be
 * parsed rather than shown as preformatted text. GFM is enabled for tables,
 * task lists, and strikethrough. Raw HTML is deliberately not enabled: model
 * output is untrusted, and this component is where it is rendered.
 *
 * @param props - Markdown source and optional extra classes.
 * @returns A styled Markdown block.
 */
export default function Markdown({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  return (
    <div className={cx('aa-md', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="aa-md-scroll">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
