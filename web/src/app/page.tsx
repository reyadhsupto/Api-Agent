'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import Icon from '@/components/ui/Icon';
import { Badge, Card } from '@/components/ui/primitives';
import { api } from '@/lib/api';

type Backend = 'checking' | 'ok' | 'down';

/**
 * Render the landing page and a live backend connectivity check.
 *
 * @returns Landing page element.
 */
export default function HomePage() {
  const [backend, setBackend] = useState<Backend>('checking');
  const [detail, setDetail] = useState('');

  useEffect(() => {
    let alive = true;
    api.get<{ status: string }>('/api/v1/health').then(
      (data) => {
        if (!alive) return;
        setBackend(data.status === 'ok' ? 'ok' : 'down');
        setDetail(data.status || '');
      },
      (reason: unknown) => {
        if (!alive) return;
        setBackend('down');
        setDetail(reason instanceof Error ? reason.message : 'Unreachable');
      },
    );
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6 py-12">
      <Card className="w-full max-w-xl p-7">
        <div className="mb-5 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md border border-line-accent bg-accent-soft text-[13px] font-extrabold text-text">
            AA
          </span>
          <div className="min-w-0">
            <h1 className="text-[19px] font-bold leading-tight tracking-[-0.02em] text-text">Api-Agent</h1>
            <p className="text-[11.5px] text-text-dim">API test case generator and executor</p>
          </div>
        </div>

        <div className="mb-5 flex items-center gap-2 rounded-md border border-line bg-panel-alt px-3 py-2">
          <Icon name={backend === 'ok' ? 'check' : backend === 'down' ? 'alert' : 'refresh'} size={14}
            className={backend === 'ok' ? 'text-ok' : backend === 'down' ? 'text-bad' : 'text-text-mute'} />
          <span className="text-[12px] font-semibold text-text">
            {backend === 'checking' ? 'Checking backend' : backend === 'ok' ? 'Backend reachable' : 'Backend unreachable'}
          </span>
          <Badge tone={backend === 'ok' ? 'ok' : backend === 'down' ? 'bad' : 'neutral'} className="ml-auto">
            /api/v1/health
          </Badge>
        </div>
        {detail ? <p className="mb-5 aa-wrap-anywhere font-mono text-[10.5px] text-text-mute">{detail}</p> : null}

        <Link
          href="/workspace"
          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-accent bg-accent px-3 text-[12.5px] font-semibold text-on-accent hover:bg-accent-hover"
        >
          Open workspace
          <Icon name="chevronRight" size={14} />
        </Link>
      </Card>
    </div>
  );
}
