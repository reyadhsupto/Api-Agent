import { proxyApiRequest } from '@/lib/server-auth';

/** Proxy API traffic through the HTTP-only JWT session. */
export const GET = proxyApiRequest;
export const POST = proxyApiRequest;
export const PUT = proxyApiRequest;
export const PATCH = proxyApiRequest;
export const DELETE = proxyApiRequest;
export const HEAD = proxyApiRequest;
