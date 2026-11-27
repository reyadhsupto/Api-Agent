import type { Metadata } from 'next';

import { ProjectProvider } from '@/context/ProjectContext';
import { THEME_BOOT_SCRIPT, ThemeProvider } from '@/lib/theme';

import './globals.css';

export const metadata: Metadata = {
  title: 'Api-Agent | QA Workbench',
  description: 'Generate, review, and execute API test cases',
};

/**
 * Wrap every route in the theme and project providers.
 *
 * The boot script applies a stored palette before first paint; first visits use light.
 *
 * @param props - Route children.
 * @returns Document shell.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-canvas text-text antialiased">
        <ThemeProvider>
          <ProjectProvider>{children}</ProjectProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
