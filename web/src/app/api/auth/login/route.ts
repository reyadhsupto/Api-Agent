import { NextResponse } from 'next/server';

import { authResponse } from '@/lib/server-auth';

/** Authenticate through FastAPI and store credentials in HTTP-only cookies. */
export async function POST(request: Request): Promise<Response> {
  const backend = process.env.BACKEND_URL || 'http://localhost:8000';
  const response = await fetch(backend + '/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: await request.text(),
    cache: 'no-store',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return NextResponse.json(data, { status: response.status });
  }
  return authResponse(data);
}
