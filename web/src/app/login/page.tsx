'use client';

import React, { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import Icon from '@/components/ui/Icon';
import { Button, Card, Input, Notice } from '@/components/ui/primitives';

/** Sign in to the configured local Api-Agent account. */
function LoginForm() {
  const router = useRouter();
  const search = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(String(payload.detail || 'Sign in failed'));
      const destination = search.get('next') || '/workspace';
      router.replace(destination.startsWith('/') && !destination.startsWith('//') ? destination : '/workspace');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign in failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-8">
      <Card className="w-full max-w-sm p-6 shadow-2">
        <div className="mb-5 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-line-accent bg-accent-soft text-accent">
            <Icon name="plug" size={18} />
          </span>
          <span>
            <span className="block text-base font-bold text-text">Api-Agent</span>
            <span className="text-xs text-text-dim">Sign in to your QA workbench</span>
          </span>
        </div>
        <form className="flex flex-col gap-3" onSubmit={(event) => void submit(event)}>
          {error ? <Notice tone="bad">{error}</Notice> : null}
          <label className="flex flex-col gap-1 text-xs font-semibold text-text-dim">
            Username
            <Input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-text-dim">
            Password
            <Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          <Button type="submit" tone="primary" disabled={busy || !username || !password}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </Card>
    </main>
  );
}

/** Keep search-param parsing within a Suspense boundary for App Router builds. */
export default function LoginPage() {
  return <Suspense fallback={<main className="flex min-h-dvh items-center justify-center bg-canvas text-sm text-text-dim">Loading sign in…</main>}><LoginForm /></Suspense>;
}
