'use client';

import { usePathname } from 'next/navigation';
import Layout from '@/components/Layout';

/**
 * Wraps pages in the global shell except routes that already provide their own
 * dedicated layout (e.g., Books and HR). This prevents double-wrapping and
 * lets section layouts control their experience.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const rootSegment = (pathname || '').split('/')[1] || '';
  const hasDedicatedLayout = rootSegment === 'books' || rootSegment === 'hr' || rootSegment === 'support';

  if (hasDedicatedLayout) {
    return <>{children}</>;
  }

  return <Layout>{children}</Layout>;
}
