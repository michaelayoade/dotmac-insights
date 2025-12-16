import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';
import { Providers } from '@/components/Providers';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Dotmac Insights',
  description: 'Business intelligence dashboard for Dotmac Technologies',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('dotmac-color-scheme');
                  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  var scheme = (saved === 'light' || saved === 'dark' || saved === 'system') ? saved : (prefersDark ? 'dark' : 'light');
                  var applied = scheme === 'system' ? (prefersDark ? 'dark' : 'light') : scheme;
                  if (applied === 'dark') {
                    document.documentElement.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                  }
                  document.documentElement.dataset.colorScheme = scheme;
                } catch (e) {
                  // swallow
                }
              })();
            `,
          }}
        />
      </head>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
