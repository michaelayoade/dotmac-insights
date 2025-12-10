import type { Metadata } from 'next';
import './globals.css';
import Layout from '@/components/Layout';
import { Providers } from '@/components/Providers';

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
    <html lang="en">
      <body>
        <Providers>
          <Layout>{children}</Layout>
        </Providers>
      </body>
    </html>
  );
}
