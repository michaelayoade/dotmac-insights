'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function NewSalesContactPage() {
  const router = useRouter();

  // Redirect to the main contacts/new page with sales context
  useEffect(() => {
    router.replace('/contacts/new?source=sales');
  }, [router]);

  return (
    <div className="flex items-center justify-center py-12">
      <div className="text-slate-muted">Redirecting to contact creation...</div>
    </div>
  );
}
