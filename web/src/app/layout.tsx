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
 * The dark class is server rendered so the first paint is already black, and the
 * boot script only removes it when a stored light preference exists.
 *
 * @param props - Route children.
 * @returns Document shell.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
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
