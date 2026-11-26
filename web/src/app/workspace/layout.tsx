import React from 'react';

import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';

/**
 * Provide the fixed application shell around every workspace route.
 *
 * The viewport never scrolls: the rail is fixed and `main` clips its child, so
 * each page decides where its own scroll region lives. That is what keeps the
 * chat composer pinned without a sticky hack or negative-margin escape.
 *
 * @param props - Route children.
 * @returns Shell element.
 */
export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh overflow-hidden bg-canvas text-text">
      <Sidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
