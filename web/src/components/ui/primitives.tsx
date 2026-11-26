'use client';

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import Icon, { type IconName } from './Icon';

/** Join class names, dropping falsy entries. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent';

type Tone = 'primary' | 'secondary' | 'ghost' | 'danger';

const BUTTON_TONE: Record<Tone, string> = {
  primary: 'border border-accent bg-accent text-on-accent hover:bg-accent-hover',
  secondary: 'border border-line-strong bg-panel-alt text-text hover:bg-hover',
  ghost: 'border border-transparent bg-transparent text-text-dim hover:bg-hover hover:text-text',
 danger: 'border border-bad/40 bg-bad/10 text-bad hover:bg-bad/20',
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual weight. Defaults to secondary. */
  tone?: Tone;
  /** Compact height for toolbars. */
  small?: boolean;
  /** Optional leading glyph. */
  icon?: IconName;
}

/**
 * Render one workbench button.
 *
 * @param props - Tone, size, icon, and native button attributes.
 * @returns Button element.
 */
export function Button({ tone = 'secondary', small = false, icon, className, children, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex select-none items-center justify-center gap-1.5 rounded-md font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45',
        small ? 'h-7 px-2 text-[11.5px]' : 'h-9 px-3 text-[12.5px]',
        BUTTON_TONE[tone],
        FOCUS,
        className,
      )}
      {...rest}
    >
      {icon ? <Icon name={icon} size={small ? 13 : 15} /> : null}
      {children}
    </button>
  );
}

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Glyph to render. */
  icon: IconName;
  /** Accessible name; also used as the tooltip. */
  label: string;
  /** Visual weight. Defaults to ghost. */
  tone?: Tone;
}

/**
 * Render a square icon-only button with an accessible name.
 *
 * @param props - Glyph, label, tone, and native button attributes.
 * @returns Button element sized for dense rows.
 */
export function IconButton({ icon, label, tone = 'ghost', className, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        BUTTON_TONE[tone],
        FOCUS,
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={15} />
    </button>
  );
}

const FIELD = cx(
  'w-full rounded-md border border-line-strong bg-panel-alt px-2.5 text-[12.5px] text-text',
  'placeholder:text-text-mute transition-colors hover:border-line-contrast',
  'focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25',
  'disabled:cursor-not-allowed disabled:opacity-50',
);

/** One labelled form control with optional hint text. */
export function Field({
  label,
  hint,
  children,
}: {
  label: React.ReactNode;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-text-mute">
        {label}
      </span>
      {children}
      {hint ? <span className="text-[11px] text-text-mute">{hint}</span> : null}
    </label>
  );
}

/** Native text input matching the workbench field style. */
export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className, ...rest } = props;
  return <input className={cx(FIELD, 'h-9', className)} {...rest} />;
}

/** Native textarea matching the workbench field style. */
export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className, ...rest } = props;
  return <textarea className={cx(FIELD, 'resize-y py-2 leading-relaxed', className)} {...rest} />;
}

/** Native select matching the workbench field style. */
export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className, ...rest } = props;
  return <select className={cx(FIELD, 'h-9 cursor-pointer pr-8', className)} {...rest} />;
}

/** Native checkbox with the accent colour. */
export function Checkbox(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className, ...rest } = props;
  return (
    <input
      type="checkbox"
      className={cx('h-4 w-4 shrink-0 cursor-pointer accent-accent', FOCUS, className)}
      {...rest}
    />
  );
}

const CARD_TONE = {
  plain: 'border-line bg-panel',
  quiet: 'border-line-soft bg-panel-alt',
  inset: 'border-line-soft bg-canvas',
  raised: 'border-line-strong bg-elevated shadow-2',
};

/** Surface recipe used by every card, row group, and dialog body. */
export function Card({
  tone = 'plain',
  className,
  children,
}: {
  tone?: keyof typeof CARD_TONE;
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={cx('rounded-lg border', CARD_TONE[tone], className)}>{children}</div>;
}

export type BadgeTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'bad' | 'info';

const DOT_TONE: Record<BadgeTone, string> = {
  neutral: 'bg-text-mute',
  accent: 'bg-accent',
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-bad',
  info: 'bg-info',
};

/**
 * Render a compact status badge.
 *
 * Meaning is carried by the dot and the border, and the label stays in the
 * normal text colour, so contrast holds in both palettes.
 */
export function Badge({
  tone = 'neutral',
  dot = true,
  className,
  children,
}: {
  tone?: BadgeTone;
  dot?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-pill border border-chip-line bg-chip-fill px-2 py-0.5',
        'text-[10.5px] font-semibold uppercase tracking-[0.04em] text-text',
        className,
      )}
    >
      {dot ? <span className={cx('h-1.5 w-1.5 rounded-pill', DOT_TONE[tone])} /> : null}
      {children}
    </span>
  );
}

const METHOD_TONE: Record<string, string> = {
  GET: 'border-method-get/30 bg-method-get-fill text-method-get',
  POST: 'border-method-post/30 bg-method-post-fill text-method-post',
  PUT: 'border-method-put/30 bg-method-put-fill text-method-put',
  PATCH: 'border-method-patch/30 bg-method-patch-fill text-method-patch',
  DELETE: 'border-method-delete/30 bg-method-delete-fill text-method-delete',
};

/** Render one HTTP method pill in the method colour family. */
export function MethodBadge({ method, className }: { method?: string; className?: string }) {
  const value = String(method || 'GET').toUpperCase();
  return (
    <span
      className={cx(
        'inline-flex min-w-[3.2rem] justify-center rounded-sm border px-1.5 py-0.5',
        'font-mono text-[10px] font-bold uppercase tracking-[0.03em]',
        METHOD_TONE[value] || 'border-line-strong bg-chip-fill text-text-dim',
        className,
      )}
    >
      {value}
    </span>
  );
}

/** Render an HTTP status pill; unknown codes stay neutral. */
export function StatusPill({ status, className }: { status?: number | null; className?: string }) {
  const code = Number(status);
  const known = Number.isFinite(code) && code > 0;
  const tone = !known ? 'neutral'
    : code >= 500 ? 'bad'
    : code >= 400 ? 'bad'
    : code >= 300 ? 'warn'
    : code >= 200 ? 'ok'
    : 'neutral';
  return (
    <Badge tone={tone} className={className}>
      {known ? String(code) : 'No status'}
    </Badge>
  );
}

/** Render a small spinner with a label. */
export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[12px] text-text-mute">
      <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label}
    </span>
  );
}

/** Render an empty state with one primary action. */
export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line-strong px-6 py-10 text-center">
      <p className="text-[13.5px] font-semibold text-text">{title}</p>
      {body ? <p className="max-w-md text-[12px] text-text-dim">{body}</p> : null}
      {action ? <div className="pt-2">{action}</div> : null}
    </div>
  );
}

const NOTICE_TONE = {
  ok: 'border-ok/40 bg-ok/10 text-text',
  warn: 'border-warn/40 bg-warn/10 text-text',
  bad: 'border-bad/40 bg-bad/10 text-text',
  info: 'border-info/40 bg-info/10 text-text',
};

/** Render one inline notice with a tone-matched border. */
export function Notice({
  tone = 'info',
  children,
}: {
  tone?: keyof typeof NOTICE_TONE;
  children: React.ReactNode;
}) {
  return <div className={cx('rounded-md border px-3 py-2 text-[12px]', NOTICE_TONE[tone])}>{children}</div>;
}

/** One action inside a Menu. */
export interface MenuItem {
  label: string;
  icon?: IconName;
  danger?: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

/**
 * Render a kebab menu that closes itself after a selection.
 *
 * Uses the native details element so open/close state is not another React
 * subscription and Escape returns focus without extra wiring.
 */
export function Menu({
  items,
  label = 'Actions',
  className,
}: {
  items: MenuItem[];
  label?: string;
  className?: string;
}) {
  const holder = useRef<HTMLDetailsElement>(null);
  const close = () => holder.current?.removeAttribute('open');

  return (
    <details ref={holder} className={cx('relative', className)}>
      <summary
        aria-label={label}
        title={label}
        className={cx(
          'flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-md text-text-dim',
          'transition-colors hover:bg-hover hover:text-text [&::-webkit-details-marker]:hidden',
          FOCUS,
        )}
      >
        <Icon name="more" size={15} />
      </summary>
      <div className="absolute right-0 z-30 mt-1 w-52 overflow-hidden rounded-md border border-line-strong bg-elevated py-1 shadow-3">
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            disabled={item.disabled}
            onClick={() => {
              close();
              item.onSelect();
            }}
            className={cx(
              'flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12px] transition-colors',
              'hover:bg-hover disabled:cursor-not-allowed disabled:opacity-40',
              item.danger ? 'text-bad' : 'text-text',
            )}
          >
            {item.icon ? <Icon name={item.icon} size={13} /> : null}
            {item.label}
          </button>
        ))}
      </div>
    </details>
  );
}

/**
 * Render a modal dialog over the whole viewport.
 *
 * Locks body scroll and closes on Escape or a backdrop click. Focus moves into
 * the dialog on mount through the first focusable control.
 */
export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open || !mounted) return null;

  return createPortal(
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/65 p-4 sm:p-8"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx(
          'my-auto w-full overflow-hidden rounded-xl border border-line-strong bg-elevated shadow-3',
          wide ? 'max-w-4xl' : 'max-w-xl',
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-[15px] font-bold text-text">{title}</h2>
            {description ? <p className="mt-1 text-[12px] text-text-dim">{description}</p> : null}
          </div>
          <IconButton icon="close" label={'Close ' + title} onClick={onClose} />
        </header>
        <div className="aa-scroll max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer ? (
          <footer className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">{footer}</footer>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

/** One tab descriptor. */
export interface TabItem {
  id: string;
  label: string;
  badge?: React.ReactNode;
}

/** Render an accessible tab strip; the active panel is owned by the caller. */
export function Tabs({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: TabItem[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  return (
    <div role="tablist" className={cx('flex items-center gap-0.5 overflow-x-auto border-b border-line', className)}>
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={cx(
              'inline-flex shrink-0 items-center gap-1.5 border-b-2 px-2.5 py-2 text-[12px] font-semibold transition-colors',
              active ? 'border-accent text-text' : 'border-transparent text-text-dim hover:text-text',
            )}
          >
            {tab.label}
            {tab.badge ? (
              <span className="rounded-pill bg-chip-fill px-1.5 py-0.5 text-[10px] text-text-dim">{tab.badge}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
