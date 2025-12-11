'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/customers');
  }, [router]);

  // Show loading state while redirecting
  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-teal-electric border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
