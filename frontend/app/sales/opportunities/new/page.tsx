'use client';

import { redirect } from 'next/navigation';

// Redirect from old /sales/opportunities/new path to new /crm/pipeline/opportunities/new path
export default function SalesOpportunityNewRedirect() {
  redirect('/crm/pipeline/opportunities/new');
}
