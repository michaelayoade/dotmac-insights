'use client';

import { redirect } from 'next/navigation';

// Redirect from old /sales/opportunities path to new /crm/pipeline/opportunities path
export default function SalesOpportunitiesRedirect() {
  redirect('/crm/pipeline/opportunities');
}
