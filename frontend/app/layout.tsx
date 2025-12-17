import type { Metadata } from 'next';
import { Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import { Providers } from '@/components/Providers';
import AppShell from '@/components/AppShell';

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-plus-jakarta',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Dotmac BOS',
  description: 'Business Operating System - Everything you need to run your business',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`${plusJakarta.variable} ${jetbrainsMono.variable}`}>
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
      <body className={plusJakarta.className}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
