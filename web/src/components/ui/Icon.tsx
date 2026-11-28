'use client';

import React from 'react';

/** Icon names used across the workspace chrome. */
export type IconName =
  | 'plug'
  | 'home'
  | 'flask'
  | 'chat'
  | 'pulse'
  | 'sun'
  | 'moon'
  | 'search'
  | 'more'
  | 'plus'
  | 'close'
  | 'chevronRight'
  | 'chevronDown'
  | 'trash'
  | 'save'
  | 'play'
  | 'download'
  | 'refresh'
  | 'check'
  | 'alert'
  | 'arrowUp'
  | 'arrowDown'
  | 'copy'
  | 'eye'
  | 'code'
  | 'layers'
  | 'file'
  | 'send'
  | 'edit'
  | 'clock'
  | 'sparkles'
  | 'book'
  | 'database'
  | 'lock'
  | 'filter'
  | 'external'
  | 'ban'
  | 'info';

const GLYPHS: Record<IconName, React.ReactNode> = {
  home: <><path d="M3 10.5L12 3l9 7.5" /><path d="M5.5 9.5V21h13V9.5M9.5 21v-7h5v7" /></>,
  plug: <><path d="M9 3v6M15 3v6" /><path d="M6 9h12v2a6 6 0 0 1-12 0z" /><path d="M12 17v4" /></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" /><path d="M8 15h8" /></>,
  chat: <path d="M20 12a8 8 0 0 1-8 8H8l-4 2 1.5-4.5A8 8 0 1 1 20 12z" />,
  pulse: <path d="M3 12h4l3-7 4 14 3-7h4" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" /></>,
  moon: <path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></>,
  more: <><path d="M12 5h.01" /><path d="M12 12h.01" /><path d="M12 19h.01" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  chevronRight: <path d="M9 6l6 6-6 6" />,
  chevronDown: <path d="M6 9l6 6 6-6" />,
  trash: <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />,
  save: <><path d="M5 3h11l3 3v15H5z" /><path d="M8 12h8M8 16h8" /></>,
  play: <path d="M7 4l13 8-13 8z" />,
  download: <path d="M12 3v12M7 11l5 5 5-5M4 21h16" />,
refresh: <path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v6h-6" />,
  check: <path d="M4 12l5 5L20 6" />,
  alert: <><path d="M12 3l9 16H3z" /><path d="M12 9v5M12 17h.01" /></>,
  arrowUp: <path d="M12 19V5M5 12l7-7 7 7" />,
  arrowDown: <path d="M12 5v14M5 12l7 7 7-7" />,
  copy: <><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  code: <path d="M8 6L3 12l5 6M16 6l5 6-5 6" />,
  layers: <path d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5" />,
  file: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></>,
  send: <><path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4z" /></>,
  edit: <><path d="M4 20h4l10-10-4-4L4 16z" /><path d="M14 6l4 4" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  sparkles: <><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z" /><path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z" /></>,
  book: <><path d="M4 19V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M4 19a2 2 0 0 0 2 2h13" /></>,
  database: <><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6" /><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
  lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  filter: <path d="M3 5h18l-7 8v6l-4-2v-4z" />,
  external: <path d="M14 4h6v6M20 4l-9 9M9 5H5a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1v-4" />,
  ban: <><circle cx="12" cy="12" r="9" /><path d="M5 19L19 5" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
};

export interface IconProps extends React.SVGProps<SVGSVGElement> {
  /** Glyph to render. */
  name: IconName;
  /** Rendered size in pixels; the icon scales with its own box. */
  size?: number;
}

/**
 * Render one stroke icon from the shared set.
 *
 * @param props - Glyph name, size, and any SVG attributes.
 * @returns An accessible, decorative SVG element.
 */
export default function Icon({ name, size = 16, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={name === 'more' ? 2.6 : 1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {GLYPHS[name]}
    </svg>
  );
}
