import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import { clearAuthCookies, rotateSession, setAuthCookies } from '@/lib/server-auth';

/** Verify the active session, rotating credentials once when required. */
export async function GET(): Promise<Response> {
  const backend = process.env.BACKEND_URL || 'http://localhost:8000';
  const jar = await cookies();
  let access = jar.get('aa_access')?.value || '';
  let response = await fetch(backend + '/api/v1/auth/me', {
    headers: { Authorization: 'Bearer ' + access }, cache: 'no-store',
  });
  let pair = null;
  if (response.status === 401) {
    pair = await rotateSession();
    if (pair) {
      access = pair.access_token;
      response = await fetch(backend + '/api/v1/auth/me', {
        headers: { Authorization: 'Bearer ' + access }, cache: 'no-store',
      });
    }
  }
  if (!response.ok) {
    const failed = NextResponse.json({ authenticated: false }, { status: 401 });
    clearAuthCookies(failed);
    return failed;
  }
  const identity = await response.json();
  const success = NextResponse.json({ authenticated: true, ...identity });
  if (pair) setAuthCookies(success, pair);
  return success;
}
