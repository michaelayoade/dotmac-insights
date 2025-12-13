'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function PurchaseInvoicesRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/purchasing/bills');
  }, [router]);

  return null;
}
