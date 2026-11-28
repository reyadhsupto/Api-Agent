import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

import { clearAuthCookies } from '@/lib/server-auth';

/** Revoke the backend refresh token and clear browser cookies. */
export async function POST(): Promise<Response> {
  const backend = process.env.BACKEND_URL || 'http://localhost:8000';
  const refresh = (await cookies()).get('aa_refresh')?.value || '';
  if (refresh) {
    await fetch(backend + '/api/v1/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: 'no-store',
    }).catch(() => undefined);
  }
  const response = NextResponse.json({ logged_out: true });
  clearAuthCookies(response);
  return response;
}
