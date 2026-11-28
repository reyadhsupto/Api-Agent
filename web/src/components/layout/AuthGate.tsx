'use client';

import React, { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

/** Redirect unauthenticated workspace visitors to the local sign-in screen. */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetch('/api/auth/session', { cache: 'no-store' }).then((response) => {
      if (!mounted) return;
      if (response.ok) {
        window.dispatchEvent(new Event('aa-authenticated'));
        setReady(true);
      }
      else router.replace('/login?next=' + encodeURIComponent(pathname || '/workspace'));
    }).catch(() => {
      if (mounted) router.replace('/login?next=' + encodeURIComponent(pathname || '/workspace'));
    });
    return () => { mounted = false; };
  }, [pathname, router]);

  return (
    <div className="relative h-dvh w-full overflow-hidden">
      <div aria-hidden={!ready} inert={!ready} className="h-full">
        {children}
      </div>
      {!ready ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-canvas text-sm text-text-dim"
          role="status"
          aria-live="polite"
        >
          Checking session…
        </div>
      ) : null}
    </div>
  );
}
